"""Uso:
  python -m datacore.ml evaluar  [--horizontes 1 2 4] [--ground-truth data/ground_truth] [--reporte reports/ml]
  python -m datacore.ml publicar [--horizontes 1 2 3 4]

evaluar:  backtest fuera de muestra contra baselines (y contra la demanda real si hay ground truth).
publicar: backtest rápido para métricas e intervalos, entrenamiento con todo el historial,
          pronóstico de las próximas semanas y alertas de inventario en ops.
"""

import argparse
import time
from pathlib import Path

import pandas as pd

from ..db import engine
from . import backtest, publicacion
from .datos import cargar, demanda_real


def main() -> None:
    parser = argparse.ArgumentParser(description="Pronóstico de demanda de DATACORE.")
    parser.add_argument("accion", choices=["evaluar", "publicar"])
    parser.add_argument("--horizontes", type=int, nargs="+")
    parser.add_argument("--ground-truth", type=Path, default=Path("data/ground_truth"))
    parser.add_argument("--reporte", type=Path, default=Path("reports/ml"))
    args = parser.parse_args()
    t0 = time.perf_counter()

    def log(msg):
        print(f"[{time.perf_counter() - t0:6.1f}s] {msg}", flush=True)

    series = cargar(engine("app"))
    log(f"series: {series.unidades.shape[1]:,} pares × {series.unidades.shape[0]} semanas "
        f"({series.unidades.index[0]:%Y-%m-%d} a {series.unidades.index[-1]:%Y-%m-%d})")

    if args.accion == "evaluar":
        perdida = args.ground_truth / "demanda_perdida.parquet"
        real = demanda_real(series, pd.read_parquet(perdida)) if perdida.exists() else None
        r = backtest.ejecutar(series, horizontes=tuple(args.horizontes or (1, 2, 4)), real=real, log=log)
        args.reporte.mkdir(parents=True, exist_ok=True)
        texto = backtest.reporte_markdown(r)
        if 1 in r["dispersion"]:
            from . import evaluacion_alertas
            tabla, casos = evaluacion_alertas.evaluar(series, r["predicciones"], r["dispersion"][1])
            print(tabla.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
            texto += "\n" + evaluacion_alertas.reporte_markdown(tabla, casos)
        (args.reporte / "backtest.md").write_text(texto, encoding="utf-8")
        r["metricas"].to_csv(args.reporte / "backtest_metricas.csv", index=False)
        log(f"reporte → {args.reporte / 'backtest.md'}")
        return

    horizontes = tuple(args.horizontes or (1, 2, 3, 4))
    r = backtest.ejecutar(series, horizontes=horizontes, variantes={"gbm": False}, log=log)
    pron = publicacion.pronosticar(series, horizontes, r["dispersion"], log=log)
    alertas = publicacion.alertas(series, pron)
    id_modelo = publicacion.guardar(engine("app"), backtest.resumen_json(r["metricas"]) | {
        "dispersion_nb": {f"h{h}": round(k, 4) for h, k in r["dispersion"].items()}},
        series.fecha_corte, pron, alertas, "HistGradientBoosting Poisson, directo h=1..4")
    log(f"modelo {id_modelo} publicado: {len(pron):,} pronósticos, alertas: "
        + ", ".join(f"{t} {n:,}" for t, n in alertas["tipo"].value_counts().items()))


if __name__ == "__main__":
    main()
