"""Conexión a PostgreSQL a partir de las variables de `.env`."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL

RAIZ = Path(__file__).resolve().parents[2]
load_dotenv(RAIZ / ".env")

ROLES = {
    "admin": ("PG_ADMIN_USER", "PG_ADMIN_PASSWORD"),
    "app": ("PG_APP_USER", "PG_APP_PASSWORD"),
    "lector": ("PG_LECTOR_USER", "PG_LECTOR_PASSWORD"),
}


def variable(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise RuntimeError(f"Falta {nombre} en .env (ver .env.example)")
    return valor


def url(rol: str = "app", base: str | None = None) -> URL:
    usuario, clave = ROLES[rol]
    return URL.create("postgresql+psycopg", username=variable(usuario), password=variable(clave),
                      host=os.getenv("PG_HOST", "localhost"), port=int(os.getenv("PG_PORT", "5432")),
                      database=base or variable("PG_DB"))


def engine(rol: str = "app", base: str | None = None, **kwargs) -> Engine:
    return create_engine(url(rol, base), **kwargs)
