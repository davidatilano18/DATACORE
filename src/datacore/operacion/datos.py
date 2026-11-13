"""Datos de entrada del ETL en un servidor nuevo.

En desarrollo, `data/` se genera a mano y no se versiona. En un contenedor (`.dockerignore` excluye
`data/`) no existe al arrancar: antes del ETL se generan los datos simulados de NexaTech con la
configuración por omisión (semilla 42, el mismo conjunto de siempre). Con `data/` en un disco
persistente, esto ocurre una sola vez.
"""

from pathlib import Path

from ..db import RAIZ
from ..registro import obtener_logger

log = obtener_logger("diario")


def hay_datos(raiz: Path = RAIZ) -> bool:
    raw = Path(raiz) / "data" / "raw"
    return raw.is_dir() and any(raw.iterdir())


def asegurar_datos_simulados(raiz: Path = RAIZ, generar=None) -> bool:
    """Genera `data/` si `data/raw` no existe o está vacío. Devuelve True si generó."""
    if hay_datos(raiz):
        return False
    if generar is None:
        from ..generator.config import GeneratorConfig
        from ..generator.run import generar as generar_datos
        generar = lambda salida: generar_datos(GeneratorConfig(), salida)  # noqa: E731
    salida = Path(raiz) / "data"
    log.info("no hay archivos en %s: se generan los datos simulados (semilla 42)", salida / "raw")
    generar(salida)
    return True
