"""Orquestación del ETL: extracción → transformación → carga (→ evaluación)."""

import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from . import transformacion as tr
from .calidad import Hallazgos
from .extraccion import extraer


def transformar(crudo: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    h = Hallazgos()
    sucs = tr.sucursales(crudo["sucursales"], h)
    cats = tr.categorias(crudo["productos"])
    provs = tr.proveedores(crudo["proveedores"], h)
    prods = tr.productos(crudo["productos"], cats, h)
    clis, mapa = tr.clientes(crudo["clientes"], h)
    detalle = tr.detalle_venta(crudo["detalle_venta"], prods, h)
    ventas, detalle_final = tr.ventas(crudo["ventas"], sucs, mapa, set(clis["id_cliente"]), detalle,
                                      crudo["detalle_venta"], h)
    tr.detalle_huerfano(detalle, detalle_final, h)
    tablas = {
        "sucursales": sucs,
        "categorias": cats,
        "proveedores": provs,
        "productos": prods,
        "clientes": clis,
        "ventas": ventas,
        "detalle_venta": detalle_final,
        "movimientos_inventario": tr.movimientos(crudo["movimientos_inventario"], sucs, prods, h),
        "inventario": tr.inventario(crudo["inventario"], sucs, prods, h),
        "incidencias": tr.incidencias(crudo["incidencias"], sucs, prods, h),
    }
    return tablas, h.to_frame()


def estadisticas(crudo: dict[str, pd.DataFrame], tablas: dict[str, pd.DataFrame]) -> dict[str, dict]:
    origen = {"categorias": "productos"}
    stats = {}
    for tabla, df in tablas.items():
        fuente = crudo[origen.get(tabla, tabla)]
        leidas = len(df) if tabla == "categorias" else len(fuente)
        stats[tabla] = {"leidas": leidas, "archivos": ", ".join(sorted(fuente["_archivo"].unique()))}
    return stats


def ejecutar(raw: Path, cargar_bd: bool = True, ground_truth: Path | None = None,
             reporte: Path | None = None) -> dict:
    inicio = datetime.now()
    t0 = time.perf_counter()

    def log(msg):
        print(f"[{time.perf_counter() - t0:6.1f}s] {msg}", flush=True)

    crudo = extraer(raw)
    log("extracción: " + ", ".join(f"{k} {len(v):,}" for k, v in crudo.items()))
    tablas, hallazgos = transformar(crudo)
    stats = estadisticas(crudo, tablas)
    resumen = pd.DataFrame({t: {"leidas": s["leidas"], "cargadas": len(tablas[t]),
                                "descartadas": s["leidas"] - len(tablas[t])} for t, s in stats.items()}).T
    log(f"transformación: {len(hallazgos):,} hallazgos de calidad")
    print(resumen.to_string())
    print(hallazgos.groupby(["regla", "accion"]).size().rename("registros").to_string())

    if cargar_bd:
        from ..db import engine
        from .carga import cargar
        cargar(engine("app"), tablas, hallazgos, stats, inicio)
        log("carga a PostgreSQL completa")

    resultado = {"tablas": tablas, "hallazgos": hallazgos, "resumen": resumen}
    if ground_truth is not None:
        from .evaluacion import deteccion, fidelidad, reporte_markdown
        bitacora = pd.read_csv(ground_truth / "defectos_inyectados.csv", dtype=str)
        det, fid = deteccion(hallazgos, bitacora), fidelidad(tablas, ground_truth)
        print(det.to_string(float_format=lambda x: f"{x:.3f}"))
        print(fid.to_string(float_format=lambda x: f"{x:.4f}"))
        resultado |= {"deteccion": det, "fidelidad": fid}
        if reporte is not None:
            reporte.mkdir(parents=True, exist_ok=True)
            (reporte / "calidad.md").write_text(reporte_markdown(det, fid, resumen), encoding="utf-8")
            log(f"reporte → {reporte / 'calidad.md'}")
    return resultado
