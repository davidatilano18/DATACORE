"""API REST de DATACORE.

Uso local:  .venv\\Scripts\\python -m uvicorn datacore.api.app:app --reload
Documentación interactiva en /docs.

Las lecturas usan el rol de solo lectura; la única escritura (atender una
alerta) usa el rol de la aplicación. Si DATACORE_API_KEY está definida, todas
las rutas salvo /salud exigen el encabezado X-API-Key.
"""

import os
import secrets
import time
from contextlib import asynccontextmanager
from datetime import date
from enum import Enum
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from sqlalchemy import text

from .. import __doc__ as descripcion_paquete
from ..db import engine
from ..registro import obtener_logger
from .consultas import filas, filtros, una

log = obtener_logger("api")
LIMITE_MAX = 5000
Limite = Annotated[int, Query(ge=1, le=LIMITE_MAX, description="Máximo de filas")]


class EstadoInventario(str, Enum):
    sin_existencia = "sin_existencia"
    bajo_minimo = "bajo_minimo"
    normal = "normal"
    exceso = "exceso"
    sin_rotacion = "sin_rotacion"


class TipoAlerta(str, Enum):
    riesgo = "RIESGO_DESABASTO"
    exceso = "EXCESO_INVENTARIO"
    sin_rotacion = "SIN_ROTACION"


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    app.state.lector = engine("lector", pool_pre_ping=True)
    app.state.escritor = engine("app", pool_pre_ping=True)
    yield
    app.state.lector.dispose()
    app.state.escritor.dispose()


app = FastAPI(title="DATACORE API", version="0.1.0", lifespan=ciclo_de_vida,
              description=f"{descripcion_paquete} Datos simulados de NexaTech Solutions (empresa ficticia).")
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("DATACORE_CORS", "*").split(","),
                   allow_methods=["GET", "POST"], allow_headers=["*"])

_encabezado = APIKeyHeader(name="X-API-Key", auto_error=False)


def verificar_clave(clave: str | None = Security(_encabezado)) -> None:
    esperada = os.getenv("DATACORE_API_KEY")
    if esperada and not (clave and secrets.compare_digest(clave, esperada)):
        raise HTTPException(status_code=401, detail="Falta o es inválido el encabezado X-API-Key")


@app.middleware("http")
async def bitacora(request: Request, siguiente):
    inicio = time.perf_counter()
    respuesta = await siguiente(request)
    log.info("%s %s %s %.0fms", request.method, request.url.path, respuesta.status_code,
             (time.perf_counter() - inicio) * 1000)
    return respuesta


def lector(request: Request):
    return request.app.state.lector


protegido = [Depends(verificar_clave)]


# --- salud y operación ----------------------------------------------------------

@app.get("/salud", tags=["operación"], summary="Estado de la API, la base de datos, el último ETL y el modelo activo")
def salud(request: Request):
    try:
        with request.app.state.lector.connect() as c:
            c.execute(text("SELECT 1"))
        bd = "ok"
    except Exception as exc:  # la salud debe responder aunque la BD falle
        log.error("salud: base de datos no disponible: %s", exc)
        return {"estado": "degradado", "base_de_datos": "error"}
    eng = request.app.state.lector
    etl = una(eng, "SELECT max(fin) AS fin, bool_and(estatus = 'exitosa') AS exitosa FROM ops.etl_ejecuciones "
                   "WHERE inicio = (SELECT max(inicio) FROM ops.etl_ejecuciones)")
    modelo = una(eng, "SELECT id_modelo, version, fecha_corte_datos FROM ops.modelos WHERE activo")
    return {"estado": "ok", "base_de_datos": bd, "ultimo_etl": etl, "modelo_activo": modelo}


@app.get("/etl/ejecuciones", tags=["operación"], dependencies=protegido)
def etl_ejecuciones(limite: Limite = 50, eng=Depends(lector)):
    return filas(eng, "SELECT * FROM ops.etl_ejecuciones ORDER BY id_ejecucion DESC LIMIT :l", l=limite)


@app.get("/calidad/ultima-carga", tags=["operación"], dependencies=protegido,
         summary="Hallazgos de calidad de la última corrida del ETL, por regla y acción")
def calidad_ultima_carga(eng=Depends(lector)):
    return filas(eng, "SELECT * FROM kpi.calidad_ultima_carga ORDER BY conteo DESC")


@app.get("/calidad/hallazgos", tags=["operación"], dependencies=protegido)
def calidad_hallazgos(regla: str | None = None, tabla: str | None = None, limite: Limite = 100,
                      eng=Depends(lector)):
    where, p = filtros(regla=regla, tabla=tabla)
    return filas(eng, f"SELECT * FROM ops.calidad_hallazgos {where} ORDER BY id_hallazgo DESC LIMIT :l", l=limite, **p)


# --- catálogos -------------------------------------------------------------------

@app.get("/catalogos/sucursales", tags=["catálogos"], dependencies=protegido)
def sucursales(eng=Depends(lector)):
    return filas(eng, "SELECT * FROM core.sucursales ORDER BY id_sucursal")


@app.get("/catalogos/categorias", tags=["catálogos"], dependencies=protegido)
def categorias(eng=Depends(lector)):
    return filas(eng, "SELECT * FROM core.categorias ORDER BY nombre")


@app.get("/catalogos/productos", tags=["catálogos"], dependencies=protegido)
def productos(buscar: str | None = Query(None, description="Texto en nombre o SKU"),
              id_categoria: int | None = None, limite: Limite = 500, eng=Depends(lector)):
    where, p = filtros(**{"p.id_categoria": id_categoria})
    if buscar:
        where = (where + " AND " if where else "WHERE ") + "(p.nombre ILIKE :b OR p.sku ILIKE :b)"
        p["b"] = f"%{buscar}%"
    return filas(eng, f"""SELECT p.*, c.nombre AS categoria, a.clase AS clase_abc
                          FROM core.productos p JOIN core.categorias c USING (id_categoria)
                          LEFT JOIN kpi.abc_productos a USING (id_producto)
                          {where} ORDER BY p.id_producto LIMIT :l""", l=limite, **p)


# --- indicadores -----------------------------------------------------------------

@app.get("/kpi/resumen", tags=["indicadores"], dependencies=protegido, summary="Resumen ejecutivo (una fila)")
def resumen(eng=Depends(lector)):
    return una(eng, "SELECT * FROM kpi.resumen_ejecutivo")


@app.get("/ventas/diarias", tags=["ventas"], dependencies=protegido,
         summary="Ventas por día; sin sucursal agrega todas")
def ventas_diarias(desde: date | None = None, hasta: date | None = None, id_sucursal: int | None = None,
                   eng=Depends(lector)):
    where, p = filtros(**{"fecha >=": desde, "fecha <=": hasta, "id_sucursal": id_sucursal})
    return filas(eng, f"""SELECT fecha, sum(tickets) AS tickets, sum(unidades) AS unidades, sum(ingreso) AS ingreso,
                                 round(sum(ingreso) / nullif(sum(tickets), 0), 2) AS ticket_promedio
                          FROM kpi.ventas_diarias_sucursal {where} GROUP BY fecha ORDER BY fecha""", **p)


@app.get("/ventas/sucursales", tags=["ventas"], dependencies=protegido, summary="Totales por sucursal en un rango")
def ventas_por_sucursal(desde: date | None = None, hasta: date | None = None, eng=Depends(lector)):
    where, p = filtros(**{"fecha >=": desde, "fecha <=": hasta})
    return filas(eng, f"""SELECT id_sucursal, codigo, sum(tickets) AS tickets, sum(ingreso) AS ingreso,
                                 round(sum(ingreso) / nullif(sum(tickets), 0), 2) AS ticket_promedio
                          FROM kpi.ventas_diarias_sucursal {where} GROUP BY 1, 2 ORDER BY ingreso DESC""", **p)


@app.get("/ventas/categorias", tags=["ventas"], dependencies=protegido, summary="Ventas mensuales por categoría")
def ventas_por_categoria(desde: date | None = None, hasta: date | None = None, eng=Depends(lector)):
    where, p = filtros(**{"mes >=": desde, "mes <=": hasta})
    return filas(eng, f"SELECT * FROM kpi.ventas_mensuales_categoria {where} ORDER BY mes, categoria", **p)


@app.get("/ventas/semanales", tags=["ventas"], dependencies=protegido,
         summary="Serie semanal de un producto (todas las sucursales o una)")
def ventas_semanales(id_producto: int, id_sucursal: int | None = None, eng=Depends(lector)):
    where, p = filtros(id_producto=id_producto, id_sucursal=id_sucursal)
    return filas(eng, f"""SELECT semana_inicio, sum(unidades) AS unidades, sum(ingreso) AS ingreso
                          FROM kpi.ventas_semanales_producto {where} GROUP BY 1 ORDER BY 1""", **p)


@app.get("/productos/abc", tags=["ventas"], dependencies=protegido)
def productos_abc(clase: str | None = Query(None, pattern="^[ABC]$"), limite: Limite = 500, eng=Depends(lector)):
    where, p = filtros(clase=clase)
    return filas(eng, f"SELECT * FROM kpi.abc_productos {where} ORDER BY ingreso DESC LIMIT :l", l=limite, **p)


# --- inventario y alertas --------------------------------------------------------

@app.get("/inventario/cobertura", tags=["inventario"], dependencies=protegido)
def cobertura(estado: EstadoInventario | None = None, id_sucursal: int | None = None, limite: Limite = 500,
              eng=Depends(lector)):
    where, p = filtros(**{"k.estado": estado.value if estado else None, "k.id_sucursal": id_sucursal})
    return filas(eng, f"""SELECT k.*, s.codigo AS sucursal, p.sku, p.nombre AS producto
                          FROM kpi.cobertura_inventario k JOIN core.sucursales s USING (id_sucursal)
                          JOIN core.productos p USING (id_producto)
                          {where} ORDER BY k.cobertura_dias NULLS FIRST LIMIT :l""", l=limite, **p)


@app.get("/inventario/estados", tags=["inventario"], dependencies=protegido,
         summary="Conteo de pares sucursal-producto por estado de inventario")
def estados_inventario(id_sucursal: int | None = None, eng=Depends(lector)):
    where, p = filtros(id_sucursal=id_sucursal)
    return filas(eng, f"SELECT estado, count(*) AS pares FROM kpi.cobertura_inventario {where} GROUP BY 1 ORDER BY 2 DESC", **p)


@app.get("/inventario/desabasto", tags=["inventario"], dependencies=protegido, summary="Tasa mensual de desabasto")
def desabasto(id_sucursal: int | None = None, eng=Depends(lector)):
    where, p = filtros(id_sucursal=id_sucursal)
    # Tasa agregada ponderando por pares activos de cada sucursal.
    return filas(eng, f"""SELECT mes, sum(pares_activos) AS pares_activos,
                                 sum(dias_par_sin_existencia) AS dias_par_sin_existencia,
                                 sum(tasa_desabasto * pares_activos) / nullif(sum(pares_activos), 0) AS tasa_desabasto
                          FROM kpi.desabasto_mensual {where} GROUP BY mes ORDER BY mes""", **p)


@app.get("/alertas", tags=["inventario"], dependencies=protegido, summary="Alertas de inventario pendientes")
def alertas(tipo: TipoAlerta | None = None, id_sucursal: int | None = None, incluir_atendidas: bool = False,
            limite: Limite = 500, eng=Depends(lector)):
    where, p = filtros(**{"a.tipo": tipo.value if tipo else None, "a.id_sucursal": id_sucursal,
                          "a.atendida": None if incluir_atendidas else False})
    return filas(eng, f"""SELECT a.*, s.codigo AS sucursal, p.sku, p.nombre AS producto, c.nombre AS categoria
                          FROM ops.alertas_inventario a JOIN core.sucursales s USING (id_sucursal)
                          JOIN core.productos p USING (id_producto) JOIN core.categorias c USING (id_categoria)
                          {where}
                          ORDER BY CASE a.tipo WHEN 'RIESGO_DESABASTO' THEN 0 WHEN 'EXCESO_INVENTARIO' THEN 1 ELSE 2 END,
                                   a.dias_cobertura NULLS LAST LIMIT :l""", l=limite, **p)


@app.post("/alertas/{id_alerta}/atender", tags=["inventario"], dependencies=protegido,
          summary="Marca una alerta como atendida")
def atender_alerta(id_alerta: int, request: Request):
    with request.app.state.escritor.begin() as c:
        n = c.execute(text("UPDATE ops.alertas_inventario SET atendida = TRUE WHERE id_alerta = :i"),
                      {"i": id_alerta}).rowcount
    if not n:
        raise HTTPException(status_code=404, detail="Alerta no encontrada")
    log.info("alerta %s atendida", id_alerta)
    return {"id_alerta": id_alerta, "atendida": True}


# --- pronóstico ------------------------------------------------------------------

@app.get("/modelo", tags=["pronóstico"], dependencies=protegido, summary="Modelo activo y sus métricas de backtest")
def modelo(eng=Depends(lector)):
    m = una(eng, "SELECT * FROM ops.modelos WHERE activo")
    if not m:
        raise HTTPException(status_code=404, detail="No hay modelo publicado")
    return m


@app.get("/pronosticos", tags=["pronóstico"], dependencies=protegido,
         summary="Pronóstico semanal del modelo activo; sin sucursal agrega todas")
def pronosticos(id_producto: int | None = None, id_sucursal: int | None = None, eng=Depends(lector)):
    where, p = filtros(**{"f.id_producto": id_producto, "f.id_sucursal": id_sucursal})
    where = (where + " AND " if where else "WHERE ") + "m.activo"
    return filas(eng, f"""SELECT f.semana_inicio, sum(f.demanda_estimada) AS demanda_estimada,
                                 sum(f.limite_inferior) AS limite_inferior, sum(f.limite_superior) AS limite_superior
                          FROM ops.predicciones_demanda f JOIN ops.modelos m USING (id_modelo)
                          {where} GROUP BY 1 ORDER BY 1""", **p)


@app.get("/incidencias/mensuales", tags=["operación"], dependencies=protegido)
def incidencias(id_sucursal: int | None = None, eng=Depends(lector)):
    where, p = filtros(id_sucursal=id_sucursal)
    return filas(eng, f"""SELECT mes, tipo, sum(total) AS total, sum(abiertas) AS abiertas
                          FROM kpi.incidencias_mensuales {where} GROUP BY 1, 2 ORDER BY 1, 2""", **p)


@app.get("/anomalias", tags=["operación"], dependencies=protegido)
def anomalias(id_sucursal: int | None = None, desde: date | None = None, hasta: date | None = None,
              tipo: str | None = Query(None, pattern="^(caida|pico)$"), eng=Depends(lector)):
    where, p = filtros(**{"a.id_sucursal": id_sucursal, "a.fecha >=": desde,
                          "a.fecha <=": hasta, "a.tipo": tipo})
    return filas(eng, f"""SELECT a.*, s.codigo AS sucursal FROM ops.anomalias a
                          JOIN core.sucursales s USING (id_sucursal)
                          {where} ORDER BY a.fecha, a.id_sucursal, a.metrica""", **p)
