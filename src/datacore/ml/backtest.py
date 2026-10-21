"""Evaluación fuera de muestra: se entrena con el pasado y se mide en las últimas semanas.

El periodo de prueba (por defecto las últimas 13 semanas: Buen Fin y Navidad
incluidos) nunca participa en el entrenamiento. Si se da la demanda real de
la simulación, se mide además contra ella: la venta observada está censurada
por los faltantes, la demanda real no.
"""

import time

import pandas as pd

from . import caracteristicas as car
from .datos import Series, clases_abc
from .modelos import dispersion_binomial_negativa, entrenar, metricas, predecir_baselines


def _tabla_metricas(df: pd.DataFrame, columnas: list[str], objetivo: str) -> pd.DataFrame:
    filas = []
    for col in columnas:
        filas.append({"metodo": col, "segmento": "todos", **metricas(df[objetivo], df[col])})
        for clase, g in df.groupby("clase_abc"):
            filas.append({"metodo": col, "segmento": f"clase {clase}", **metricas(g[objetivo], g[col])})
        # Agregado por producto y semana (todas las sucursales): lo que ve compras al negociar con el proveedor.
        agregado = df.groupby(["semana", "id_producto"])[[objetivo, col]].sum()
        filas.append({"metodo": col, "segmento": "producto-semana", **metricas(agregado[objetivo], agregado[col])})
    return pd.DataFrame(filas)


VARIANTES = {"gbm": False, "gbm_sin_censura": True}  # nombre → excluir semanas censuradas al entrenar


def ejecutar(series: Series, horizontes=(1, 2, 4), semanas_prueba: int = 13,
             real: pd.DataFrame | None = None, variantes: dict[str, bool] = VARIANTES, log=print) -> dict:
    semanas = series.unidades.index
    inicio_prueba = semanas[-semanas_prueba]
    abc = clases_abc(series, inicio_prueba)
    resultados, predicciones, dispersion = [], [], {}
    for h in horizontes:
        t0 = time.perf_counter()
        df = car.construir(series, h)
        df["agotado_objetivo"] = car._apilar(series.agotado, "a").reindex(
            pd.MultiIndex.from_frame(df[["semana", "id_sucursal", "id_producto"]])).to_numpy()
        df["clase_abc"] = pd.MultiIndex.from_frame(df[["id_sucursal", "id_producto"]]).map(abc)
        if real is not None:
            df["y_real"] = car._apilar(real, "r").reindex(
                pd.MultiIndex.from_frame(df[["semana", "id_sucursal", "id_producto"]])).to_numpy()
        entreno, prueba = df[df["semana"] < inicio_prueba], df[df["semana"] >= inicio_prueba].copy()

        for nombre, excluir in variantes.items():
            modelo = entrenar(entreno, excluir_censuradas=excluir)
            prueba[nombre] = modelo.predict(prueba[car.COLUMNAS_MODELO])
        base = predecir_baselines(prueba)
        prueba[base.columns] = base
        columnas = [*variantes, *base.columns]
        dispersion[h] = dispersion_binomial_negativa(prueba["y"], prueba["gbm"])

        for objetivo in ["y"] + (["y_real"] if real is not None else []):
            t = _tabla_metricas(prueba, columnas, objetivo)
            t.insert(0, "contra", "ventas observadas" if objetivo == "y" else "demanda real")
            t.insert(0, "horizonte", h)
            resultados.append(t)
        predicciones.append(prueba.assign(horizonte=h))
        log(f"horizonte {h}: {len(entreno):,} filas de entrenamiento, {len(prueba):,} de prueba "
            f"({time.perf_counter() - t0:.0f}s)")
    return {"metricas": pd.concat(resultados, ignore_index=True),
            "predicciones": pd.concat(predicciones, ignore_index=True),
            "dispersion": dispersion, "inicio_prueba": inicio_prueba}


def resumen_json(metricas: pd.DataFrame) -> dict:
    """Métricas clave por horizonte para guardar junto al modelo en ops.modelos."""
    m = metricas[metricas["contra"] == "ventas observadas"]
    out = {}
    for h, g in m.groupby("horizonte"):
        tabla = g.set_index(["metodo", "segmento"])
        out[f"h{h}"] = {
            "wape_par": round(tabla.loc[("gbm", "todos"), "wape"], 4),
            "wape_producto_semana": round(tabla.loc[("gbm", "producto-semana"), "wape"], 4),
            "sesgo": round(tabla.loc[("gbm", "todos"), "sesgo"], 4),
            "wape_media_movil_8": round(tabla.loc[("media_movil_8", "todos"), "wape"], 4),
        }
    return out


def reporte_markdown(r: dict) -> str:
    m = r["metricas"]
    partes = ["# Evaluación del modelo de demanda semanal",
              f"Backtest fuera de muestra: entrenamiento con semanas anteriores a **{r['inicio_prueba']:%Y-%m-%d}**; "
              "prueba en las 13 semanas siguientes (incluye Buen Fin y Navidad). Generado por "
              "`python -m datacore.ml evaluar`.",
              "**WAPE** = Σ|real − pronóstico| / Σ real (menor es mejor). **Sesgo** = Σ(pronóstico − real) / Σ real "
              "(negativo = subestima). *par* = sucursal-producto-semana; *producto-semana* = suma de sucursales."]
    for contra, g in m.groupby("contra", sort=False):
        partes.append(f"## Contra {contra}")
        if contra == "demanda real":
            partes.append("La demanda real (ventas + demanda no surtida) solo existe en la simulación. Mide si el "
                          "modelo recupera la demanda que los faltantes ocultan.")
        for segmento in ("todos", "producto-semana", "clase A", "clase B", "clase C"):
            t = g[g["segmento"] == segmento].pivot_table(index="metodo", columns="horizonte", values=["wape", "sesgo"])
            if t.empty:
                continue
            t.columns = [f"{met} h={h}" for met, h in t.columns]
            t = t.sort_values(t.columns[-1] if "wape" in t.columns[-1] else t.columns[0])
            nombre = "par (todos)" if segmento == "todos" else segmento
            filas = ["| método | " + " | ".join(t.columns) + " |", "|---|" + "---|" * len(t.columns)]
            filas += [f"| {i} | " + " | ".join(f"{v:.1%}" for v in fila) + " |" for i, fila in t.iterrows()]
            partes.append(f"### {nombre}\n\n" + "\n".join(filas))
    disp = ", ".join(f"h={h}: k={k:.2f}" for h, k in r["dispersion"].items())
    partes.append(f"## Intervalos\n\nDispersión binomial negativa estimada en la prueba (Var = μ + μ²/k): {disp}.")
    return "\n\n".join(partes) + "\n"
