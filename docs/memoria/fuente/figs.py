"""Figuras propias de la memoria de estadía DATACORE."""
import sys
from pathlib import Path

import matplotlib
import pandas as pd
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

GRANATE = "#8A1538"
MARINO = "#1B2A4A"
AZUL = "#2E5A9C"
GRIS = "#8A94A6"
CLARO = "#E8ECF3"
plt.rcParams.update({"font.family": "Arial", "font.size": 11, "axes.spines.top": False,
                     "axes.spines.right": False, "savefig.dpi": 200, "savefig.bbox": "tight"})


def caja(ax, x, y, w, h, titulo, sub=None, fill=CLARO, edge=MARINO, bold=True, fs=10.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=fill, ec=edge, lw=1.3))
    if sub:
        ax.text(x + w / 2, y + h * 0.64, titulo, ha="center", va="center", fontsize=fs,
                fontweight="bold" if bold else "normal", color=MARINO)
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=fs - 2, color="#333")
    else:
        ax.text(x + w / 2, y + h / 2, titulo, ha="center", va="center", fontsize=fs,
                fontweight="bold" if bold else "normal", color=MARINO)


def flecha(ax, a, b, color=GRIS, estilo="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=estilo, mutation_scale=14, color=color, lw=1.4, ls=ls))


def lienzo(w, h):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off")
    return fig, ax


# 1. Arquitectura por capas -------------------------------------------------------
fig, ax = lienzo(11, 6.4)
capas = [("Fuentes", 5.3), ("Procesamiento", 4.15), ("Persistencia", 3.0), ("Analítica e IA", 1.85), ("Servicios y visualización", 0.7)]
for nombre, y in capas:
    ax.add_patch(FancyBboxPatch((0.15, y - 0.05), 10.7, 0.95, boxstyle="round,pad=0,rounding_size=0.05", fc="#F6F7FA", ec="#D5DAE3", lw=0.8))
    ax.text(0.3, y + 0.42, nombre, fontsize=9.5, color=GRANATE, fontweight="bold", va="center")
fuentes = [("POS", "ventas CSV"), ("Compras", "Excel"), ("CRM", "CSV cp1252"), ("Almacén", "CSV"), ("Mesa de ayuda", "CSV")]
for i, (t, s) in enumerate(fuentes):
    caja(ax, 2.3 + i * 1.72, 5.32, 1.5, 0.62, t, s, fs=9.5)
caja(ax, 2.3, 4.17, 1.5, 0.62, "Generador", "semilla 42", fill="#FFFFFF", fs=9.5)
caja(ax, 4.6, 4.17, 4.6, 0.62, "ETL + 18 reglas de calidad", "extracción · limpieza · carga COPY", fs=9.5)
caja(ax, 2.3, 3.02, 2.3, 0.62, "core", "datos de negocio", fs=9.5)
caja(ax, 5.1, 3.02, 2.3, 0.62, "ops", "bitácoras · modelos · alertas", fs=9.5)
caja(ax, 7.9, 3.02, 2.3, 0.62, "kpi", "vistas de indicadores", fs=9.5)
ax.text(10.75, 3.33, "PostgreSQL 16", ha="right", fontsize=8.5, color=GRIS, rotation=90, va="center")
caja(ax, 2.9, 1.87, 2.9, 0.62, "Pronóstico de demanda", "GBM Poisson · 4 horizontes", fs=9.5)
caja(ax, 6.2, 1.87, 4.0, 0.62, "Alertas y anomalías", "desabasto · exceso · sin rotación", fs=9.5)
caja(ax, 2.3, 0.72, 2.6, 0.62, "API FastAPI", "27 rutas · clave de acceso", fs=9.5)
caja(ax, 5.6, 0.72, 2.6, 0.62, "Dashboard Streamlit", "6 páginas", fs=9.5)
caja(ax, 8.6, 0.72, 2.0, 0.62, "Usuario", "navegador", fill="#FFFFFF", fs=9.5)
flecha(ax, (3.05, 4.79), (3.05, 5.32))
flecha(ax, (6.9, 5.32), (6.9, 4.79))
flecha(ax, (5.6, 4.17), (3.45, 3.64)); flecha(ax, (6.9, 4.17), (6.25, 3.64)); flecha(ax, (8.2, 4.17), (9.05, 3.64))
flecha(ax, (3.9, 3.02), (3.9, 2.49)); flecha(ax, (5.8, 2.18), (6.2, 2.18)); flecha(ax, (7.6, 2.49), (6.6, 3.02))
flecha(ax, (2.55, 3.02), (2.55, 1.34), color=AZUL); ax.text(2.65, 2.75, "lee core, ops y kpi", fontsize=8, color=AZUL, ha="left", va="center")
flecha(ax, (4.9, 1.03), (5.6, 1.03)); flecha(ax, (8.2, 1.03), (8.6, 1.03))
ax.text(10.6, 4.48, "cron: proceso\ndiario 02:00", fontsize=8.5, color=GRANATE, ha="right", va="center")
fig.savefig(OUT / "arquitectura.png"); plt.close(fig)

# 2. Cronograma de 16 semanas ---------------------------------------------------
fases = [("Requerimientos y alcance", "Documento de requerimientos"),
         ("Arquitectura, modelo E-R y reglas de simulación", "Diseño técnico y esquema de BD"),
         ("Generación de datos, base de datos y ETL inicial", "Dataset v1, BD y ETL"),
         ("Calidad, EDA e indicadores", "Reporte de calidad y EDA"),
         ("Variables, entrenamiento y evaluación", "Modelo y reporte de métricas"),
         ("API, dashboard e integración", "Prototipo integrado"),
         ("Despliegue, monitoreo, respaldos y pruebas", "Versión candidata"),
         ("Ajustes, documentación y presentación", "Versión final y memoria")]
fig, ax = plt.subplots(figsize=(11, 4.6))
for i, (f, e) in enumerate(fases):
    y = len(fases) - 1 - i
    ax.barh(y, 2, left=2 * i, color=AZUL if i % 2 == 0 else MARINO, height=0.55)
    ax.text(2 * i + 2.15, y, e, va="center", fontsize=8.5, color="#333")
ax.set_yticks(range(len(fases))); ax.set_yticklabels([f for f, _ in reversed(fases)], fontsize=9)
ax.set_xticks(range(0, 17, 2)); ax.set_xticklabels([str(s) for s in range(0, 17, 2)])
ax.set_xlim(0, 24); ax.set_xlabel("Semana", x=0.33); ax.spines["bottom"].set_bounds(0, 16)
ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color="#E3E6EC", lw=0.8); ax.set_axisbelow(True)
fig.savefig(OUT / "cronograma.png"); plt.close(fig)

# 3. Flujo del ETL ------------------------------------------------------------------
fig, ax = lienzo(11, 3.2)
pasos = [("Extracción", "CSV por año · Excel\ncp1252 con ';'"), ("Estandarización", "códigos, fechas,\nestados, correos"),
         ("Reglas de calidad", "corregir · rechazar\n· marcar"), ("Llaves internas", "código y SKU →\nid interno"),
         ("Carga", "COPY en una\ntransacción"), ("Evaluación", "contra la verdad\nde referencia")]
for i, (t, s) in enumerate(pasos):
    x = 0.2 + i * 1.8
    caja(ax, x, 1.2, 1.55, 1.25, t, s, fill=CLARO if i != 2 else "#F3E3E8", edge=MARINO if i != 2 else GRANATE, fs=9.5)
    if i:
        flecha(ax, (x - 0.25, 1.82), (x, 1.82))
ax.text(5.6, 0.75, "Cada hallazgo se guarda en ops.calidad_hallazgos con su regla, registro de origen y acción;\ncada corrida, en ops.etl_ejecuciones.",
        ha="center", fontsize=9, color="#444")
fig.savefig(OUT / "flujo_etl.png"); plt.close(fig)

# 4. Modelo entidad-relación (core) ------------------------------------------------
fig, ax = lienzo(11, 7.0)
ent = {
    "categorias": (0.3, 4.9, ["id_categoria PK", "nombre"]),
    "proveedores": (0.3, 2.6, ["id_proveedor PK", "rfc", "dias_entrega"]),
    "productos": (3.0, 3.6, ["id_producto PK", "sku", "id_categoria FK", "id_proveedor FK", "precio_unitario", "costo_unitario"]),
    "sucursales": (8.2, 4.55, ["id_sucursal PK", "codigo", "region", "tamano"]),
    "clientes": (8.2, 2.4, ["id_cliente PK", "tipo_cliente", "id_sucursal_pref. FK"]),
    "ventas": (5.6, 4.6, ["id_venta PK", "folio", "fecha_hora", "id_sucursal FK", "id_cliente FK", "total"]),
    "detalle_venta": (5.6, 1.9, ["id_detalle PK", "id_venta FK", "id_producto FK", "cantidad", "subtotal"]),
    "inventario": (3.7, 0.3, ["id_sucursal PK/FK", "id_producto PK/FK", "existencia"]),
    "movimientos_inv.": (0.3, 0.3, ["id_movimiento PK", "fecha", "tipo", "cantidad"]),
    "incidencias": (8.2, 0.05, ["id_incidencia PK", "tipo", "severidad", "estatus"]),
}
W = 2.2
pos = {}
for n, (x, y, cols) in ent.items():
    h = 0.5 + 0.24 * len(cols)
    ax.add_patch(FancyBboxPatch((x, y), W, h, boxstyle="round,pad=0,rounding_size=0.05", fc="white", ec=MARINO, lw=1.2))
    ax.add_patch(FancyBboxPatch((x, y + h - 0.34), W, 0.34, boxstyle="round,pad=0,rounding_size=0.05", fc=MARINO, ec=MARINO))
    ax.text(x + W / 2, y + h - 0.17, n, ha="center", va="center", color="white", fontsize=9.5, fontweight="bold")
    for j, c in enumerate(cols):
        ax.text(x + 0.1, y + h - 0.52 - 0.24 * j, c, fontsize=8, va="center", color=GRANATE if "PK" in c else "#333")
    pos[n] = (x, y, W, h)


def borde(n, lado):
    x, y, w, h = pos[n]
    return {"izq": (x, y + h / 2), "izq_alto": (x, y + h * 0.78), "izq_bajo": (x, y + h * 0.25), "der": (x + w, y + h / 2), "arr": (x + w / 2, y + h), "aba": (x + w / 2, y), "aba_izq": (x + 0.35, y), "aba_der": (x + w - 0.35, y)}[lado]


rel = [("categorias", "der", "productos", "izq_alto"), ("proveedores", "der", "productos", "izq"),
       ("productos", "der", "detalle_venta", "izq"), ("ventas", "aba", "detalle_venta", "arr"),
       ("sucursales", "izq", "ventas", "der"), ("clientes", "izq", "ventas", "der"),
       ("productos", "aba", "inventario", "arr"), ("productos", "aba_izq", "movimientos_inv.", "der"),
       ("sucursales", "aba", "clientes", "arr"), ("sucursales", "der", "incidencias", "der")]
for a, la, b, lb in rel:
    cs = "angle,angleA=90,angleB=0,rad=0" if (a, b) == ("productos", "movimientos_inv.") else ("arc,angleA=0,angleB=0,armA=25,armB=25,rad=8" if b == "incidencias" else "arc3")
    ax.annotate("", xy=borde(b, lb), xytext=borde(a, la), arrowprops=dict(arrowstyle="-|>", color=GRIS, lw=1.1, connectionstyle=cs))
ax.text(10.7, 6.45, "1 → N", ha="right", fontsize=9, color=GRIS)
fig.savefig(OUT / "modelo_er.png"); plt.close(fig)

# 5. Proceso diario ---------------------------------------------------------------
fig, ax = lienzo(11, 2.6)
pasos = [("Respaldo", "pg_dump + restauración\ny conteo de filas"), ("ETL", "recarga core\ny refresca kpi"),
         ("Modelo", "pronóstico 4 semanas\ny alertas"), ("Anomalías", "Poisson sobre\ntickets diarios"), ("Monitoreo", "BD, API, dashboard,\ndisco y antigüedad")]
for i, (t, s) in enumerate(pasos):
    x = 0.3 + i * 2.15
    caja(ax, x, 0.8, 1.85, 1.2, t, s, fs=10)
    if i:
        flecha(ax, (x - 0.3, 1.4), (x, 1.4))
ax.text(5.5, 0.35, "Cada paso registra su duración y su error en ops.corridas; si uno falla, la corrida se detiene y queda en la bitácora.",
        ha="center", fontsize=9, color="#444")
fig.savefig(OUT / "proceso_diario.png"); plt.close(fig)

# 6. WAPE del modelo contra baselines ----------------------------------------------
metodos = ["Modelo\n(GBM Poisson)", "Media móvil\n8 semanas", "SBA", "Ingenuo", "Estacional"]
wape = {1: [26.9, 28.8, 33.9, 36.0, 38.9], 2: [27.0, 29.3, 34.2, 36.6, 39.0], 4: [27.2, 30.2, 34.6, 37.5, 39.1]}
fig, ax = plt.subplots(figsize=(10, 4.6))
import numpy as np
x = np.arange(len(metodos)); w = 0.26
tonos = {1: "#9DB3D6", 2: "#5B82BF", 4: MARINO}
for k, h in enumerate([1, 2, 4]):
    b = ax.bar(x + (k - 1) * w, wape[h], w, color=tonos[h], label=f"h = {h} semana{'s' if h > 1 else ''}")
    for r in b:
        ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 0.4, f"{r.get_height():.1f}", ha="center", fontsize=7.5)
ax.set_xticks(x); ax.set_xticklabels(metodos)
ax.set_ylabel("WAPE producto-semana (%)"); ax.set_ylim(0, 45)
ax.legend(frameon=False, ncol=3, loc="upper left")
ax.grid(axis="y", color="#E3E6EC"); ax.set_axisbelow(True)
fig.savefig(OUT / "wape_baselines.png"); plt.close(fig)

# 7. Exhaustividad de anomalías por duración ---------------------------------------
fig, ax = plt.subplots(figsize=(8, 3.6))
dur = ["2-3 h", "4-5 h", "6-8 h"]; rec = [12.7, 15.2, 49.6]
b = ax.bar(dur, rec, color=[GRIS, GRIS, AZUL], width=0.5)
for r in b:
    ax.text(r.get_x() + r.get_width() / 2, r.get_height() + 1, f"{r.get_height():.1f} %", ha="center")
ax.set_ylabel("Exhaustividad (%)"); ax.set_xlabel("Duración de la falla del punto de venta"); ax.set_ylim(0, 60)
ax.grid(axis="y", color="#E3E6EC"); ax.set_axisbelow(True)
fig.savefig(OUT / "anomalias_duracion.png"); plt.close(fig)

# 8. Precisión y exhaustividad de las reglas de alerta -------------------------------
fig, ax = plt.subplots(figsize=(8, 4))
reglas = [("Modelo, percentil 90\n(publicada)", 16.2, 54.1), ("Modelo,\nvalor medio", 27.8, 30.8), ("Promedio 4 semanas\n(sin modelo)", 20.5, 33.2)]
for nombre, p, r in reglas:
    c = AZUL if "publicada" in nombre else GRIS
    ax.scatter(r, p, s=140, color=c, zorder=3)
    ax.annotate(nombre.replace("\n", " "), (r, p), xytext=(8, 6), textcoords="offset points", fontsize=9)
ax.set_xlabel("Exhaustividad: faltantes anticipados (%)"); ax.set_ylabel("Precisión: alertas acertadas (%)")
ax.set_xlim(20, 70); ax.set_ylim(10, 32)
ax.grid(color="#E3E6EC"); ax.set_axisbelow(True)
fig.savefig(OUT / "alertas_pr.png"); plt.close(fig)

# 9. Defectos inyectados por tipo ---------------------------------------------------
defs = {"sucursal_codigo_sucio": 3621, "venta_fecha_formato_alterno": 3621, "venta_metodo_pago_faltante": 1811,
        "detalle_duplicado": 1281, "cliente_estado_variante": 1200, "venta_duplicada": 724,
        "movimiento_cantidad_cero": 648, "detalle_cantidad_negativa": 641, "detalle_precio_escala": 641,
        "cliente_email_faltante": 640, "venta_total_inconsistente": 543, "cliente_telefono_faltante": 480,
        "detalle_producto_inexistente": 320, "cliente_casi_duplicado": 160, "venta_fecha_futura": 89,
        "cliente_email_invalido": 74, "producto_categoria_faltante": 4, "producto_costo_mayor_precio": 4}
fig, ax = plt.subplots(figsize=(9, 5.6))
n = list(defs)[::-1]; v = [defs[k] for k in n]
ax.barh(n, v, color=AZUL, height=0.6)
for i, val in enumerate(v):
    ax.text(val + 40, i, f"{val:,}", va="center", fontsize=8)
ax.set_xlabel("Registros con el defecto inyectado"); ax.tick_params(axis="y", labelsize=8.5)
ax.spines["left"].set_visible(False); ax.tick_params(axis="y", length=0); ax.set_xlim(0, 4200)
fig.savefig(OUT / "defectos.png"); plt.close(fig)
print("ok", sorted(p.name for p in OUT.glob("*.png")))

# 10. Frontera inventario–ventas perdidas (Fase 1 de mejoras) -------------------------------
m = pd.read_csv(Path(sys.argv[2]) / "impacto_metricas.csv", index_col=0) if len(sys.argv) > 2 else None
if m is not None:
    fig, ax = plt.subplots(figsize=(9, 4.8))
    dc = m.drop(index="actual")
    ax.plot(dc["inventario_promedio_pesos"] / 1e6, dc["ventas_perdidas_unidades"] / 1e3, "-o", color=AZUL, lw=1.8, ms=6,
            label="DATACORE (un punto por cuantil)")
    for q, r in dc.iterrows():
        ax.annotate(f"p{float(q) * 100:g}", (r["inventario_promedio_pesos"] / 1e6, r["ventas_perdidas_unidades"] / 1e3),
                    xytext=(6, 4), textcoords="offset points", fontsize=8.5, color="#333")
    a = m.loc["actual"]
    ax.scatter([a["inventario_promedio_pesos"] / 1e6], [a["ventas_perdidas_unidades"] / 1e3], s=110, color=GRANATE,
               zorder=5, label="Política actual (órdenes reales)")
    ax.annotate("política actual", (a["inventario_promedio_pesos"] / 1e6, a["ventas_perdidas_unidades"] / 1e3),
                xytext=(-10, 12), textcoords="offset points", ha="right", fontsize=9, color=GRANATE)
    ax.set_xlabel("Inventario promedio inmovilizado (millones de pesos)")
    ax.set_ylabel("Ventas perdidas (miles de unidades)")
    ax.grid(color="#E3E6EC"); ax.set_axisbelow(True); ax.legend(frameon=False, loc="upper right")
    fig.savefig(OUT / "impacto_frontera.png"); plt.close(fig)

# 11. F1 por trimestre de las reglas de alerta (Fase 2 de mejoras; valores de reports/ml/backtest.md) ----
bloques = ["ene–mar", "abr–jun", "jul–sep", "oct–dic"]
f1 = {"p90 (anterior)": ([0.238, 0.226, 0.241, 0.249], GRIS, "--"),
      "Media": ([0.262, 0.256, 0.286, 0.292], "#9DB3D6", "-"),
      "Umbral por segmento": ([0.264, 0.251, 0.279, 0.281], "#C9A227", ":"),
      "Media + censura (nueva)": ([0.269, 0.263, 0.291, 0.299], AZUL, "-")}
fig, ax = plt.subplots(figsize=(9, 4.2))
for nombre, (v, c, ls) in f1.items():
    ax.plot(bloques, v, ls, marker="o", color=c, lw=2.4 if "nueva" in nombre else 1.6, label=nombre)
ax.set_ylabel("F1 (2025, fuera de muestra)"); ax.set_ylim(0.2, 0.32)
ax.grid(axis="y", color="#E3E6EC"); ax.set_axisbelow(True); ax.legend(frameon=False, ncol=2, loc="lower right")
fig.savefig(OUT / "alertas_f1_bloques.png"); plt.close(fig)
print("figuras de mejoras listas")

# 12. Capturas del dashboard recortadas para la memoria: sin la barra lateral y solo la sección principal, -----------
#     para que se lean al ancho de la página. Las capturas completas están en reports/dashboard/.
from PIL import Image  # noqa: E402

RECORTES = {  # (x0, y0, x1, y1) en píxeles de la captura de 1440 × 1400
    "inicio": (360, 30, 1380, 1260),
    "ventas": (360, 30, 1380, 860),
    "inventario": (360, 30, 1380, 905),
    "alertas": (360, 30, 1380, 985),
    "pronostico": (360, 30, 1380, 1060),
    "calidad": (360, 30, 1380, 940),
}
CAPTURAS = Path(__file__).resolve().parents[3] / "reports/dashboard"
for nombre, caja in RECORTES.items():
    Image.open(CAPTURAS / f"{nombre}.png").crop(caja).save(OUT / f"dash_{nombre}.png", optimize=True)
print("capturas recortadas")
