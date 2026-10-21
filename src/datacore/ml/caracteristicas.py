"""Variables para pronosticar la semana t con información disponible hasta t − h.

Todo rezago o ventana se calcula sobre la serie desplazada h semanas, de modo
que el modelo de horizonte h nunca ve datos posteriores a su fecha de origen.
Las variables de calendario sí son del periodo objetivo: el calendario se
conoce de antemano.
"""

import numpy as np
import pandas as pd

from .datos import Series

TAMANOS = {"pequena": 0, "mediana": 1, "grande": 2}


def _buen_fin(anio: int) -> pd.DatetimeIndex:
    lunes = pd.date_range(f"{anio}-11-01", f"{anio}-11-30", freq="W-MON")[2]
    return pd.date_range(lunes - pd.Timedelta(days=3), lunes)


def calendario(semanas: pd.DatetimeIndex) -> pd.DataFrame:
    filas = []
    for s in semanas:
        dias = pd.date_range(s, periods=7)
        md = set(dias.strftime("%m-%d"))
        filas.append({
            "semana_anio": s.isocalendar().week,
            "mes": s.month,
            "buen_fin": int(dias.isin(_buen_fin(s.year)).any() or dias.isin(_buen_fin(s.year + 1)).any()),
            "navidad": int(bool(md & {f"12-{d}" for d in range(18, 25)})),
            "fin_de_anio": int(bool(md & {"12-25", "12-31", "01-01"})),
            "reyes": int(bool(md & {"01-05", "01-06"})),
            "dia_madres": int("05-10" in md),
            "dia_nino": int("04-30" in md),
            "regreso_clases": int(s.month == 8 or (s.month == 7 and s.day >= 25)),
            "quincenas": int(sum(d.day in (1, 15, 16) or d.is_month_end for d in dias)),
        })
    return pd.DataFrame(filas, index=semanas)


def sba(unidades: pd.DataFrame, alfa: float = 0.1) -> pd.DataFrame:
    """Pronóstico Syntetos-Boylan para demanda intermitente, actualizado al cierre de cada semana."""
    y = unidades.to_numpy()
    tamano = np.full(y.shape[1], np.nan)
    intervalo = np.full(y.shape[1], np.nan)
    desde_ultima = np.ones(y.shape[1])
    salida = np.full(y.shape, np.nan)
    for t in range(y.shape[0]):
        fila = y[t]
        vende = fila > 0
        nuevo = vende & np.isnan(tamano)
        tamano[nuevo], intervalo[nuevo] = fila[nuevo], desde_ultima[nuevo]
        act = vende & ~nuevo
        tamano[act] += alfa * (fila[act] - tamano[act])
        intervalo[act] += alfa * (desde_ultima[act] - intervalo[act])
        desde_ultima = np.where(vende, 1, desde_ultima + ~np.isnan(fila))
        pron = (1 - alfa / 2) * tamano / intervalo
        salida[t] = np.where(np.isnan(fila), np.nan, np.nan_to_num(pron, nan=0.0))
    return pd.DataFrame(salida, index=unidades.index, columns=unidades.columns)


def _apilar(ancho: pd.DataFrame, nombre: str) -> pd.Series:
    s = ancho.stack(level=[0, 1], future_stack=True)
    s.index.names = ["semana", "id_sucursal", "id_producto"]
    return s.rename(nombre)


def construir(series: Series, h: int, semanas_objetivo: pd.DatetimeIndex | None = None,
              objetivo: pd.DataFrame | None = None) -> pd.DataFrame:
    """Tabla larga con una fila por (semana objetivo, sucursal, producto).

    `objetivo` permite reemplazar la variable a predecir (p. ej. la demanda real
    de la simulación); por defecto son las unidades vendidas. Para pronosticar
    semanas futuras se extiende el índice con filas vacías.
    """
    y = series.unidades
    if semanas_objetivo is not None and semanas_objetivo.max() > y.index.max():
        extra = pd.date_range(y.index.max() + pd.Timedelta(weeks=1), semanas_objetivo.max(), freq="W-MON")
        y = pd.concat([y, pd.DataFrame(np.nan, index=extra, columns=y.columns)])
    base = y.shift(h)
    vars_ancho = {
        "lag_1": base,
        "lag_2": y.shift(h + 1),
        "lag_3": y.shift(h + 2),
        "lag_4": y.shift(h + 3),
        "lag_52": y.shift(52) if h <= 52 else base * np.nan,
        "lag_52_suave": y.shift(51).rolling(3, min_periods=1).mean(),
        "media_4": base.rolling(4, min_periods=1).mean(),
        "media_8": base.rolling(8, min_periods=1).mean(),
        "media_13": base.rolling(13, min_periods=1).mean(),
        "media_26": base.rolling(26, min_periods=1).mean(),
        "desv_8": base.rolling(8, min_periods=2).std(),
        "max_13": base.rolling(13, min_periods=1).max(),
        "frac_cero_13": (base == 0).astype(float).where(base.notna()).rolling(13, min_periods=1).mean(),
        "ewm_03": base.ewm(alpha=0.3, ignore_na=True).mean(),
        "media_historica": base.expanding(min_periods=1).mean(),
        "sba": sba(y).shift(h),
        "agotado_lag": series.agotado.reindex(y.index).shift(h),
        "agotado_4": series.agotado.reindex(y.index).shift(h).rolling(4, min_periods=1).mean(),
        "precio": series.precio.reindex(y.index).ffill().shift(h),
    }
    # Señal del producto en todas las sucursales (menos ruidosa que la del par).
    por_producto = base.T.groupby(level="id_producto").mean().T
    vars_ancho["producto_media_4"] = por_producto.rolling(4, min_periods=1).mean() \
        .reindex(columns=y.columns, level="id_producto")
    # Índice estacional de la categoría: semana equivalente del año pasado contra su vecindad (±12 semanas).
    cat_de = series.productos.set_index("id_producto")["id_categoria"]
    por_cat = y.T.groupby(y.columns.get_level_values("id_producto").map(cat_de)).sum().T
    estacional = por_cat.shift(52) / por_cat.shift(40).rolling(25, min_periods=13).mean()
    vars_ancho["cat_estacional"] = estacional[[cat_de[p] for p in y.columns.get_level_values("id_producto")]] \
        .set_axis(y.columns, axis=1)

    objetivo = y if objetivo is None else objetivo.reindex(index=y.index, columns=y.columns)
    vivo = pd.DataFrame(y.index.to_numpy()[:, None] >= series.inicio_par.to_numpy()[None, :],
                        index=y.index, columns=y.columns)
    df = pd.concat([_apilar(objetivo.where(vivo), "y"), _apilar(vivo, "_vivo")]
                   + [_apilar(v, k) for k, v in vars_ancho.items()], axis=1)
    if semanas_objetivo is None:
        # Entrenamiento y evaluación: semanas observadas con al menos una semana previa de historia.
        df = df[df["y"].notna() & df["lag_1"].notna()]
    else:
        # Pronóstico: semanas pedidas, aunque aún no tengan valor observado.
        df = df[df.index.get_level_values("semana").isin(semanas_objetivo) & df["_vivo"].astype(bool)]
    df = df.drop(columns="_vivo")

    df = df.reset_index()
    df = df.join(calendario(pd.DatetimeIndex(df["semana"].unique())), on="semana")
    prod = series.productos.set_index("id_producto")
    suc = series.sucursales.set_index("id_sucursal")
    df["id_categoria"] = df["id_producto"].map(prod["id_categoria"])
    df["dias_entrega"] = df["id_producto"].map(prod["dias_entrega"])
    df["tamano"] = df["id_sucursal"].map(suc["tamano"]).map(TAMANOS)
    df["region"] = df["id_sucursal"].map(suc["region"])
    inicio = pd.MultiIndex.from_frame(df[["id_sucursal", "id_producto"]]).map(series.inicio_par)
    df["semanas_de_vida"] = ((df["semana"] - pd.DatetimeIndex(inicio)).dt.days // 7).to_numpy()
    for col in ("id_sucursal", "id_categoria", "region"):
        df[col + "_cat"] = df[col].astype("category")
    return df


COLUMNAS_MODELO = [
    "lag_1", "lag_2", "lag_3", "lag_4", "lag_52", "lag_52_suave", "media_4", "media_8", "media_13", "media_26",
    "desv_8", "max_13", "frac_cero_13", "ewm_03", "media_historica", "sba", "agotado_lag", "agotado_4", "precio",
    "producto_media_4", "cat_estacional", "semana_anio", "mes", "buen_fin", "navidad", "fin_de_anio", "reyes",
    "dia_madres", "dia_nino", "regreso_clases", "quincenas", "dias_entrega", "tamano", "semanas_de_vida",
    "id_sucursal_cat", "id_categoria_cat", "region_cat",
]
