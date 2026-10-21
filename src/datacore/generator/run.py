"""Orquestador del generador: produce el dataset limpio (verdad de referencia)
y las exportaciones crudas con defectos que consumirá el ETL."""

import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

from . import defects, incidents, inventory, masters, sales
from .config import GeneratorConfig


def _log(msg: str, t0: float) -> None:
    print(f"[{time.perf_counter() - t0:6.1f}s] {msg}", flush=True)


def generar(cfg: GeneratorConfig, salida: Path) -> dict[str, pd.DataFrame]:
    t0 = time.perf_counter()
    rng = np.random.default_rng(cfg.seed)
    fake = Faker("es_MX")
    fake.seed_instance(cfg.seed)
    dias = pd.date_range(cfg.fecha_inicio, cfg.fecha_fin, freq="D")

    sucursales = masters.build_sucursales()
    categorias = masters.build_categorias()
    proveedores = masters.build_proveedores(cfg, rng, fake, categorias)
    productos = masters.build_productos(cfg, rng, categorias, proveedores)
    clientes = masters.build_clientes(cfg, rng, fake, sucursales)
    _log(f"catálogos: {len(productos)} productos, {len(clientes)} clientes, {len(proveedores)} proveedores", t0)

    fallas = sales.generar_fallas_sistema(cfg, rng, sucursales, dias)
    tickets = sales.generar_tickets(cfg, rng, sucursales, clientes, dias, fallas)
    precios = sales.tabla_precios(cfg, rng, productos, sorted(dias.year.unique()))
    renglones = sales.generar_renglones(cfg, rng, tickets, productos, sucursales, categorias, precios)
    _log(f"demanda: {len(tickets):,} tickets, {len(renglones):,} renglones", t0)

    # Demanda diaria por sucursal-producto (los tickets cancelados no consumen inventario).
    cancelada = renglones["id_venta"].map(tickets.set_index("id_venta")["estatus"]) == "cancelada"
    pos_suc = pd.Series(np.arange(len(sucursales)), index=sucursales["id_sucursal"])
    pos_prod = pd.Series(np.arange(len(productos)), index=productos["id_producto"])
    pos_dia = pd.Series(np.arange(len(dias)), index=dias)
    validos = renglones[~cancelada]
    demanda = np.zeros((len(sucursales), len(productos), len(dias)))
    np.add.at(demanda, (pos_suc[validos["id_sucursal"]].to_numpy(), pos_prod[validos["id_producto"]].to_numpy(),
                        pos_dia[validos["fecha"]].to_numpy()), validos["cantidad"].to_numpy())

    inv = inventory.simular(cfg, rng, demanda, sucursales, productos, proveedores, dias)
    _log(f"inventario: {len(inv.movimientos):,} movimientos, {len(inv.entregas):,} órdenes de compra, "
         f"{inv.perdido.sum() / demanda.sum():.1%} de la demanda no surtida", t0)

    renglones = _recortar_a_lo_surtido(renglones, cancelada, inv.vendido, pos_suc, pos_prod, pos_dia)
    tickets = tickets[tickets["id_venta"].isin(renglones["id_venta"])].reset_index(drop=True)

    renglones["subtotal"] = (renglones["cantidad"] * renglones["precio_unitario"]
                             * (1 - renglones["descuento_pct"])).round(2)
    renglones = renglones.sort_values(["id_venta", "id_producto"]).reset_index(drop=True)
    renglones.insert(0, "id_detalle", np.arange(1, len(renglones) + 1))
    tickets["total"] = tickets["id_venta"].map(renglones.groupby("id_venta")["subtotal"].sum()).round(2)

    incid = incidents.generar(cfg, rng, dias, sucursales, productos, proveedores, fallas,
                              inv.perdido, inv.entregas, inv.movimientos)
    _log(f"ventas finales: {len(tickets):,} tickets, {len(renglones):,} renglones; {len(incid):,} incidencias", t0)

    precio_actual = precios[precios.columns.max()]
    productos["precio_unitario"] = productos["id_producto"].map(precio_actual)
    productos["costo_unitario"] = (productos["precio_unitario"] * (1 - productos["_margen"])).round(2)
    tickets["id_cliente"] = tickets["id_cliente"].astype("Int64")

    limpio = {
        "sucursales": sucursales[["id_sucursal", "codigo", "nombre", "ciudad", "estado", "region", "tamano",
                                  "fecha_apertura"]],
        "categorias": categorias[["id_categoria", "nombre"]],
        "proveedores": proveedores[["id_proveedor", "nombre", "rfc", "ciudad", "estado", "telefono", "email",
                                    "dias_entrega", "activo"]],
        "productos": productos[["id_producto", "sku", "nombre", "id_categoria", "id_proveedor", "precio_unitario",
                                "costo_unitario", "unidad", "fecha_alta", "activo"]],
        "clientes": clientes.drop(columns=["_frecuencia"]),
        "ventas": tickets[["id_venta", "folio", "fecha_hora", "id_sucursal", "id_cliente", "metodo_pago",
                           "total", "estatus"]],
        "detalle_venta": renglones[["id_detalle", "id_venta", "id_producto", "cantidad", "precio_unitario",
                                    "descuento_pct", "subtotal"]],
        "inventario": inv.existencia_final,
        "movimientos_inventario": inv.movimientos,
        "incidencias": incid,
    }
    ocultos = {
        "ordenes_compra": inv.entregas,
        "demanda_perdida": _demanda_perdida(inv.perdido, sucursales, productos, dias),
        "parametros_productos": productos[["id_producto", "_popularidad", "_tendencia_anual", "_fecha_baja"]],
        "fallas_sistema": fallas,
    }

    crudo = _formato_exportacion(limpio)
    crudo, bitacora = defects.ensuciar(cfg, rng, crudo)
    _log(f"defectos inyectados: {len(bitacora):,}", t0)

    _escribir(salida, cfg, limpio, ocultos, crudo, bitacora)
    _log(f"listo → {salida.resolve()}", t0)
    return limpio


def _recortar_a_lo_surtido(r, cancelada, vendido, pos_suc, pos_prod, pos_dia) -> pd.DataFrame:
    """Quita de los renglones lo que no se pudo surtir. Se atiende en orden de llegada."""
    activos = r[~cancelada].sort_values(["fecha", "id_venta"]).copy()
    i = pos_suc[activos["id_sucursal"]].to_numpy()
    j = pos_prod[activos["id_producto"]].to_numpy()
    d = pos_dia[activos["fecha"]].to_numpy()
    disponible = vendido[i, j, d]
    acumulado_previo = activos.groupby(["id_sucursal", "id_producto", "fecha"])["cantidad"].cumsum() - activos["cantidad"]
    activos["cantidad"] = np.clip(disponible - acumulado_previo.to_numpy(), 0, activos["cantidad"].to_numpy())
    activos = activos[activos["cantidad"] > 0]
    out = pd.concat([activos, r[cancelada]])
    out["cantidad"] = out["cantidad"].astype(np.int64)
    return out.drop(columns=["_mayorista"])


def _demanda_perdida(perdido, sucursales, productos, dias) -> pd.DataFrame:
    i, j, d = np.nonzero(perdido)
    return pd.DataFrame({"fecha": dias[d], "id_sucursal": sucursales["id_sucursal"].to_numpy()[i],
                         "id_producto": productos["id_producto"].to_numpy()[j],
                         "unidades": perdido[i, j, d].astype(np.int64)})


def _formato_exportacion(limpio: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Las áreas exportan con códigos de negocio (código de sucursal, SKU), no con llaves internas."""
    cod = limpio["sucursales"].set_index("id_sucursal")["codigo"]
    sku = limpio["productos"].set_index("id_producto")["sku"]
    cat = limpio["categorias"].set_index("id_categoria")["nombre"]

    def con_codigos(df, quitar_producto=True):
        df = df.copy()
        df.insert(df.columns.get_loc("id_sucursal"), "codigo_sucursal", df["id_sucursal"].map(cod))
        df = df.drop(columns=["id_sucursal"])
        if "id_producto" in df:
            df.insert(df.columns.get_loc("id_producto"), "sku", df["id_producto"].map(sku))
            if quitar_producto:
                df = df.drop(columns=["id_producto"])
        return df

    productos = limpio["productos"].copy()
    productos.insert(productos.columns.get_loc("id_categoria"), "categoria", productos["id_categoria"].map(cat))
    productos = productos.drop(columns=["id_categoria"])
    detalle = limpio["detalle_venta"].copy()
    detalle.insert(detalle.columns.get_loc("id_producto"), "sku", detalle["id_producto"].map(sku))
    detalle = detalle.drop(columns=["id_producto"])
    return {
        "sucursales": limpio["sucursales"],
        "proveedores": limpio["proveedores"],
        "productos": productos,
        "clientes": limpio["clientes"],
        "ventas": con_codigos(limpio["ventas"]),
        "detalle_venta": detalle,
        "inventario": con_codigos(limpio["inventario"]),
        "movimientos_inventario": con_codigos(limpio["movimientos_inventario"]),
        "incidencias": con_codigos(limpio["incidencias"]),
    }


def _escribir(salida: Path, cfg, limpio, ocultos, crudo, bitacora) -> None:
    raw = salida / "raw"
    ref = salida / "ground_truth"
    for carpeta in ("ventas", "catalogos", "clientes", "inventario", "operacion"):
        (raw / carpeta).mkdir(parents=True, exist_ok=True)
    ref.mkdir(parents=True, exist_ok=True)

    # Ventas y movimientos: un archivo por año, como los cierres anuales del punto de venta.
    # Se parte por el año real del ticket, aunque su fecha venga mal capturada.
    ven = crudo["ventas"]
    anio_real = limpio["ventas"].set_index("id_venta")["fecha_hora"].dt.year
    anio_venta = ven["id_venta"].map(anio_real)
    det = crudo["detalle_venta"]
    anio_det = det["id_venta"].map(anio_real)
    for anio in sorted(anio_real.unique()):
        ven[anio_venta == anio].to_csv(raw / "ventas" / f"ventas_{anio}.csv", index=False)
        det[anio_det == anio].to_csv(raw / "ventas" / f"detalle_venta_{anio}.csv", index=False)
    mov = crudo["movimientos_inventario"]
    for anio, grupo in mov.groupby(mov["fecha"].dt.year):
        grupo.to_csv(raw / "inventario" / f"movimientos_inventario_{anio}.csv", index=False)
    crudo["inventario"].to_csv(raw / "inventario" / "inventario_actual.csv", index=False)

    # Compras administra sus catálogos en Excel.
    crudo["productos"].to_excel(raw / "catalogos" / "productos.xlsx", index=False, sheet_name="Productos")
    crudo["proveedores"].to_excel(raw / "catalogos" / "proveedores.xlsx", index=False, sheet_name="Proveedores")
    crudo["sucursales"].to_csv(raw / "catalogos" / "sucursales.csv", index=False)
    # El CRM exporta en Windows-1252 con punto y coma.
    crudo["clientes"].to_csv(raw / "clientes" / "clientes.csv", index=False, sep=";", encoding="cp1252",
                             errors="replace")
    crudo["incidencias"].to_csv(raw / "operacion" / "incidencias.csv", index=False)

    for nombre, df in {**limpio, **ocultos}.items():
        df.to_parquet(ref / f"{nombre}.parquet", index=False)
    bitacora.to_csv(ref / "defectos_inyectados.csv", index=False)
    meta = asdict(cfg) | {"filas": {k: len(v) for k, v in limpio.items()},
                          "defectos_por_tipo": bitacora["tipo_defecto"].value_counts().to_dict()}
    (ref / "metadata.json").write_text(json.dumps(meta, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
