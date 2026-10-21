"""Respaldos con pg_dump y prueba de recuperación con pg_restore.

La verificación restaura el respaldo en una base temporal y compara el
número de filas de cada tabla de `core` y `ops` contra la base viva: un
respaldo solo cuenta como bueno si se pudo recuperar.
"""

import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from ..db import RAIZ, engine, url, variable
from ..registro import obtener_logger

log = obtener_logger("respaldo")
CARPETA = Path(os.getenv("DATACORE_BACKUP_DIR", RAIZ / "backups"))
BASE_PRUEBA = "datacore_restauracion"


def _binario(nombre: str) -> str:
    """Busca pg_dump/pg_restore en el PATH o en la instalación estándar de Windows."""
    encontrado = shutil.which(nombre)
    if encontrado:
        return encontrado
    for version in ("17", "16", "15"):
        ruta = Path(rf"C:\Program Files\PostgreSQL\{version}\bin\{nombre}.exe")
        if ruta.exists():
            return str(ruta)
    raise FileNotFoundError(f"No se encontró {nombre}; instala el cliente de PostgreSQL")


def _entorno(rol: str) -> tuple[dict, list[str]]:
    u = url(rol)
    env = os.environ | {"PGPASSWORD": u.password}
    return env, ["-h", u.host, "-p", str(u.port), "-U", u.username]


def _conteos(base: str | None = None) -> dict[str, int]:
    eng = engine("admin", base=base or variable("PG_DB"))
    with eng.connect() as c:
        tablas = c.execute(text("SELECT table_schema || '.' || table_name FROM information_schema.tables "
                                "WHERE table_schema IN ('core','ops') AND table_type = 'BASE TABLE' "
                                "AND table_name NOT IN ('respaldos','monitoreo','corridas') ORDER BY 1")).scalars().all()
        conteos = {t: c.execute(text(f"SELECT count(*) FROM {t}")).scalar() for t in tablas}
    eng.dispose()
    return conteos


def respaldar(conservar: int = 7) -> Path:
    CARPETA.mkdir(parents=True, exist_ok=True)
    archivo = CARPETA / f"datacore_{datetime.now():%Y%m%d_%H%M%S}.dump"
    env, conexion = _entorno("app")
    inicio = datetime.now()
    t0 = time.perf_counter()
    try:
        subprocess.run([_binario("pg_dump"), *conexion, "-d", variable("PG_DB"), "-Fc", "-Z", "6",
                        "-n", "core", "-n", "ops", "-n", "kpi", "-f", str(archivo)],
                       env=env, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        _registrar(inicio, archivo, "fallido", detalle=exc.stderr[-2000:])
        log.error("respaldo fallido: %s", exc.stderr.strip())
        raise
    tamano = archivo.stat().st_size
    log.info("respaldo %s (%.1f MB) en %.1fs", archivo.name, tamano / 1e6, time.perf_counter() - t0)
    _registrar(inicio, archivo, "exitoso", tamano=tamano)
    for viejo in sorted(CARPETA.glob("datacore_*.dump"))[:-conservar]:
        viejo.unlink()
        log.info("respaldo antiguo eliminado: %s", viejo.name)
    return archivo


def verificar(archivo: Path | None = None) -> dict:
    """Restaura en una base temporal, compara conteos y la elimina."""
    archivo = archivo or max(CARPETA.glob("datacore_*.dump"))
    admin = engine("admin", base="postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{BASE_PRUEBA}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{BASE_PRUEBA}" TEMPLATE template0 ENCODING \'UTF8\''))
    env, conexion = _entorno("admin")
    t0 = time.perf_counter()
    try:
        subprocess.run([_binario("pg_restore"), *conexion, "-d", BASE_PRUEBA, "--no-owner", "--no-privileges",
                        "-j", "2", str(archivo)], env=env, check=True, capture_output=True, text=True)
        vivos, restaurados = _conteos(), _conteos(BASE_PRUEBA)
    finally:
        with admin.connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{BASE_PRUEBA}" WITH (FORCE)'))
        admin.dispose()
    diferencias = {t: (vivos.get(t), restaurados.get(t)) for t in vivos if vivos.get(t) != restaurados.get(t)}
    ok = not diferencias
    with engine("app").begin() as c:
        c.execute(text("UPDATE ops.respaldos SET verificado = :ok, detalle = :d WHERE archivo = :a"),
                  {"ok": ok, "a": str(archivo), "d": "restauración verificada" if ok else f"diferencias: {diferencias}"})
    log.info("verificación de %s: %s en %.1fs (%d tablas, %s filas)", archivo.name, "OK" if ok else "FALLA",
             time.perf_counter() - t0, len(vivos), f"{sum(vivos.values()):,}")
    return {"archivo": archivo.name, "ok": ok, "tablas": len(vivos), "filas": sum(vivos.values()),
            "diferencias": diferencias}


def _registrar(inicio, archivo, estatus, tamano=None, detalle=None) -> None:
    with engine("app").begin() as c:
        c.execute(text("INSERT INTO ops.respaldos (inicio, fin, archivo, tamano_bytes, estatus, detalle) "
                       "VALUES (:i, now(), :a, :t, :e, :d)"),
                  {"i": inicio, "a": str(archivo), "t": tamano, "e": estatus, "d": detalle})
