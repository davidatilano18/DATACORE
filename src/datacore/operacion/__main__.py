"""Uso:
  python -m datacore.operacion respaldo [--verificar]   respaldo con pg_dump (y prueba de restauración)
  python -m datacore.operacion verificar [ARCHIVO]      restaura un respaldo en una base temporal y compara
  python -m datacore.operacion monitoreo                chequeo de componentes → ops.monitoreo
  python -m datacore.operacion diario [--sin-modelo]    respaldo → ETL → modelo → monitoreo
"""

import argparse
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Operación de DATACORE.")
    sub = parser.add_subparsers(dest="accion", required=True)
    r = sub.add_parser("respaldo")
    r.add_argument("--verificar", action="store_true")
    r.add_argument("--conservar", type=int, default=7)
    v = sub.add_parser("verificar")
    v.add_argument("archivo", type=Path, nargs="?")
    sub.add_parser("monitoreo")
    d = sub.add_parser("diario")
    d.add_argument("--sin-modelo", action="store_true")
    d.add_argument("--sin-verificar", action="store_true")
    args = parser.parse_args()

    if args.accion == "respaldo":
        from .respaldo import respaldar, verificar
        archivo = respaldar(args.conservar)
        return 0 if not args.verificar or verificar(archivo)["ok"] else 1
    if args.accion == "verificar":
        from .respaldo import verificar
        return 0 if verificar(args.archivo)["ok"] else 1
    if args.accion == "monitoreo":
        from .monitoreo import revisar
        return 1 if any(r["estado"] == "falla" for r in revisar()) else 0
    from .diario import ejecutar
    return 0 if ejecutar(con_modelo=not args.sin_modelo, verificar_respaldo=not args.sin_verificar) else 1


if __name__ == "__main__":
    sys.exit(main())
