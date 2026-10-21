"""Pruebas de respaldo, recuperación y monitoreo; se saltan si no hay base local."""

import pytest
from sqlalchemy import text

try:
    from datacore.db import engine

    with engine("app").connect() as _c:
        _OK = _c.execute(text("SELECT to_regclass('ops.respaldos') IS NOT NULL")).scalar()
except Exception:
    _OK = False

pytestmark = pytest.mark.skipif(not _OK, reason="sin base de datos con tablas de operación")

TABLAS_BITACORA = {"ops.respaldos": "id_respaldo", "ops.monitoreo": "id_chequeo"}


@pytest.fixture(autouse=True)
def no_ensuciar_bitacoras():
    """Las pruebas corren contra la base real: borran al final lo que agregaron a las bitácoras
    de operación, para que el dashboard no muestre respaldos o chequeos de prueba."""
    with engine("app").connect() as c:
        antes = {t: c.execute(text(f"SELECT coalesce(max({col}), 0) FROM {t}")).scalar()
                 for t, col in TABLAS_BITACORA.items()}
    yield
    with engine("app").begin() as c:
        for t, col in TABLAS_BITACORA.items():
            c.execute(text(f"DELETE FROM {t} WHERE {col} > :m"), {"m": antes[t]})


def test_respaldo_y_recuperacion(tmp_path, monkeypatch):
    from datacore.operacion import respaldo
    monkeypatch.setattr(respaldo, "CARPETA", tmp_path)
    archivo = respaldo.respaldar(conservar=1)
    assert archivo.exists() and archivo.stat().st_size > 0
    r = respaldo.verificar(archivo)
    assert r["ok"], r["diferencias"]
    assert r["filas"] > 0
    with engine("app").connect() as c:
        verificado = c.execute(text("SELECT verificado FROM ops.respaldos WHERE archivo = :a"),
                               {"a": str(archivo)}).scalar()
    assert verificado is True


def test_retencion_de_respaldos(tmp_path, monkeypatch):
    from datacore.operacion import respaldo
    monkeypatch.setattr(respaldo, "CARPETA", tmp_path)
    for nombre in ("datacore_20000101_000000.dump", "datacore_20000102_000000.dump"):
        (tmp_path / nombre).write_bytes(b"x")
    respaldo.respaldar(conservar=1)
    assert len(list(tmp_path.glob("datacore_*.dump"))) == 1


def test_ops_no_depende_de_core_por_llaves_foraneas():
    """El ETL recarga core con TRUNCATE ... CASCADE: una llave foránea de ops hacia core
    borraría el historial de pronósticos, las alertas atendidas y las anomalías."""
    with engine("app").connect() as c:
        n = c.execute(text("SELECT count(*) FROM pg_constraint WHERE contype = 'f' "
                           "AND connamespace = 'ops'::regnamespace "
                           "AND starts_with(confrelid::regclass::text, 'core.')")).scalar()
    assert n == 0


def test_monitoreo_registra_componentes():
    from datacore.operacion.monitoreo import revisar
    resultados = revisar(api_url="http://127.0.0.1:9")  # puerto sin servicio: la API debe salir en falla
    por_componente = {r["componente"]: r["estado"] for r in resultados}
    assert por_componente["base_de_datos"] == "ok"
    assert por_componente["api"] == "falla"
    assert {"etl", "respaldo", "modelo", "disco"} <= set(por_componente)
