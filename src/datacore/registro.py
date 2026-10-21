"""Bitácora de eventos de la plataforma: consola y archivo rotativo en logs/."""

import logging
import os
from logging.handlers import RotatingFileHandler

from .db import RAIZ

FORMATO = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def obtener_logger(nombre: str) -> logging.Logger:
    logger = logging.getLogger(f"datacore.{nombre}")
    if logger.handlers:
        return logger
    logger.setLevel(os.getenv("DATACORE_LOG_LEVEL", "INFO"))
    consola = logging.StreamHandler()
    consola.setFormatter(logging.Formatter(FORMATO))
    logger.addHandler(consola)
    carpeta = RAIZ / "logs"
    try:
        carpeta.mkdir(exist_ok=True)
        archivo = RotatingFileHandler(carpeta / f"{nombre}.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
        archivo.setFormatter(logging.Formatter(FORMATO))
        logger.addHandler(archivo)
    except OSError:
        pass  # en contenedores de solo lectura basta con la consola
    logger.propagate = False
    return logger
