"""Crea la base de datos, los roles y el esquema de DATACORE.

Uso: python -m datacore.db_setup [--reset | --refrescar]

--reset borra y recrea los esquemas core y ops (se pierden los datos cargados).
"""

import argparse
from time import perf_counter

from sqlalchemy import Engine, text

from .db import RAIZ, engine, variable


def crear_roles_y_base() -> None:
    admin = engine("admin", base="postgres", isolation_level="AUTOCOMMIT")
    app, lector, base = variable("PG_APP_USER"), variable("PG_LECTOR_USER"), variable("PG_DB")
    with admin.connect() as c:
        for rol, clave in ((app, variable("PG_APP_PASSWORD")), (lector, variable("PG_LECTOR_PASSWORD"))):
            existe = c.execute(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": rol}).scalar()
            verbo = "ALTER" if existe else "CREATE"
            # Los nombres de rol vienen de .env, no de usuarios externos; las claves van como literal escapado.
            clave_sql = c.execute(text("SELECT quote_literal(:k)"), {"k": clave}).scalar()
            c.execute(text(f'{verbo} ROLE "{rol}" LOGIN PASSWORD {clave_sql}'))
            print(f"rol {rol}: {'actualizado' if existe else 'creado'}")
        if not c.execute(text("SELECT 1 FROM pg_database WHERE datname = :b"), {"b": base}).scalar():
            c.execute(text(f'CREATE DATABASE "{base}" OWNER "{app}" ENCODING \'UTF8\' TEMPLATE template0'))
            print(f"base {base}: creada")
        else:
            print(f"base {base}: ya existía")
    admin.dispose()


def aplicar_esquema(reset: bool) -> None:
    lector = variable("PG_LECTOR_USER")
    ddl = (RAIZ / "db" / "schema.sql").read_text(encoding="utf-8")
    with engine("app").begin() as c:
        ya_existe = c.execute(text("SELECT 1 FROM information_schema.schemata WHERE schema_name = 'core'")).scalar()
        if ya_existe and not reset:
            print("esquemas core/ops ya existen (usa --reset para recrearlos)")
        else:
            c.execute(text("DROP SCHEMA IF EXISTS core CASCADE; DROP SCHEMA IF EXISTS ops CASCADE;"))
            c.exec_driver_sql(ddl)
            print("esquema aplicado: db/schema.sql")
        c.exec_driver_sql((RAIZ / "db" / "operacion.sql").read_text(encoding="utf-8"))
        print("tablas de operación aplicadas: db/operacion.sql")
        c.exec_driver_sql((RAIZ / "db" / "vistas.sql").read_text(encoding="utf-8"))
        print("vistas aplicadas: db/vistas.sql")
        for esquema in ("core", "ops", "kpi"):
            c.execute(text(f'GRANT USAGE ON SCHEMA {esquema} TO "{lector}"'))
            c.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA {esquema} TO "{lector}"'))
            c.execute(text(f'ALTER DEFAULT PRIVILEGES IN SCHEMA {esquema} GRANT SELECT ON TABLES TO "{lector}"'))
        tablas = c.execute(text("SELECT table_schema, count(*) FROM information_schema.tables "
                                "WHERE table_schema IN ('core','ops') GROUP BY 1 ORDER BY 1")).all()
        print("tablas:", dict(tablas))


def refrescar_vistas(engine: Engine) -> dict[str, float]:
    """Refresca las materializadas existentes y devuelve sus tiempos en segundos.

    Una instalación sin kpi todavía no requiere refresco. Todos los agregados
    se actualizan en una transacción y con una misma foto de los datos.
    """
    tiempos = {}
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as c:
        with c.begin():
            vistas = c.execute(text("SELECT matviewname FROM pg_matviews "
                                    "WHERE schemaname = 'kpi' ORDER BY matviewname")).scalars().all()
            for vista in vistas:
                inicio = perf_counter()
                nombre = c.dialect.identifier_preparer.quote(vista)
                c.exec_driver_sql(f"REFRESH MATERIALIZED VIEW kpi.{nombre}")
                tiempos[vista] = perf_counter() - inicio
    return tiempos


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--refrescar", action="store_true",
                        help="refresca únicamente las vistas materializadas existentes")
    args = parser.parse_args()
    if args.refrescar:
        for vista, segundos in refrescar_vistas(engine("app")).items():
            print(f"kpi.{vista}: {segundos:.3f} s")
        return
    crear_roles_y_base()
    aplicar_esquema(args.reset)


if __name__ == "__main__":
    main()
