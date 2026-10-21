"""Detección causal de anomalías diarias; la verdad de referencia solo evalúa."""

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import text

COLUMNAS = ["fecha", "id_sucursal", "metrica", "tipo", "valor", "esperado", "z"]


def festivos(fechas):
    """Exclusión explícita de eventos del calendario de docs/04 y del simulador."""
    fechas = pd.DatetimeIndex(fechas)
    especiales = {"01-01", "01-05", "01-06", "04-29", "04-30", "05-08", "05-09",
                  "05-10", "09-16", "12-31"} | {f"12-{d}" for d in range(18, 26)}
    mascara = fechas.strftime("%m-%d").isin(especiales)
    for anio in fechas.year.unique():
        lunes = pd.date_range(f"{anio}-11-01", f"{anio}-11-30", freq="W-MON")[2]
        mascara |= fechas.isin(pd.date_range(lunes-pd.Timedelta(days=3), lunes))
    return mascara


def cargar(eng):
    with eng.connect() as c:
        diaria = pd.read_sql("SELECT fecha, id_sucursal, ingreso, tickets FROM kpi.ventas_diarias_sucursal", c,
                             parse_dates=["fecha"])
        sucursales = pd.read_sql("SELECT id_sucursal, fecha_apertura FROM core.sucursales", c,
                                 parse_dates=["fecha_apertura"])
    return diaria, sucursales


def detectar(diaria, sucursales, umbral=3.5):
    """Mediana de 8 semanas por día, mínimo 6; tendencia y MAD solo pasados.

    Completa días sin tickets con cero desde la apertura y dentro del periodo
    observado. El piso de escala evita infinitos cuando MAD es cero.
    """
    if umbral <= 0 or not np.isfinite(umbral):
        raise ValueError("El umbral debe ser positivo y finito")
    if diaria.empty:
        return pd.DataFrame(columns=COLUMNAS)
    diaria = diaria.copy()
    diaria["fecha"] = pd.to_datetime(diaria.fecha)
    inicio, fin = diaria.fecha.min(), diaria.fecha.max()
    resultado = []
    for suc in sucursales.itertuples():
        fechas = pd.date_range(max(inicio, pd.Timestamp(suc.fecha_apertura)), fin)
        marco = diaria[diaria.id_sucursal == suc.id_sucursal].set_index("fecha")
        marco = marco.reindex(fechas)[["ingreso", "tickets"]].fillna(0).astype(float)
        especial = festivos(fechas)
        for metrica in marco:
            valores = marco[metrica].to_numpy()
            limpios = pd.Series(valores, index=fechas).mask(especial)
            base = pd.Series(np.nan, index=fechas)
            for dia in range(7):
                seleccion = fechas.dayofweek == dia
                base.loc[seleccion] = limpios.loc[seleccion].shift(1).rolling(8, min_periods=6).median()
            razon = limpios / base.replace(0, np.nan)
            tendencia = razon.shift(1).rolling(28, min_periods=14).median().clip(0.5, 2).fillna(1)
            esperado = base * tendencia
            if metrica == "tickets":
                # Los tickets son conteos: se usa la cola de Poisson (p medio) y se expresa como z normal.
                # Es más sensible que el MAD, que mezcla el ruido de los tickets grandes de mayoristas.
                x, mu = marco[metrica], esperado.clip(lower=1e-6)
                p = stats.poisson.cdf(x - 1, mu) + 0.5 * stats.poisson.pmf(x, mu)
                z = pd.Series(stats.norm.ppf(np.clip(p, 1e-12, 1 - 1e-12)), index=fechas).where(esperado.notna())
            else:
                residuo = limpios - esperado
                # MAD de residuos históricos alrededor de su mediana; no usa el día evaluado.
                centro = residuo.shift(1).rolling(56, min_periods=21).median()
                mad = residuo.shift(1).rolling(56, min_periods=21).apply(
                    lambda x: np.nanmedian(np.abs(x-np.nanmedian(x))), raw=True)
                escala = (1.4826 * mad).clip(lower=1e-6)
                escala = np.maximum(escala, esperado.abs() * 0.05)
                z = (marco[metrica] - esperado - centro) / escala
            for fecha in fechas[(z.abs() > umbral).fillna(False).to_numpy() & ~especial]:
                resultado.append([fecha, suc.id_sucursal, metrica, "caida" if z.loc[fecha] < 0 else "pico",
                                  round(marco.loc[fecha, metrica], 2), round(esperado.loc[fecha], 2), z.loc[fecha]])
    return pd.DataFrame(resultado, columns=COLUMNAS)


def evaluar(detectadas, fallas):
    """Unidad: sucursal-día, unión de caídas de ambas métricas sin duplicar.

    Por horas, la precisión usa todas las falsas alarmas (no tienen horas
    atribuibles); TP de otros estratos no se consideran falsos positivos.
    Se conservan todas las fallas, incluso calentamiento y festivos.
    """
    def claves(marco):
        return set(zip(marco.id_sucursal, pd.to_datetime(marco.fecha).dt.normalize()))
    pred = claves(detectadas[detectadas.tipo == "caida"])
    verdad = claves(fallas)
    fp = len(pred - verdad)
    filas = []
    for grupo, subset in [("total", fallas)] + [(f"{a}-{b} h", fallas[fallas.horas_fuera.between(a, b)])
                                               for a, b in [(2, 3), (4, 5), (6, 8)]]:
        reales = claves(subset)
        tp = len(pred & reales)
        precision = tp / (tp+fp) if tp+fp else 0.0
        exhaustividad = tp / len(reales) if reales else 0.0
        filas.append(dict(grupo=grupo, verdaderos_positivos=tp, falsos_positivos=fp,
                          fallas=len(reales), precision=precision, exhaustividad=exhaustividad,
                          f1=2*precision*exhaustividad/(precision+exhaustividad) if precision+exhaustividad else 0.0))
    return pd.DataFrame(filas)


def ejecutar(eng, ground_truth, reporte):
    diaria, sucursales = cargar(eng)
    # Umbrales en unidades z: 2.33, 2.58 y 3.09 equivalen a colas de Poisson de 1 %, 0.5 % y 0.1 % en tickets.
    candidatos = {u: detectar(diaria, sucursales, u) for u in (2.33, 2.58, 3.09)}
    archivo = ground_truth / "fallas_sistema.parquet"
    umbral = 2.58
    texto = "# Detección de anomalías\n\n"
    if archivo.exists():
        fallas = pd.read_parquet(archivo)
        # Se evalúan las caídas de tickets: el ingreso diario es demasiado ruidoso por los mayoristas.
        resultados = pd.concat([evaluar(d[d.metrica == "tickets"], fallas).assign(umbral=u)
                                for u, d in candidatos.items()], ignore_index=True)
        total = resultados[resultados.grupo == "total"]
        umbral = float(total.sort_values(["f1", "umbral"], ascending=[False, False]).iloc[0].umbral)
        texto += "Selección exploratoria por mayor F1 en el historial completo; empate: umbral mayor. No es una estimación fuera de muestra.\n\n"
        texto += "| " + " | ".join(resultados.columns) + " |\n|" + "---|"*len(resultados.columns) + "\n"
        for fila in resultados.itertuples(index=False, name=None):
            texto += "| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in fila) + " |\n"
    else:
        texto += "Sin ground truth: se usa el umbral predeterminado 2.58 (cola de Poisson de 0.5 %).\n"
    detectadas = candidatos[umbral]
    with eng.begin() as c:
        c.execute(text("LOCK TABLE ops.anomalias IN EXCLUSIVE MODE"))
        c.execute(text("DELETE FROM ops.anomalias"))
        if not detectadas.empty:
            detectadas.to_sql("anomalias", c, schema="ops", if_exists="append", index=False)
    texto += f"\nUmbral elegido: {umbral}. Anomalías publicadas: {len(detectadas)}.\n"
    texto += "\nSe excluyen eventos festivos del calendario y de la referencia; pueden ocultar fallas reales. Evaluación por sucursal-día, unión de métricas. Por horas se reutilizan las falsas alarmas globales; las precisiones de estratos no son aditivas. El denominador incluye fallas en festivos y calentamiento.\n"
    reporte.mkdir(parents=True, exist_ok=True)
    (reporte / "anomalias.md").write_text(texto, encoding="utf-8")
    print(texto)
