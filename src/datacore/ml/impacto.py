"""Impacto en dinero: ¿cuánto vale resurtir con DATACORE frente a la política actual de NexaTech?

Se simula un año día a día (2025 por defecto) sobre la MISMA demanda real de cada par
sucursal-producto (ventas + demanda no surtida de `ground_truth`) con dos políticas:

a) Política actual: se reproducen tal cual las órdenes de compra que la política (s, S)
   del generador emitió ese año (`ground_truth/ordenes_compra`, con su retraso real).
b) DATACORE: revisión semanal (decisión al cierre del domingo, pedido el lunes). Con el
   pronóstico fuera de muestra del backtest (origen móvil: cada semana se pronostica solo con
   datos anteriores) se calcula un cuantil de la demanda durante el día del pedido + el tiempo
   de entrega + el retraso esperado + la semana de revisión (binomial negativa) y se pide lo
   que falte para cubrirlo, contando existencia y pedidos en camino. Como el modelo aprende
   de VENTAS, que subestiman la demanda cuando hubo faltantes, el pronóstico se corrige con
   la fracción de días agotado de las últimas 4 semanas (información que DATACORE sí tiene).
   El retraso de cada orden se sortea con la tasa de retrasos de su proveedor ANTERIOR al año.

El cuantil no se elige mirando el año evaluado: se calibra en el año anterior (el menor de la
rejilla que iguala o supera el nivel de servicio de la política actual) y se aplica fijo.

En ambas: la demanda que no encuentra existencia se pierde; no hay mermas ni ajustes de
conteo (se omiten en las dos para comparar solo la política de resurtido); se deja de
resurtir 30 días antes de descontinuar un producto (regla de negocio conocida).

Supuestos de dinero (configurables en `Supuestos`): precio y costo de la lista vigente
(core.productos), sin descuentos; costo anual de mantener inventario como fracción del costo.
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

EXTRA = 120  # días después del año en los que aún pueden llegar pedidos (no cuentan en las métricas)


@dataclass
class Supuestos:
    anio: int = 2025
    tasa_mantener_anual: float = 0.25   # capital, almacén, seguro y obsolescencia, como fracción del costo por año
    cuantil_objetivo: float | None = None  # None: se calibra en el año anterior (ver `calibrar`)
    cuantiles: tuple = (0.90, 0.95, 0.97, 0.98, 0.99, 0.995)  # rejilla para calibrar y para la frontera
    corregir_censura: bool = True       # divide el pronóstico entre (1 − fracción de días agotado en 4 semanas)
    tope_censura: float = 2.0           # factor máximo de esa corrección
    dias_revision: int = 7              # DATACORE revisa una vez por semana
    dias_fin_resurtido: int = 30        # se deja de pedir este número de días antes de la baja del producto
    semilla: int = 42                   # sorteo de retrasos de proveedor en la política DATACORE
    dispersion: dict = field(default_factory=lambda: {1: 2.30, 2: 2.28, 3: 2.29})  # k de la binomial negativa


@dataclass
class Datos:
    """Matrices (pares × días) con los pares siempre en el mismo orden."""
    pares: pd.MultiIndex                # (id_sucursal, id_producto)
    dias: pd.DatetimeIndex
    demanda: np.ndarray                 # demanda real diaria (vendido + perdido)
    vendido_real: np.ndarray            # lo que realmente se vendió (validación del simulador)
    existencia_inicial: np.ndarray      # existencia al cierre del día anterior al primer día
    llegadas_iniciales: np.ndarray      # inventario inicial de pares que arrancan dentro del año (ambas políticas)
    llegadas_previas: np.ndarray        # órdenes emitidas antes del año que llegan dentro de él (ambas políticas)
    llegadas_actual: np.ndarray         # recepciones de las órdenes reales emitidas dentro del año (política actual)
    vivo: np.ndarray                    # el par ya existe ese día
    puede_pedir: np.ndarray             # vivo y lejos de la baja del producto
    entrega: np.ndarray                 # días de entrega comprometidos por el proveedor
    prob_retraso: np.ndarray            # fracción histórica de órdenes con retraso del proveedor
    retraso_medio: np.ndarray           # retraso promedio cuando lo hay
    precio: np.ndarray
    costo: np.ndarray


# --- datos ----------------------------------------------------------------------------------
def cargar(ruta_gt: Path, sup: Supuestos, inicio: pd.Timestamp | None = None, fin: pd.Timestamp | None = None) -> Datos:
    """Por omisión simula el año sup.anio completo; inicio y fin permiten un periodo más corto."""
    gt = lambda nombre: pd.read_parquet(Path(ruta_gt) / f"{nombre}.parquet")
    inicio = pd.Timestamp(inicio) if inicio is not None else pd.Timestamp(sup.anio, 1, 1)
    fin = pd.Timestamp(fin) if fin is not None else pd.Timestamp(sup.anio, 12, 31)
    dias = pd.date_range(inicio, fin, freq="D")
    pares = pd.MultiIndex.from_frame(gt("inventario")[["id_sucursal", "id_producto"]]
                                     .sort_values(["id_sucursal", "id_producto"]))

    def matriz(df, valor, fecha="fecha"):
        df = df[(df[fecha] >= inicio) & (df[fecha] <= fin)]
        t = df.pivot_table(index=["id_sucursal", "id_producto"], columns=fecha, values=valor, aggfunc="sum")
        return t.reindex(index=pares, columns=dias).fillna(0).to_numpy(dtype=float)

    mov = gt("movimientos_inventario")
    vendido = matriz(mov[mov["tipo"] == "SALIDA_VENTA"].assign(u=lambda d: -d["cantidad"]), "u")
    perdido = matriz(gt("demanda_perdida"), "unidades")
    iniciales = matriz(mov[mov["tipo"] == "INVENTARIO_INICIAL"], "cantidad")
    previo = mov[mov["fecha"] < inicio].sort_values("id_movimiento").groupby(["id_sucursal", "id_producto"]).last()
    existencia0 = previo["existencia_resultante"].reindex(pares).fillna(0).to_numpy(dtype=float)
    primer_mov = mov.groupby(["id_sucursal", "id_producto"])["fecha"].min().reindex(pares)
    vivo = dias.to_numpy()[None, :] >= primer_mov.to_numpy()[:, None]

    ordenes = gt("ordenes_compra")
    del_anio = ordenes[ordenes["fecha_orden"] >= inicio]
    previas = ordenes[(ordenes["fecha_orden"] < inicio) & (ordenes["fecha_llegada"] >= inicio)]

    productos = gt("productos").set_index("id_producto")
    proveedores = gt("proveedores").set_index("id_proveedor")
    id_prod = pares.get_level_values("id_producto")
    proveedor = productos.loc[id_prod, "id_proveedor"].to_numpy()
    historia = ordenes[ordenes["fecha_orden"] < inicio].assign(
        id_proveedor=lambda d: d["id_producto"].map(productos["id_proveedor"]))
    por_prov = historia.groupby("id_proveedor")["dias_retraso"]
    prob = por_prov.apply(lambda s: float((s > 0).mean()))
    medio = por_prov.apply(lambda s: float(s[s > 0].mean()) if (s > 0).any() else 0.0)

    baja = gt("parametros_productos").set_index("id_producto")["_fecha_baja"].reindex(id_prod)
    limite = (baja - pd.Timedelta(days=sup.dias_fin_resurtido)).fillna(fin + pd.Timedelta(days=1))
    puede = vivo & (dias.to_numpy()[None, :] < limite.to_numpy()[:, None])

    return Datos(
        pares=pares, dias=dias, demanda=vendido + perdido, vendido_real=vendido, existencia_inicial=existencia0,
        llegadas_iniciales=iniciales, llegadas_previas=matriz(previas, "cantidad", "fecha_llegada"),
        llegadas_actual=matriz(del_anio, "cantidad", "fecha_llegada"), vivo=vivo, puede_pedir=puede,
        entrega=proveedores.loc[proveedor, "dias_entrega"].to_numpy(dtype=float),
        prob_retraso=prob.reindex(proveedor).fillna(0).to_numpy(dtype=float),
        retraso_medio=medio.reindex(proveedor).fillna(0).to_numpy(dtype=float),
        precio=productos.loc[id_prod, "precio_unitario"].to_numpy(dtype=float),
        costo=productos.loc[id_prod, "costo_unitario"].to_numpy(dtype=float))


# --- motor ------------------------------------------------------------------------------------
@dataclass
class Resultado:
    vendido: np.ndarray
    perdido: np.ndarray
    existencia: np.ndarray              # al cierre de cada día
    pedidos: int = 0
    unidades_pedidas: float = 0.0


def simular(demanda: np.ndarray, existencia0: np.ndarray, llegadas_fijas: np.ndarray,
            pedidos_en_camino: np.ndarray | None = None, politica=None) -> Resultado:
    """Simulación diaria con ventas perdidas.

    `llegadas_fijas`: recepciones que no dependen de la política (pares × días).
    `pedidos_en_camino`: recepciones ya pedidas al iniciar; cuentan como "en camino" hasta llegar.
    `politica(d, existencia, en_camino, vendido)`: al cierre del día d devuelve (cantidad, día de llegada)
    por par, o None si ese día no se revisa.
    """
    n, nd = demanda.shape
    relleno = np.zeros((n, EXTRA))
    fijas = np.concatenate([llegadas_fijas, relleno], axis=1)
    pedidos = np.concatenate([np.zeros_like(llegadas_fijas) if pedidos_en_camino is None else pedidos_en_camino,
                              relleno], axis=1)
    en_camino = pedidos.sum(axis=1)
    existencia = existencia0.astype(float).copy()
    vendido, perdido, cierre = (np.zeros_like(demanda) for _ in range(3))
    n_pedidos, unidades = 0, 0.0
    for d in range(nd):
        existencia += fijas[:, d] + pedidos[:, d]
        en_camino -= pedidos[:, d]
        v = np.minimum(demanda[:, d], existencia)
        vendido[:, d], perdido[:, d] = v, demanda[:, d] - v
        existencia -= v
        cierre[:, d] = existencia
        if politica is None:
            continue
        orden = politica(d, existencia, en_camino, vendido)
        if orden is None:
            continue
        q, llega = orden
        idx = np.flatnonzero(q > 0)
        np.add.at(pedidos, (idx, np.minimum(llega[idx], nd + EXTRA - 1)), q[idx])
        en_camino[idx] += q[idx]
        n_pedidos += len(idx)
        unidades += float(q[idx].sum())
    return Resultado(vendido, perdido, cierre, n_pedidos, unidades)


def simular_actual(datos: Datos) -> Resultado:
    """Política actual: las órdenes reales del año, con sus fechas de llegada reales."""
    return simular(datos.demanda, datos.existencia_inicial,
                   datos.llegadas_iniciales + datos.llegadas_previas + datos.llegadas_actual)


# --- política DATACORE -------------------------------------------------------------------------
def cuantil_binomial_negativa(mu: np.ndarray, var: np.ndarray, q: float) -> np.ndarray:
    """Cuantil q de una binomial negativa con la media y varianza dadas (Poisson si var ≤ media)."""
    mu = np.maximum(np.asarray(mu, dtype=float), 0.0)
    var = np.asarray(var, dtype=float)
    out = stats.poisson.ppf(q, mu)
    nb = (var > mu * 1.0001) & (mu > 0)
    if nb.any():
        out[nb] = stats.nbinom.ppf(q, mu[nb] ** 2 / (var[nb] - mu[nb]), mu[nb] / var[nb])
    return np.nan_to_num(out)


def pronosticos_semanales(predicciones: pd.DataFrame, pares: pd.MultiIndex, horizontes=(1, 2, 3),
                          columna: str = "gbm") -> dict[int, pd.DataFrame]:
    """{h: (semana objetivo × pares)} con el pronóstico hecho h semanas antes de esa semana."""
    out = {}
    for h in horizontes:
        p = predicciones[predicciones["horizonte"] == h]
        out[h] = p.pivot_table(index="semana", columns=["id_sucursal", "id_producto"], values=columna,
                               aggfunc="mean").reindex(columns=pares)
    return out


def demanda_proteccion(pron: dict[int, pd.DataFrame], lunes: pd.Timestamp, proteccion: np.ndarray,
                       dispersion: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Media y varianza de la demanda en los próximos `proteccion` días, prorrateando los pronósticos
    semanales hechos al cierre del domingo previo (semana del lunes = h1, la siguiente = h2…).
    Devuelve además qué pares no tienen pronóstico."""
    n = len(proteccion)
    mu, var = np.zeros(n), np.zeros(n)
    sin_pron = np.zeros(n, dtype=bool)
    restante = proteccion.astype(float).copy()
    for k, h in enumerate(sorted(pron)):
        semana = lunes + pd.Timedelta(weeks=k)
        fila = pron[h].loc[semana].to_numpy(dtype=float) if semana in pron[h].index else np.full(n, np.nan)
        fraccion = np.clip(restante / 7, 0, 1)
        sin_pron |= np.isnan(fila) & (fraccion > 0)
        semanal = np.clip(np.nan_to_num(fila), 0, None)
        mu += semanal * fraccion
        var += (semanal + semanal ** 2 / dispersion.get(h, 2.3)) * fraccion
        restante -= 7
    return mu, var, sin_pron


def politica_datacore(datos: Datos, pron: dict[int, pd.DataFrame], sup: Supuestos, cuantil: float | None = None):
    """Revisión semanal (decisión al cierre del domingo, pedido el lunes): pide lo necesario para que
    existencia + en camino cubra el cuantil de la demanda durante entrega + retraso esperado + revisión."""
    rng = np.random.default_rng(sup.semilla)
    q_obj = sup.cuantil_objetivo if cuantil is None else cuantil
    # +1: el pedido sale el lunes, al día siguiente de la decisión.
    proteccion = 1 + datos.entrega + datos.prob_retraso * datos.retraso_medio + sup.dias_revision
    n = len(datos.pares)
    agotado = np.zeros((n, 28))  # días con existencia 0 en las últimas 4 semanas (ventana circular)

    def politica(d, existencia, en_camino, vendido):
        agotado[:, d % 28] = existencia <= 0
        if datos.dias[d].dayofweek != 6:
            return None
        lunes = datos.dias[d] + pd.Timedelta(days=1)
        mu, var, sin_pron = demanda_proteccion(pron, lunes, proteccion, sup.dispersion)
        if sin_pron.any():
            # Sin pronóstico (p. ej., la última semana del año): ventas observadas de los últimos 28 días.
            base = vendido[sin_pron, max(0, d - 27):d + 1].sum(axis=1) / 28 * proteccion[sin_pron]
            mu[sin_pron], var[sin_pron] = base, base * 2
        if sup.corregir_censura:
            factor = np.clip(1 / (1 - np.minimum(agotado.mean(axis=1), 0.5)), 1, sup.tope_censura)
            mu, var = mu * factor, var * factor ** 2
        nivel = cuantil_binomial_negativa(mu, var, q_obj)
        posicion = existencia + en_camino
        q = np.where(datos.puede_pedir[:, d] & (posicion < nivel), np.ceil(nivel - posicion), 0.0)
        retraso = np.where(rng.random(n) < datos.prob_retraso, rng.integers(2, 9, n), 0)
        return q, d + 1 + datos.entrega.astype(int) + retraso

    return politica


def simular_datacore(datos: Datos, pron: dict[int, pd.DataFrame], sup: Supuestos,
                     cuantil: float | None = None) -> Resultado:
    return simular(datos.demanda, datos.existencia_inicial, datos.llegadas_iniciales,
                   pedidos_en_camino=datos.llegadas_previas, politica=politica_datacore(datos, pron, sup, cuantil))


# --- métricas -------------------------------------------------------------------------------------
def metricas(res: Resultado, datos: Datos, sup: Supuestos) -> dict:
    vivo = datos.vivo
    demanda = float((datos.demanda * vivo).sum())
    perdido = (res.perdido * vivo).sum(axis=1)
    inventario_diario = (res.existencia * vivo * datos.costo[:, None]).sum(axis=0)
    promedio = float(inventario_diario.mean())
    return {
        "demanda_unidades": demanda,
        "ventas_perdidas_unidades": float(perdido.sum()),
        "ventas_perdidas_pesos": float((perdido * datos.precio).sum()),
        "margen_perdido_pesos": float((perdido * (datos.precio - datos.costo)).sum()),
        "inventario_promedio_pesos": promedio,
        "costo_mantener_pesos": promedio * sup.tasa_mantener_anual * len(datos.dias) / 365,
        "dias_par_con_faltante": int(((res.perdido > 0) & vivo).sum()),
        "nivel_servicio": float((res.vendido * vivo).sum() / demanda) if demanda else float("nan"),
        "pedidos": res.pedidos,
    }


def impacto(actual: dict, datacore: dict) -> dict:
    """Ahorro de DATACORE (positivo = mejor que la política actual)."""
    margen = actual["margen_perdido_pesos"] - datacore["margen_perdido_pesos"]
    mantener = actual["costo_mantener_pesos"] - datacore["costo_mantener_pesos"]
    return {"margen_recuperado_pesos": margen, "ahorro_mantener_pesos": mantener, "beneficio_neto_pesos": margen + mantener,
            "ventas_recuperadas_pesos": actual["ventas_perdidas_pesos"] - datacore["ventas_perdidas_pesos"],
            "inventario_liberado_pesos": actual["inventario_promedio_pesos"] - datacore["inventario_promedio_pesos"]}


# --- pronósticos fuera de muestra -----------------------------------------------------------------
COLUMNAS_PRED = ["semana", "id_sucursal", "id_producto", "horizonte", "origen", "clase_abc", "gbm", "media_4", "y"]


def obtener_predicciones(cache: Path, recalcular: bool = False, log=print) -> tuple[pd.DataFrame, dict]:
    """Predicciones del backtest con origen móvil (7 bloques de 13 semanas: de abril de 2024 a diciembre de 2025, horizontes 1 a 3).
    Se guardan en `cache` (data/ no se versiona) porque calcularlas toma varios minutos."""
    import json
    cache = Path(cache)
    meta = cache.with_suffix(".json")
    if cache.exists() and meta.exists() and not recalcular:
        disp = {int(k): v for k, v in json.loads(meta.read_text(encoding="utf-8")).items()}
        return pd.read_parquet(cache), disp
    from ..db import engine
    from . import backtest
    from .datos import cargar as cargar_series
    series = cargar_series(engine("app"))
    r = backtest.ejecutar(series, horizontes=(1, 2, 3), origenes=7, variantes={"gbm": False}, log=log)
    pred = r["predicciones"][[c for c in COLUMNAS_PRED if c in r["predicciones"]]]
    cache.parent.mkdir(parents=True, exist_ok=True)
    pred.to_parquet(cache, index=False)
    meta.write_text(json.dumps({str(k): float(v) for k, v in r["dispersion"].items()}), encoding="utf-8")
    return pred, {int(k): float(v) for k, v in r["dispersion"].items()}


# --- reporte ----------------------------------------------------------------------------------------
def _pesos(x: float) -> str:
    return f"$ {x / 1e6:,.2f} M" if abs(x) >= 1e6 else f"$ {x:,.0f}"


def frontera(datos: Datos, pron, sup: Supuestos, log=print) -> pd.DataFrame:
    """Métricas de la política actual y de DATACORE para cada cuantil de la rejilla."""
    filas = {"actual": metricas(simular_actual(datos), datos, sup)}
    for q in sup.cuantiles:
        filas[q] = metricas(simular_datacore(datos, pron, sup, q), datos, sup)
        log(f"{sup.anio}: DATACORE p{q * 100:g} listo")
    return pd.DataFrame(filas).T


def calibrar(tabla: pd.DataFrame) -> float:
    """El menor cuantil cuyo nivel de servicio iguala o supera al de la política actual."""
    actual = tabla.loc["actual", "nivel_servicio"]
    candidatos = [q for q in tabla.index if q != "actual" and tabla.loc[q, "nivel_servicio"] >= actual]
    return float(min(candidatos)) if candidatos else float(max(q for q in tabla.index if q != "actual"))


def ejecutar(ruta_gt: Path, cache: Path, reporte: Path, sup: Supuestos, recalcular: bool = False,
             log=print) -> dict:
    pred, disp = obtener_predicciones(cache, recalcular, log)
    sup.dispersion = {**sup.dispersion, **disp}
    resultados = {}
    # Calibración: del primer bloque del backtest al cierre del año anterior; evaluación: el año completo.
    primera = pd.Timestamp(pred["semana"].min())
    periodos = {sup.anio - 1: (max(primera, pd.Timestamp(sup.anio - 1, 1, 1)), pd.Timestamp(sup.anio - 1, 12, 31)),
                sup.anio: (pd.Timestamp(sup.anio, 1, 1), pd.Timestamp(sup.anio, 12, 31))}
    for anio, (ini, fin) in periodos.items():
        s_anio = Supuestos(**{**sup.__dict__, "anio": anio})
        datos = cargar(ruta_gt, s_anio, ini, fin)
        log(f"{ini:%Y-%m-%d} a {fin:%Y-%m-%d}: {len(datos.pares):,} pares × {len(datos.dias)} días")
        resultados[anio] = (frontera(datos, pronosticos_semanales(pred, datos.pares), s_anio, log), datos)
    calibrado = sup.cuantil_objetivo or calibrar(resultados[sup.anio - 1][0])
    tabla, datos = resultados[sup.anio]
    if calibrado not in tabla.index:
        tabla.loc[calibrado] = metricas(simular_datacore(datos, pronosticos_semanales(pred, datos.pares), sup,
                                                         calibrado), datos, sup)
    perdido_real = float(((datos.demanda - datos.vendido_real) * datos.vivo).sum())
    reporte.mkdir(parents=True, exist_ok=True)
    texto = reporte_markdown(tabla, resultados[sup.anio - 1][0], calibrado, sup, perdido_real,
                             periodo_calibracion=periodos[sup.anio - 1])
    (reporte / "impacto.md").write_text(texto, encoding="utf-8")
    tabla.to_csv(reporte / "impacto_metricas.csv")
    return {"tabla": tabla, "calibracion": resultados[sup.anio - 1][0], "cuantil": calibrado,
            "impacto": impacto(tabla.loc["actual"].to_dict(), tabla.loc[calibrado].to_dict())}


def _nombre(q) -> str:
    return "Actual (órdenes reales)" if q == "actual" else f"DATACORE p{float(q) * 100:g}"


def _tabla_md(tabla: pd.DataFrame, marcar=None) -> str:
    filas = ["| política | ventas perdidas (u) | ventas perdidas | margen perdido | inventario promedio | "
             "costo de mantener | días-par con faltante | nivel de servicio |",
             "|---|---|---|---|---|---|---|---|"]
    for q, r in tabla.iterrows():
        nombre = f"**{_nombre(q)}** (calibrado)" if q == marcar else _nombre(q)
        filas.append(f"| {nombre} | {r.ventas_perdidas_unidades:,.0f} | {_pesos(r.ventas_perdidas_pesos)} | "
                     f"{_pesos(r.margen_perdido_pesos)} | {_pesos(r.inventario_promedio_pesos)} | "
                     f"{_pesos(r.costo_mantener_pesos)} | {r.dias_par_con_faltante:,.0f} | {r.nivel_servicio:.2%} |")
    return "\n".join(filas)


def reporte_markdown(tabla: pd.DataFrame, calibracion: pd.DataFrame, q: float, sup: Supuestos,
                     perdido_real: float, periodo_calibracion=None) -> str:
    actual, dc = tabla.loc["actual"], tabla.loc[q]
    imp = impacto(actual.to_dict(), dc.to_dict())
    menos_perdidas = 1 - dc.ventas_perdidas_unidades / actual.ventas_perdidas_unidades
    menos_inventario = 1 - dc.inventario_promedio_pesos / actual.inventario_promedio_pesos
    menos_faltantes = 1 - dc.dias_par_con_faltante / actual.dias_par_con_faltante
    previo = sup.anio - 1
    if periodo_calibracion is not None:
        ini, fin = periodo_calibracion
        previo = f"el periodo del {ini:%d/%m/%Y} al {fin:%d/%m/%Y}"
    servicio = "mayor" if dc.nivel_servicio >= actual.nivel_servicio else "menor"
    return f"""# Impacto en dinero de DATACORE ({sup.anio})

Generado por `python -m datacore.ml impacto`. Simulación diaria de {sup.anio} sobre la **misma demanda real** de cada
par sucursal-producto (ventas + demanda no surtida de `data/ground_truth`) con dos políticas de resurtido.

## Conclusión

Con DATACORE, NexaTech habría perdido **{menos_perdidas:.0%} menos ventas** ({_pesos(imp['ventas_recuperadas_pesos'])}
recuperados) con **{menos_inventario:.0%} menos inventario** inmovilizado ({_pesos(imp['inventario_liberado_pesos'])} en
promedio) y un nivel de servicio {servicio}: {dc.nivel_servicio:.1%} contra {actual.nivel_servicio:.1%}. El beneficio
neto estimado, entre margen recuperado y menor costo de mantener inventario, es de
**{_pesos(imp['beneficio_neto_pesos'])} al año**.

## Impacto de DATACORE ({_nombre(q)} contra la política actual, {sup.anio})

| concepto | política actual | DATACORE | diferencia |
|---|---|---|---|
| Ventas perdidas (unidades) | {actual.ventas_perdidas_unidades:,.0f} | {dc.ventas_perdidas_unidades:,.0f} | {menos_perdidas:.1%} menos |
| Ventas perdidas (pesos) | {_pesos(actual.ventas_perdidas_pesos)} | {_pesos(dc.ventas_perdidas_pesos)} | {_pesos(imp['ventas_recuperadas_pesos'])} recuperados |
| Margen perdido | {_pesos(actual.margen_perdido_pesos)} | {_pesos(dc.margen_perdido_pesos)} | {_pesos(imp['margen_recuperado_pesos'])} recuperados |
| Inventario promedio inmovilizado | {_pesos(actual.inventario_promedio_pesos)} | {_pesos(dc.inventario_promedio_pesos)} | {menos_inventario:.1%} menos |
| Costo anual de mantener inventario | {_pesos(actual.costo_mantener_pesos)} | {_pesos(dc.costo_mantener_pesos)} | {_pesos(imp['ahorro_mantener_pesos'])} de ahorro |
| Días-par con faltante | {actual.dias_par_con_faltante:,.0f} | {dc.dias_par_con_faltante:,.0f} | {menos_faltantes:.1%} menos |
| Nivel de servicio | {actual.nivel_servicio:.2%} | {dc.nivel_servicio:.2%} | {(dc.nivel_servicio - actual.nivel_servicio) * 100:+.2f} puntos |
| **Beneficio neto anual** | | | **{_pesos(imp['beneficio_neto_pesos'])}** |

## Cómo se eligió el cuantil (sin mirar {sup.anio})

DATACORE pide hasta cubrir un cuantil de la demanda esperada. El cuantil se calibró en **{previo}**: es el menor de la
rejilla con el que DATACORE iguala o supera el nivel de servicio de la política actual ese año. Después se aplicó fijo
a {sup.anio}. Que el cuantil nominal sea alto indica que la incertidumbre por par está subestimada (el WAPE por par
ronda 77 %): un p99 nominal se comporta como un nivel de cobertura menor.

### Calibración ({previo})

{_tabla_md(calibracion, marcar=q)}

### Frontera en {sup.anio} (todos los cuantiles, solo como referencia)

{_tabla_md(tabla, marcar=q)}

Cuantiles más altos compran servicio con inventario; más bajos, al revés.

## Cómo se simuló

- **Política actual:** se reproducen las órdenes de compra reales de NexaTech en {sup.anio}, con sus fechas de llegada
  reales. El simulador da {actual.ventas_perdidas_unidades:,.0f} unidades perdidas contra {perdido_real:,.0f} de la
  simulación original; la diferencia viene de omitir mermas y ajustes de conteo en ambas políticas.
- **DATACORE:** cada domingo, con el pronóstico fuera de muestra del backtest (origen móvil: cada bloque de 13 semanas
  se pronostica con un modelo entrenado solo con lo anterior), calcula el cuantil de la demanda durante el día del
  pedido, el tiempo de entrega, el retraso esperado del proveedor y la semana de revisión, y pide lo que falte para
  cubrirlo contando la existencia y lo ya pedido. Como el modelo aprende de ventas, que subestiman la demanda cuando
  hubo faltantes, el pronóstico se divide entre (1 − fracción de días agotado en las últimas 4 semanas), hasta
  ×{sup.tope_censura:g}.

## Supuestos (configurables en `Supuestos` o por línea de comandos)

| supuesto | valor | fuente |
|---|---|---|
| Precio y costo | lista vigente de `core.productos`, sin descuentos | catálogo |
| Margen | precio − costo de cada producto | catálogo |
| Costo anual de mantener inventario | {sup.tasa_mantener_anual:.0%} del costo | supuesto (capital, almacén, seguro, obsolescencia); `--tasa-mantener` |
| Revisión de DATACORE | semanal (pedido los lunes) | la política actual revisa a diario |
| Retraso de proveedores | sorteo con la tasa y el retraso medio de cada proveedor antes del año simulado | `ground_truth/ordenes_compra` |
| Venta perdida | la demanda sin existencia se pierde, no se acumula | igual que el generador |
| Mermas y ajustes de conteo | se omiten en ambas políticas | aislar la política de resurtido |
| Productos descontinuados | se deja de resurtir {sup.dias_fin_resurtido} días antes de la baja, en ambas | regla del generador |

**Lectura:** *días-par con faltante* son los días en que algún cliente no encontró el producto en una sucursal.
*Nivel de servicio* es la fracción de la demanda que se surtió. *Inventario promedio* es el valor a costo de la
existencia diaria promedio, y sobre él se calcula el costo de mantener.

**Limitaciones:** los pronósticos se calcularon con la historia real (la de la política actual), no con la que habría
generado DATACORE; la corrección de censura compensa una parte. El resultado vale para estos datos simulados.
"""
