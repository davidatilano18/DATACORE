"""Generación de la demanda: tickets de venta y sus renglones.

Aquí se produce la demanda "real" de los clientes. Después, el simulador de
inventario recorta los renglones que no se pudieron surtir por falta de stock.
"""

import numpy as np
import pandas as pd

from .config import PERFILES_ESTACIONALES, GeneratorConfig

FACTOR_DIA_SEMANA = np.array([0.85, 0.85, 0.90, 0.95, 1.15, 1.35, 1.00])  # lun..dom
CATEGORIAS_BUEN_FIN = {"Electrónica": 2.8, "Juguetes": 1.8, "Hogar": 2.0}
HORAS = np.arange(9, 21)
PESO_HORA = np.array([0.04, 0.06, 0.08, 0.11, 0.12, 0.09, 0.07, 0.08, 0.11, 0.11, 0.08, 0.05])


def buen_fin(anio: int) -> pd.DatetimeIndex:
    """Viernes previo al tercer lunes de noviembre, hasta ese lunes."""
    lunes = pd.date_range(f"{anio}-11-01", f"{anio}-11-30", freq="W-MON")[2]
    return pd.date_range(lunes - pd.Timedelta(days=3), lunes)


def factores_calendario(dias: pd.DatetimeIndex) -> tuple[np.ndarray, np.ndarray]:
    """Factor de afluencia por día y marca de Buen Fin."""
    f = FACTOR_DIA_SEMANA[dias.dayofweek].copy()
    quincena = dias.day.isin([1, 15, 16]) | dias.is_month_end
    f[quincena] *= 1.15
    md = dias.strftime("%m-%d")
    ajustes = {"12-18": 1.25, "12-19": 1.3, "12-20": 1.35, "12-21": 1.4, "12-22": 1.45, "12-23": 1.6,
               "12-24": 1.3, "12-25": 0.3, "12-31": 0.7, "01-01": 0.3, "01-05": 1.5, "01-06": 1.2,
               "04-29": 1.2, "04-30": 1.3, "05-08": 1.2, "05-09": 1.35, "05-10": 1.5, "09-16": 0.6}
    for clave, valor in ajustes.items():
        f[md == clave] *= valor
    es_bf = np.zeros(len(dias), dtype=bool)
    for anio in dias.year.unique():
        es_bf |= dias.isin(buen_fin(anio))
    f[es_bf] *= 1.9
    return f, es_bf


def generar_fallas_sistema(cfg, rng, sucursales, dias) -> pd.DataFrame:
    """Días en que el punto de venta de una sucursal estuvo caído parte del día."""
    filas = []
    p = cfg.fallas_sistema_por_mes_sucursal / 30.4
    for suc in sucursales.itertuples():
        abiertos = dias[dias >= suc.fecha_apertura]
        marcados = abiertos[rng.random(len(abiertos)) < p]
        for d in marcados:
            filas.append({"id_sucursal": suc.id_sucursal, "fecha": d,
                          "horas_fuera": int(rng.integers(2, 9))})
    return pd.DataFrame(filas, columns=["id_sucursal", "fecha", "horas_fuera"])


def generar_tickets(cfg: GeneratorConfig, rng: np.random.Generator, sucursales: pd.DataFrame,
                    clientes: pd.DataFrame, dias: pd.DatetimeIndex, fallas: pd.DataFrame) -> pd.DataFrame:
    factor_dia, _ = factores_calendario(dias)
    anios = (dias - dias[0]).days.to_numpy() / 365.25
    tendencia_trafico = (1.03) ** anios

    fallas_idx = {(r.id_sucursal, r.fecha): r.horas_fuera for r in fallas.itertuples()}
    bloques = []
    for suc in sucursales.to_dict("records"):
        dias_abierta = (dias - suc["fecha_apertura"]).days.to_numpy()
        # Las sucursales nuevas tardan unos 6 meses en alcanzar su afluencia normal.
        maduracion = np.clip(0.45 + 0.55 * dias_abierta / 180, 0, 1)
        lam = suc["_tickets_dia"] * factor_dia * tendencia_trafico * maduracion
        lam[dias_abierta < 0] = 0
        for i, d in enumerate(dias):
            horas = fallas_idx.get((suc["id_sucursal"], d))
            if horas:
                lam[i] *= 1 - horas / 12
        conteo = rng.poisson(lam)
        bloques.append(pd.DataFrame({
            "id_sucursal": suc["id_sucursal"],
            "fecha": np.repeat(dias.to_numpy(), conteo),
        }))
    t = pd.concat(bloques, ignore_index=True)

    n = len(t)
    hora = rng.choice(HORAS, size=n, p=PESO_HORA / PESO_HORA.sum())
    segundos = hora * 3600 + rng.integers(0, 3600, n)
    t["fecha_hora"] = t["fecha"] + pd.to_timedelta(segundos, unit="s")
    t["id_cliente"] = _asignar_clientes(cfg, rng, t, clientes)
    t = t.sort_values(["fecha_hora", "id_sucursal"]).reset_index(drop=True)
    t.insert(0, "id_venta", np.arange(1, n + 1))

    cod = t["id_sucursal"].map(sucursales.set_index("id_sucursal")["codigo"])
    consecutivo = t.groupby("id_sucursal").cumcount() + 1
    t.insert(1, "folio", cod + "-" + consecutivo.astype(str).str.zfill(7))

    tipo = t["id_cliente"].map(clientes.set_index("id_cliente")["tipo_cliente"]).fillna("publico")
    t["_mayorista"] = (tipo == "mayorista").to_numpy()
    metodo = rng.choice(["efectivo", "tarjeta_debito", "tarjeta_credito", "transferencia"],
                        size=n, p=[0.45, 0.25, 0.20, 0.10])
    metodo_mayorista = rng.choice(["transferencia", "tarjeta_credito", "efectivo"], size=n, p=[0.7, 0.2, 0.1])
    t["metodo_pago"] = np.where(t["_mayorista"], metodo_mayorista, metodo)
    t["estatus"] = np.where(rng.random(n) < cfg.pct_tickets_cancelados, "cancelada", "completada")
    return t


def _asignar_clientes(cfg, rng, t: pd.DataFrame, clientes: pd.DataFrame) -> np.ndarray:
    resultado = np.full(len(t), np.nan)
    con_cliente = rng.random(len(t)) >= cfg.pct_tickets_publico_general
    mes = t["fecha"].dt.to_period("M")
    for (suc, periodo), idx in t[con_cliente].groupby([t["id_sucursal"], mes]).groups.items():
        inicio_mes = periodo.to_timestamp()
        elegibles = clientes[clientes["fecha_registro"] <= inicio_mes]
        if elegibles.empty:
            continue
        # 90 % compra en su sucursal preferida, 10 % en cualquier otra.
        peso = elegibles["_frecuencia"].to_numpy() * np.where(
            elegibles["id_sucursal_preferida"].to_numpy() == suc, 1.0, 0.012)
        resultado[idx] = rng.choice(elegibles["id_cliente"].to_numpy(), size=len(idx), p=peso / peso.sum())
    return resultado


def tabla_precios(cfg: GeneratorConfig, rng: np.random.Generator, productos: pd.DataFrame,
                  anios: list[int]) -> pd.DataFrame:
    """Lista de precios vigente por producto y año (se actualiza cada enero)."""
    base = productos["_precio_base"].to_numpy()
    factores = 1 + cfg.inflacion_anual + rng.uniform(-0.03, 0.04, (len(anios), len(base)))
    factores[0] = 1.0
    acumulado = np.cumprod(factores, axis=0)
    return pd.DataFrame(np.round(acumulado * base, 2).T, index=productos["id_producto"], columns=anios)


def generar_renglones(cfg: GeneratorConfig, rng: np.random.Generator, tickets: pd.DataFrame,
                      productos: pd.DataFrame, sucursales: pd.DataFrame, categorias: pd.DataFrame,
                      precios: pd.DataFrame) -> pd.DataFrame:
    n_ren = 1 + rng.poisson(cfg.renglones_extra_media + 2.0 * tickets["_mayorista"].to_numpy())
    r = pd.DataFrame({
        "id_venta": np.repeat(tickets["id_venta"].to_numpy(), n_ren),
        "id_sucursal": np.repeat(tickets["id_sucursal"].to_numpy(), n_ren),
        "fecha": np.repeat(tickets["fecha"].to_numpy(), n_ren),
        "_mayorista": np.repeat(tickets["_mayorista"].to_numpy(), n_ren),
    })
    region = r["id_sucursal"].map(sucursales.set_index("id_sucursal")["region"])
    _, es_bf = factores_calendario(pd.DatetimeIndex(r["fecha"]))
    # Segmento: mes calendario, o Buen Fin del año (mezcla de productos distinta).
    segmento = r["fecha"].dt.strftime("%Y-%m").where(~es_bf, "BF-" + r["fecha"].dt.year.astype(str))

    afinidad = _afinidad_regional(rng, sucursales, categorias)
    perfil = categorias.set_index("nombre")["perfil"]
    estacional = np.array([PERFILES_ESTACIONALES[perfil[c]] for c in productos["categoria"]])  # (n_prod, 12)
    inicio = pd.Timestamp(cfg.fecha_inicio)
    alta = productos["fecha_alta"].to_numpy()
    baja = productos["_fecha_baja"].fillna(pd.Timestamp("2100-01-01")).to_numpy()
    boost_bf = productos["categoria"].map(CATEGORIAS_BUEN_FIN).fillna(1.0).to_numpy()

    id_producto = np.zeros(len(r), dtype=np.int64)
    for (seg, reg), idx in r.groupby([segmento, region]).groups.items():
        fecha_ref = pd.Timestamp(r.at[idx[0], "fecha"])
        mes_inicio = fecha_ref.to_period("M").to_timestamp().to_datetime64()
        anios = (fecha_ref - inicio).days / 365.25
        w = (productos["_popularidad"].to_numpy()
             * estacional[:, fecha_ref.month - 1]
             * (1 + productos["_tendencia_anual"].to_numpy()) ** anios
             * afinidad.loc[reg, productos["categoria"]].to_numpy())
        if seg.startswith("BF-"):
            w = w * boost_bf
        w[(alta > mes_inicio) | (baja <= mes_inicio)] = 0
        id_producto[idx] = rng.choice(productos["id_producto"].to_numpy(), size=len(idx), p=w / w.sum())
    r["id_producto"] = id_producto

    cant_media = r["id_producto"].map(productos.set_index("id_producto")["_cantidad_media"]).to_numpy()
    cant_media = np.where(r["_mayorista"], cant_media * 4, cant_media)
    r["cantidad"] = 1 + rng.poisson(np.maximum(cant_media - 1, 0.05))

    # Un ticket no repite producto: se consolidan los renglones duplicados.
    r["_es_bf"] = es_bf
    r = (r.groupby(["id_venta", "id_producto"], as_index=False)
          .agg(id_sucursal=("id_sucursal", "first"), fecha=("fecha", "first"),
               _mayorista=("_mayorista", "first"), _es_bf=("_es_bf", "first"), cantidad=("cantidad", "sum")))

    precio = precios.stack()
    r["precio_unitario"] = precio.reindex(pd.MultiIndex.from_arrays(
        [r["id_producto"], r["fecha"].dt.year])).to_numpy()
    cat = r["id_producto"].map(productos.set_index("id_producto")["categoria"])
    desc = np.zeros(len(r))
    desc_bf = r["_es_bf"].to_numpy() & cat.isin(CATEGORIAS_BUEN_FIN).to_numpy()
    desc[desc_bf] = rng.choice([0.10, 0.15, 0.20, 0.25], size=desc_bf.sum())
    desc[r["_mayorista"].to_numpy() & (desc == 0)] = 0.05
    r["descuento_pct"] = desc
    r = r.drop(columns=["_es_bf"])
    return r


def _afinidad_regional(rng, sucursales, categorias) -> pd.DataFrame:
    regiones = sucursales["region"].unique()
    return pd.DataFrame(rng.uniform(0.7, 1.3, (len(regiones), len(categorias))),
                        index=regiones, columns=categorias["nombre"])
