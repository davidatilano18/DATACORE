"""Uso: python -m datacore.generator [--seed 42] [--salida data]"""

import argparse
from dataclasses import replace
from pathlib import Path

from .config import GeneratorConfig
from .run import generar


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera el dataset simulado de NexaTech Solutions.")
    parser.add_argument("--seed", type=int, default=GeneratorConfig.seed)
    parser.add_argument("--salida", type=Path, default=Path("data"))
    parser.add_argument("--productos", type=int, default=GeneratorConfig.n_productos)
    parser.add_argument("--clientes", type=int, default=GeneratorConfig.n_clientes)
    args = parser.parse_args()
    cfg = replace(GeneratorConfig(), seed=args.seed, n_productos=args.productos, n_clientes=args.clientes)
    generar(cfg, args.salida)


if __name__ == "__main__":
    main()
