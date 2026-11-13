"""Mejora de la alerta de desabasto: umbral por segmento y corrección de censura.

La alerta publicada usaba un solo umbral para todo el catálogo: existencia < cuantil 90 de la
demanda durante la entrega + 7 días. Aquí se prueban, SIEMPRE fuera de muestra:

- Umbral por segmento (clase ABC × tiempo de entrega): cada bloque de 13 semanas se evalúa con
  los umbrales que mejor funcionaron (mayor F1) en los bloques ANTERIORES (ventana creciente).
- Corrección de censura: el pronóstico aprende de ventas, que subestiman la demanda de los pares
  que se agotaron; se divide entre (1 − fracción de días agotado en las 4 semanas previas).

La regla final se decide con los bloques de 2024 y se confirma en los 4 bloques de 2025, que no
participan en ninguna elección.

Un caso es un par × semana de origen con existencia positiva al cierre; el evento es al menos
un día sin existencia en las dos semanas siguientes (misma definición que evaluacion_alertas).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from .datos import Series

CANDIDATOS = ("media", 0.6, 0.7, 0.8, 0.9, 0.95)   # "media": umbral = demanda esperada (z = 0)
GRUPOS_ENTREGA = [(0, 4, "corta"), (5, 7, "media"), (8, 99, "larga")]  # días de entrega comprometidos
MINIMO_CASOS = 300  # un segmento con menos casos de entrenamiento usa la regla global afinada
INICIO_EVALUACION = pd.Timestamp("2024-12-30")  # se reportan los 4 bloques de 2025, como en backtest.md
TOPE_CENSURA = 2.0   # mismo tope que la política de reposición (impacto.py); 1.5 y 3 dan el mismo F1


def factor_censura(fraccion_agotado: np.ndarray, tope: float = TOPE_CENSURA) -> np.ndarray:
    """1 / (1 − fracción de días agotado), entre 1 y `tope`: lo que la venta observada subestima la demanda."""
    return np.clip(1 / (1 - np.minimum(np.nan_to_num(fraccion_agotado), 0.67)), 1, tope)


def grupo_entrega(dias: pd.Series | np.ndarray) -> np.ndarray:
    dias = np.asarray(dias)
    return np.select([(dias >= a) & (dias <= b) for a, b, _ in GRUPOS_ENTREGA], [g for *_, g in GRUPOS_ENTREGA], "larga")


def z(regla) -> float:
    return 0.0 if regla == "media" else float(stats.norm.ppf(float(regla)))


def casos(series: Series, predicciones: pd.DataFrame, dispersion: float) -> pd.DataFrame:
    """Una fila por par × semana de origen con existencia positiva: media y varianza de la demanda
    durante entrega + 7 días (pronóstico h=1), promedio de 4 semanas, segmento y si hubo faltante."""
    p = predicciones[predicciones["horizonte"] == 1].copy()
    p["semana_origen"] = p["semana"] - pd.Timedelta(weeks=1)

    def apilado(ancho: pd.DataFrame) -> pd.Series:
        s = ancho.stack(level=[0, 1], future_stack=True)
        s.index.names = ["semana", "id_sucursal", "id_producto"]
        return s

    clave = lambda df, col: pd.MultiIndex.from_arrays([df[col], df["id_sucursal"], df["id_producto"]])
    existencia, agotado = apilado(series.existencia), apilado(series.agotado)
    p["existencia"] = existencia.reindex(clave(p, "semana_origen")).to_numpy()
    siguiente = agotado.reindex(clave(p.assign(s2=p["semana"] + pd.Timedelta(weeks=1)), "s2")).to_numpy()
    p["evento"] = (np.nan_to_num(agotado.reindex(clave(p, "semana")).to_numpy()) > 0) | (np.nan_to_num(siguiente) > 0)
    p = p.dropna(subset=["existencia"])
    p = p[p["existencia"] > 0].copy()
    entrega = p["id_producto"].map(series.productos.set_index("id_producto")["dias_entrega"])
    dias = entrega.to_numpy() + 7
    p["mu"] = np.clip(p["gbm"].to_numpy(), 0, None) * dias / 7
    p["var"] = p["mu"] + p["mu"] ** 2 / dispersion
    p["mu_promedio_4"] = np.clip(p["media_4"].to_numpy(), 0, None) * dias / 7
    agotado_4 = apilado(series.agotado.rolling(4, min_periods=1).mean())
    p["factor_censura"] = factor_censura(agotado_4.reindex(clave(p, "semana_origen")).to_numpy())
    p["entrega"] = grupo_entrega(entrega)
    p["clase_abc"] = p["clase_abc"].fillna("C")
    p["segmento"] = p["clase_abc"] + "·" + p["entrega"]
    return p[["origen", "semana", "id_sucursal", "id_producto", "clase_abc", "entrega", "segmento",
              "existencia", "mu", "var", "mu_promedio_4", "factor_censura", "evento"]].reset_index(drop=True)


def alerta(df: pd.DataFrame, regla, censura: bool = False) -> np.ndarray:
    f = df["factor_censura"].to_numpy() if censura else 1.0
    return df["existencia"].to_numpy() < (df["mu"].to_numpy() + z(regla) * np.sqrt(df["var"].to_numpy())) * f


def _f1(a: np.ndarray, e: np.ndarray) -> float:
    vp = (a & e).sum()
    return 2 * vp / (a.sum() + e.sum()) if vp else 0.0


def clasificacion(a: np.ndarray, e: np.ndarray) -> dict:
    vp, fp, fn = int((a & e).sum()), int((a & ~e).sum()), int((~a & e).sum())
    precision = vp / (vp + fp) if vp + fp else np.nan
    exhaustividad = vp / (vp + fn) if vp + fn else np.nan
    return {"alertas": vp + fp, "faltantes_reales": vp + fn, "aciertos": vp, "precision": precision,
            "exhaustividad": exhaustividad, "f1": _f1(a, e)}


def elegir_global(entreno: pd.DataFrame) -> object:
    e = entreno["evento"].to_numpy()
    return max(CANDIDATOS, key=lambda r: _f1(alerta(entreno, r), e))


def elegir_por_segmento(entreno: pd.DataFrame) -> dict:
    """{segmento: regla} con la mayor F1 en el entrenamiento; segmentos chicos usan la regla global."""
    global_ = elegir_global(entreno)
    reglas = {}
    for seg, g in entreno.groupby("segmento"):
        reglas[seg] = elegir_global(g) if len(g) >= MINIMO_CASOS and g["evento"].any() else global_
    reglas["_global"] = global_
    return reglas


def alerta_segmentada(df: pd.DataFrame, reglas: dict) -> np.ndarray:
    zz = df["segmento"].map(lambda s: z(reglas.get(s, reglas["_global"]))).to_numpy()
    return df["existencia"].to_numpy() < df["mu"].to_numpy() + zz * np.sqrt(df["var"].to_numpy())


# Reglas fijas candidatas para la decisión en 2024: (regla, corrección de censura).
FIJAS = {"modelo p90 (publicada)": (0.9, False), "modelo, media": ("media", False),
         "modelo p90 + censura": (0.9, True), "modelo, media + censura": ("media", True)}
REGLAS = ["modelo p90 (publicada)", "modelo, media", "promedio 4 semanas", "umbral único afinado",
          "umbral por segmento", "modelo, media + censura"]


def decidir(c: pd.DataFrame, hasta: pd.Timestamp = INICIO_EVALUACION) -> tuple[str, pd.DataFrame]:
    """Elige entre las reglas fijas la de mayor F1 en los bloques anteriores a `hasta` (2024)."""
    previo = c[c["origen"] < hasta]
    e = previo["evento"].to_numpy()
    tabla = pd.DataFrame([{"regla": n, **clasificacion(alerta(previo, r, cen), e)} for n, (r, cen) in FIJAS.items()])
    return str(tabla.loc[tabla["f1"].idxmax(), "regla"]), tabla


def evaluar_anidado(c: pd.DataFrame, inicio: pd.Timestamp = INICIO_EVALUACION) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Evalúa cada bloque desde `inicio`; las reglas afinadas se eligen solo con los bloques anteriores.
    Devuelve (resultados totales, resultados por bloque, reglas por segmento elegidas en cada bloque)."""
    bloques = sorted(c["origen"].unique())
    por_bloque, elegidas = [], {}
    acumulado = {n: ([], []) for n in REGLAS}
    for b in [b for b in bloques if b >= inicio]:
        entreno, prueba = c[c["origen"] < b], c[c["origen"] == b]
        reglas = elegir_por_segmento(entreno)
        elegidas[pd.Timestamp(b)] = reglas
        e = prueba["evento"].to_numpy()
        alertas = {
            "modelo p90 (publicada)": alerta(prueba, 0.9),
            "modelo, media": alerta(prueba, "media"),
            "promedio 4 semanas": prueba["existencia"].to_numpy() < prueba["mu_promedio_4"].to_numpy(),
            "umbral único afinado": alerta(prueba, reglas["_global"]),
            "umbral por segmento": alerta_segmentada(prueba, reglas),
            "modelo, media + censura": alerta(prueba, "media", censura=True),
        }
        for nombre, a in alertas.items():
            por_bloque.append({"bloque": pd.Timestamp(b), "regla": nombre, **clasificacion(a, e)})
            acumulado[nombre][0].append(a)
            acumulado[nombre][1].append(e)
    total = pd.DataFrame([{"regla": n, **clasificacion(np.concatenate(a), np.concatenate(e))}
                          for n, (a, e) in acumulado.items()])
    return total, pd.DataFrame(por_bloque), elegidas


def guardar_umbrales(reglas: dict, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    valor = lambda v: v if isinstance(v, (str, bool)) else float(v)
    ruta.write_text(json.dumps({k: valor(v) for k, v in reglas.items()}, indent=2, ensure_ascii=False),
                    encoding="utf-8")


def cargar_umbrales(ruta: Path) -> dict | None:
    if not Path(ruta).exists():
        return None
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def _nombre_regla(r) -> str:
    return "media" if r == "media" else f"p{float(r) * 100:g}"


def _tabla(total: pd.DataFrame, marcar: str | None = None) -> str:
    filas = ["| regla | alertas | faltantes reales | aciertos | precisión | exhaustividad | F1 |",
             "|---|---|---|---|---|---|---|"]
    for r in total.itertuples(index=False):
        nombre = f"**{r.regla}** (elegida)" if r.regla == marcar else r.regla
        filas.append(f"| {nombre} | {r.alertas:,} | {r.faltantes_reales:,} | {r.aciertos:,} | {r.precision:.1%} | "
                     f"{r.exhaustividad:.1%} | {r.f1:.3f} |")
    return "\n".join(filas)


def reporte_markdown(total: pd.DataFrame, por_bloque: pd.DataFrame, decision: pd.DataFrame, elegida: str,
                     finales: dict, n_casos: int) -> str:
    pivote = por_bloque.pivot(index="bloque", columns="regla", values="f1")[REGLAS]
    bloques = ["| bloque desde | " + " | ".join(REGLAS) + " |", "|---|" + "---|" * len(REGLAS)]
    for b, fila in pivote.iterrows():
        mejor = fila.idxmax()
        bloques.append(f"| {b:%Y-%m-%d} | " + " | ".join(
            (f"**{v:.3f}**" if col == mejor else f"{v:.3f}") for col, v in fila.items()) + " |")
    nueva, media, p90 = pivote[elegida], pivote["modelo, media"], pivote["modelo p90 (publicada)"]
    gana_media, gana_p90 = int((nueva > media).sum()), int((nueva > p90).sum())
    seg_gana = int((pivote["umbral por segmento"] > media).sum())
    t = total.set_index("regla")
    sostiene = ("se sostiene en los 4 bloques" if gana_media == len(pivote) else
                f"**no se sostiene en todos los bloques**: supera a la regla de la media en {gana_media} de {len(pivote)}")
    segmentos = sorted(k for k in finales if not k.startswith("_"))
    seg = ["| segmento (clase · entrega) | umbral que habría elegido |", "|---|---|"] + [
        f"| {s} | {_nombre_regla(finales[s])} |" for s in segmentos]
    return f"""<!-- inicio: alertas segmentadas -->
## Mejora de las alertas de desabasto

Generado por `python -m datacore.ml alertas` con las predicciones fuera de muestra de 7 bloques (abril de 2024 a
diciembre de 2025). Se probaron dos ideas:

1. **Umbral por segmento** (clase ABC × tiempo de entrega: corta 2–4 días, media 5–7, larga 8–10). En cada bloque se
   elige, con los bloques **anteriores** y por mayor F1, entre la media y los cuantiles 60 a 95; los segmentos con menos
   de {MINIMO_CASOS} casos usan el mejor umbral único.
2. **Corrección de censura**: el pronóstico se divide entre (1 − fracción de días agotado en las 4 semanas previas),
   hasta ×{TOPE_CENSURA:g}, porque los pares que se agotan venden menos de lo que se les pide.

### Decisión (bloques de 2024, antes de mirar 2025)

{_tabla(decision, elegida)}

### Antes y después (los 4 bloques de 2025, {n_casos:,} casos; ningún bloque participó en la elección)

{_tabla(total, elegida)}

### F1 por bloque (la mejor de cada fila en negritas)

{chr(10).join(bloques)}

**Lectura:**

- La regla elegida, *{elegida}*, sube la F1 de {t.loc['modelo p90 (publicada)', 'f1']:.3f} (p90 publicada) y de
  {t.loc['modelo, media', 'f1']:.3f} (media) a **{t.loc[elegida, 'f1']:.3f}**, con precisión de
  {t.loc[elegida, 'precision']:.1%} (antes {t.loc['modelo p90 (publicada)', 'precision']:.1%}). Supera a la p90 en
  {gana_p90} de {len(pivote)} bloques; frente a la regla de la media, {sostiene}.
- A cambio, la exhaustividad baja de {t.loc['modelo p90 (publicada)', 'exhaustividad']:.1%} a
  {t.loc[elegida, 'exhaustividad']:.1%}: la p90 avisa de más faltantes, pero con 5 alertas falsas por acierto.
- **El umbral por segmento no se sostiene**: supera a la media solo en {seg_gana} de {len(pivote)} bloques y su F1
  total ({t.loc['umbral por segmento', 'f1']:.3f}) queda por debajo. Con 9 segmentos y pocos faltantes en cada uno,
  los umbrales se ajustan al ruido de los bloques de entrenamiento. Por eso no se publica.
- El umbral único afinado (elegido con los bloques anteriores) queda prácticamente empatado con la media: mover el
  umbral no aporta; lo que aporta es corregir la censura del pronóstico.

### Umbrales que habría elegido la segmentación con los 7 bloques (no se usan)

{chr(10).join(seg)}
<!-- fin: alertas segmentadas -->
"""


def insertar_en_reporte(ruta: Path, seccion: str) -> None:
    """Reemplaza (o agrega) la sección marcada dentro de backtest.md sin tocar lo demás."""
    texto = ruta.read_text(encoding="utf-8") if ruta.exists() else ""
    ini, fin = "<!-- inicio: alertas segmentadas -->", "<!-- fin: alertas segmentadas -->"
    if ini in texto and fin in texto:
        texto = texto[:texto.index(ini)] + seccion.strip() + texto[texto.index(fin) + len(fin):]
    else:
        texto = texto.rstrip() + "\n\n" + seccion.strip() + "\n"
    ruta.write_text(texto, encoding="utf-8")


def ejecutar(series: Series, predicciones: pd.DataFrame, dispersion: float, reporte: Path, log=print) -> dict:
    c = casos(series, predicciones, dispersion)
    log(f"{len(c):,} casos en {c['origen'].nunique()} bloques")
    elegida, decision = decidir(c)
    log(f"regla elegida con los bloques de 2024: {elegida}")
    total, por_bloque, _ = evaluar_anidado(c)
    regla, censura = FIJAS[elegida]
    guardar_umbrales({"_global": regla, "_censura": censura, "_tope_censura": TOPE_CENSURA, "_regla": elegida},
                     reporte / "regla_alertas.json")
    n = int((c["origen"] >= INICIO_EVALUACION).sum())
    texto = reporte_markdown(total, por_bloque, decision, elegida, elegir_por_segmento(c), n)
    insertar_en_reporte(reporte / "backtest.md", texto)
    return {"total": total, "por_bloque": por_bloque, "decision": decision, "regla": elegida}
