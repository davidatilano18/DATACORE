"""Uso: python -m datacore.etl [--raw data/raw] [--sin-carga] [--evaluar data/ground_truth] [--reporte reports/etl]"""

import argparse
from pathlib import Path

from .pipeline import ejecutar


def main() -> None:
    parser = argparse.ArgumentParser(description="ETL de DATACORE: archivos de las áreas → PostgreSQL.")
    parser.add_argument("--raw", type=Path, default=Path("data/raw"))
    parser.add_argument("--sin-carga", action="store_true", help="solo extraer y transformar")
    parser.add_argument("--evaluar", type=Path, nargs="?", const=Path("data/ground_truth"),
                        help="comparar contra la verdad de referencia")
    parser.add_argument("--reporte", type=Path, default=Path("reports/etl"))
    args = parser.parse_args()
    ejecutar(args.raw, cargar_bd=not args.sin_carga, ground_truth=args.evaluar,
             reporte=args.reporte if args.evaluar else None)


if __name__ == "__main__":
    main()
