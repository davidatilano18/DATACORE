"""Integración de indicadores con la base local; no modifica datos."""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from datacore.db import engine


@pytest.fixture(scope="module")
def conexion():
    motor = None
    try:
        motor = engine("lector", connect_args={"connect_timeout": 3})
        c = motor.connect()
    except (SQLAlchemyError, RuntimeError):
        if motor is not None:
            motor.dispose()
        pytest.skip("PostgreSQL local no disponible")
    try:
        if not c.execute(text("SELECT to_regnamespace('kpi')")).scalar():
            pytest.skip("El esquema kpi no existe")
        yield c
    finally:
        c.close()
        motor.dispose()


def test_ingreso_diario(conexion):
    assert conexion.execute(text("SELECT coalesce(sum(ingreso), 0) FROM "
                                 "kpi.ventas_diarias_sucursal")).scalar_one() == conexion.execute(text(
        "SELECT coalesce(sum(total), 0) FROM core.ventas WHERE estatus = 'completada'"
    )).scalar_one()


def test_unidades_semanales(conexion):
    assert conexion.execute(text("SELECT coalesce(sum(unidades), 0) FROM "
                                 "kpi.ventas_semanales_producto")).scalar_one() == conexion.execute(text(
        "SELECT coalesce(sum(d.cantidad), 0) FROM core.detalle_venta d "
        "JOIN core.ventas v USING (id_venta) WHERE v.estatus = 'completada'"
    )).scalar_one()


def test_clases_abc(conexion):
    assert conexion.execute(text("SELECT count(*) FROM kpi.abc_productos "
                                 "WHERE clase IS NULL OR clase NOT IN ('A', 'B', 'C')")).scalar_one() == 0
    assert conexion.execute(text("SELECT count(*) FROM kpi.abc_productos WHERE clase <> "
        "CASE WHEN ingreso = 0 THEN 'C' WHEN pct_acumulado <= 80 THEN 'A' "
        "WHEN pct_acumulado <= 95 THEN 'B' ELSE 'C' END")).scalar_one() == 0


def test_tasa_desabasto(conexion):
    assert conexion.execute(text("SELECT count(*) FROM kpi.desabasto_mensual "
        "WHERE tasa_desabasto IS NULL OR tasa_desabasto NOT BETWEEN 0 AND 1")).scalar_one() == 0


def test_resumen_unico(conexion):
    assert conexion.execute(text("SELECT count(*) FROM kpi.resumen_ejecutivo")).scalar_one() == 1


@pytest.mark.parametrize("vista", [
    "ventas_diarias_sucursal", "ventas_mensuales_categoria", "ventas_semanales_producto",
    "abc_productos", "cobertura_inventario", "desabasto_mensual", "incidencias_mensuales",
    "calidad_ultima_carga", "resumen_ejecutivo",
])
def test_vistas_con_filas(conexion, vista):
    assert conexion.execute(text(f"SELECT EXISTS (SELECT 1 FROM kpi.{vista})")).scalar_one()
