"""Inyección controlada de defectos en las exportaciones crudas.

Cada defecto queda registrado en una bitácora (tabla, clave, tipo, valor
original y valor sucio). Con ella se mide qué tan bien detectan y corrigen
los procesos ETL y las reglas de calidad.
"""

import unicodedata

import numpy as np
import pandas as pd

from .catalogs import VARIANTES_ESTADO
from .config import GeneratorConfig

FORMATO_ISO = "%Y-%m-%d %H:%M:%S"


class Bitacora:
    def __init__(self):
        self.filas: list[dict] = []

    def agregar(self, tabla, claves, tipo, originales, sucios):
        for c, o, s in zip(claves, originales, sucios):
            self.filas.append({"tabla": tabla, "clave": str(c), "tipo_defecto": tipo,
                               "valor_original": "" if pd.isna(o) else str(o),
                               "valor_sucio": "" if pd.isna(s) else str(s)})

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.filas, columns=["tabla", "clave", "tipo_defecto", "valor_original", "valor_sucio"])


def _muestra(rng, df, frac) -> np.ndarray:
    k = int(round(len(df) * frac))
    return rng.choice(df.index.to_numpy(), size=k, replace=False) if k else np.array([], dtype=int)


def _sin_acentos(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c))


def ensuciar(cfg: GeneratorConfig, rng: np.random.Generator, crudo: dict[str, pd.DataFrame]):
    """Recibe las tablas en formato de exportación y las devuelve con defectos."""
    p = cfg.defectos
    log = Bitacora()
    crudo = {k: v.copy() for k, v in crudo.items()}

    # --- clientes -------------------------------------------------------------
    cli = crudo["clientes"]
    idx = _muestra(rng, cli, p["cliente_casi_duplicado"])
    dups = cli.loc[idx].copy()
    siguiente = cli["id_cliente"].max() + 1
    dups["id_cliente"] = np.arange(siguiente, siguiente + len(dups))
    variante = rng.integers(0, 3, len(dups))
    dups["nombre"] = np.select([variante == 0, variante == 1],
                               [dups["nombre"].str.upper(), dups["nombre"].map(_sin_acentos)],
                               "  " + dups["nombre"] + " ")
    dups["apellido_paterno"] = np.where(variante == 0, dups["apellido_paterno"].str.upper(),
                                        dups["apellido_paterno"].map(_sin_acentos))
    dups["email"] = np.where(rng.random(len(dups)) < 0.5, dups["email"].str.upper(), "")
    log.agregar("clientes", dups["id_cliente"], "cliente_casi_duplicado", cli.loc[idx, "id_cliente"], dups["id_cliente"])
    mapa_dup = dict(zip(cli.loc[idx, "id_cliente"], dups["id_cliente"]))

    for col, tipo in (("email", "cliente_email_faltante"), ("telefono", "cliente_telefono_faltante")):
        i = _muestra(rng, cli, p[tipo])
        log.agregar("clientes", cli.loc[i, "id_cliente"], tipo, cli.loc[i, col], [""] * len(i))
        cli.loc[i, col] = ""

    con_email = cli[cli["email"] != ""]
    i = _muestra(rng, con_email, p["cliente_email_invalido"])
    malos = [rng.choice([e.replace("@", ""), e.replace(".com", ".con"), e.replace("@", " @ ")]) for e in cli.loc[i, "email"]]
    log.agregar("clientes", cli.loc[i, "id_cliente"], "cliente_email_invalido", cli.loc[i, "email"], malos)
    cli.loc[i, "email"] = malos

    i = _muestra(rng, cli, p["cliente_estado_variante"])
    variantes = [rng.choice(VARIANTES_ESTADO[e]) for e in cli.loc[i, "estado"]]
    log.agregar("clientes", cli.loc[i, "id_cliente"], "cliente_estado_variante", cli.loc[i, "estado"], variantes)
    cli.loc[i, "estado"] = variantes
    crudo["clientes"] = pd.concat([cli, dups], ignore_index=True).sort_values("id_cliente").reset_index(drop=True)

    # --- productos ------------------------------------------------------------
    prod = crudo["productos"]
    i = _muestra(rng, prod, p["producto_categoria_faltante"])
    log.agregar("productos", prod.loc[i, "sku"], "producto_categoria_faltante", prod.loc[i, "categoria"], [""] * len(i))
    prod.loc[i, "categoria"] = ""
    i = _muestra(rng, prod, p["producto_costo_mayor_precio"])
    nuevo = (prod.loc[i, "precio_unitario"] * rng.uniform(1.05, 1.5, len(i))).round(2)
    log.agregar("productos", prod.loc[i, "sku"], "producto_costo_mayor_precio", prod.loc[i, "costo_unitario"], nuevo)
    prod.loc[i, "costo_unitario"] = nuevo

    # --- ventas ---------------------------------------------------------------
    ven = crudo["ventas"]
    # Parte de las compras del cliente original quedan a nombre de su duplicado.
    tiene_dup = ven["id_cliente"].isin(list(mapa_dup))
    reasigna = tiene_dup & (rng.random(len(ven)) < 0.3)
    ven.loc[reasigna, "id_cliente"] = ven.loc[reasigna, "id_cliente"].map(mapa_dup)

    ven["fecha_hora"] = ven["fecha_hora"].dt.strftime(FORMATO_ISO)
    i = _muestra(rng, ven, p["venta_fecha_formato_alterno"])
    alterno = pd.to_datetime(ven.loc[i, "fecha_hora"]).dt.strftime("%d/%m/%Y %H:%M")
    log.agregar("ventas", ven.loc[i, "id_venta"], "venta_fecha_formato_alterno", ven.loc[i, "fecha_hora"], alterno)
    ven.loc[i, "fecha_hora"] = alterno.to_numpy()

    i = _muestra(rng, ven.drop(index=i), p["venta_fecha_futura"])
    futura = [("2031" if rng.random() < 0.5 else "2027") + f[4:] for f in ven.loc[i, "fecha_hora"]]
    log.agregar("ventas", ven.loc[i, "id_venta"], "venta_fecha_futura", ven.loc[i, "fecha_hora"], futura)
    ven.loc[i, "fecha_hora"] = futura

    i = _muestra(rng, ven, p["venta_metodo_pago_faltante"])
    log.agregar("ventas", ven.loc[i, "id_venta"], "venta_metodo_pago_faltante", ven.loc[i, "metodo_pago"], [""] * len(i))
    ven.loc[i, "metodo_pago"] = ""

    i = _muestra(rng, ven, p["venta_total_inconsistente"])
    malo = (ven.loc[i, "total"] * rng.choice([0.1, 0.5, 1.5, 10], len(i))).round(2)
    log.agregar("ventas", ven.loc[i, "id_venta"], "venta_total_inconsistente", ven.loc[i, "total"], malo)
    ven.loc[i, "total"] = malo

    i = _muestra(rng, ven, p["sucursal_codigo_sucio"])
    sucio = [rng.choice([c.lower(), f" {c} ", c[:-2] + "-" + c[-2:]]) for c in ven.loc[i, "codigo_sucursal"]]
    log.agregar("ventas", ven.loc[i, "id_venta"], "sucursal_codigo_sucio", ven.loc[i, "codigo_sucursal"], sucio)
    ven.loc[i, "codigo_sucursal"] = sucio

    i = _muestra(rng, ven, p["venta_duplicada"])
    log.agregar("ventas", ven.loc[i, "id_venta"], "venta_duplicada", ven.loc[i, "id_venta"], ven.loc[i, "id_venta"])
    ven = pd.concat([ven, ven.loc[i]]).sort_values("id_venta", kind="stable").reset_index(drop=True)
    crudo["ventas"] = ven

    # --- detalle de venta -----------------------------------------------------
    det = crudo["detalle_venta"]
    i = _muestra(rng, det, p["detalle_cantidad_negativa"])
    log.agregar("detalle_venta", det.loc[i, "id_detalle"], "detalle_cantidad_negativa", det.loc[i, "cantidad"], -det.loc[i, "cantidad"])
    det.loc[i, "cantidad"] = -det.loc[i, "cantidad"]

    i = _muestra(rng, det, p["detalle_precio_escala"])
    escalado = (det.loc[i, "precio_unitario"] * rng.choice([10, 0.1], len(i))).round(2)
    log.agregar("detalle_venta", det.loc[i, "id_detalle"], "detalle_precio_escala", det.loc[i, "precio_unitario"], escalado)
    det.loc[i, "precio_unitario"] = escalado

    i = _muestra(rng, det, p["detalle_producto_inexistente"])
    fantasma = [f"NX-ZZZ-{n:05d}" for n in rng.integers(90000, 99999, len(i))]
    log.agregar("detalle_venta", det.loc[i, "id_detalle"], "detalle_producto_inexistente", det.loc[i, "sku"], fantasma)
    det.loc[i, "sku"] = fantasma

    i = _muestra(rng, det, p["detalle_duplicado"])
    log.agregar("detalle_venta", det.loc[i, "id_detalle"], "detalle_duplicado", det.loc[i, "id_detalle"], det.loc[i, "id_detalle"])
    crudo["detalle_venta"] = pd.concat([det, det.loc[i]]).sort_values("id_detalle", kind="stable").reset_index(drop=True)

    # --- movimientos ----------------------------------------------------------
    mov = crudo["movimientos_inventario"]
    i = _muestra(rng, mov, p["movimiento_cantidad_cero"])
    log.agregar("movimientos_inventario", mov.loc[i, "id_movimiento"], "movimiento_cantidad_cero", mov.loc[i, "cantidad"], [0] * len(i))
    mov.loc[i, "cantidad"] = 0

    return crudo, log.to_frame()
