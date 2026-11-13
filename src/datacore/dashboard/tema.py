"""Sistema visual de DATACORE: marca, paleta validada, plantilla de Plotly y componentes.

Reglas (guía de visualización del proyecto):
- Color de series en orden FIJO (SERIES), nunca ciclado ni por rango; más de 8 → "Otras".
- Un solo eje Y por gráfica; nada de ejes dobles.
- Los textos usan tinta (TINTA_*), nunca el color de la serie.
- Los colores de estado (ESTADO) son exclusivos de estados y siempre van con ícono + texto.
- SERIES pasó el validador de daltonismo (adyacentes ΔE ≥ 11.5, visión normal ≥ 21.4; los 3
  primeros también en todos los pares). Ámbar y rosa tienen contraste < 3:1 sobre blanco:
  úsalos con etiquetas visibles o tabla.
"""

from html import escape
from pathlib import Path

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

RAIZ = Path(__file__).resolve().parents[3]
MARCA = RAIZ / "branding" / "png"

# --- marca ----------------------------------------------------------------------
MARINO = "#1B2A4A"      # azul marino UPQ: texto principal, encabezados
GUINDA = "#8A1538"      # guinda UPQ: acento de marca, acción primaria
GUINDA_CLARO = "#E05A7E"
NIEBLA = "#E9EDF3"

# --- superficies y tinta ------------------------------------------------------------
FONDO = "#F5F7FA"
SUPERFICIE = "#FFFFFF"
TINTA = "#1B2A4A"
TINTA_2 = "#4A5A75"
TINTA_TENUE = "#7C8AA3"
REJILLA = "#E6EAF0"
EJE = "#C9D2E0"
BORDE = "rgba(27, 42, 74, 0.10)"

# --- datos -------------------------------------------------------------------------
SERIES = ["#2E5A9C", "#A3214A", "#1F9E89", "#C8612E", "#7356BF", "#D9A21B", "#4C8C2B", "#E07AA0"]
DESTACADO = SERIES[0]   # una sola serie protagonista
CONTEXTO = "#B8C2D3"    # series de comparación que deben ceder protagonismo
SECUENCIAL = ["#E3EAF5", "#B9CCE8", "#86A9D8", "#5683C2", "#2E5A9C", "#1F4278", "#142C52"]

ESTADO = {  # nivel → (color, ícono)
    "bien": ("#1E8E3E", "●"),
    "aviso": ("#C77C02", "▲"),
    "serio": ("#D4622A", "◆"),
    "critico": ("#C62828", "■"),
    "neutro": ("#7C8AA3", "○"),
}

FUENTE = '"IBM Plex Sans", "Segoe UI", system-ui, -apple-system, sans-serif'  # alojada en static/fuentes
FUENTE_CIFRAS = '"IBM Plex Sans Condensed", "IBM Plex Sans", "Segoe UI", sans-serif'  # títulos y cifras grandes


# --- formatos -----------------------------------------------------------------------
def mxn(valor, decimales: int = 0) -> str:
    return "—" if valor is None else f"$ {valor:,.{decimales}f}"


def mxn_corto(valor) -> str:
    if valor is None:
        return "—"
    for limite, sufijo in ((1e9, "MM"), (1e6, "M"), (1e3, "k")):
        if abs(valor) >= limite:
            return f"$ {valor / limite:,.1f} {sufijo}"
    return f"$ {valor:,.0f}"


def entero(valor) -> str:
    return "—" if valor is None else f"{valor:,.0f}"


def pct(valor, decimales: int = 1, con_signo: bool = False) -> str:
    if valor is None:
        return "—"
    return f"{valor:+.{decimales}f} %" if con_signo else f"{valor:.{decimales}f} %"


# --- plantilla de Plotly ------------------------------------------------------------
def _plantilla() -> go.layout.Template:
    t = go.layout.Template()
    t.layout = go.Layout(
        font=dict(family=FUENTE, size=13, color=TINTA_2),
        colorway=SERIES,
        paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE,
        margin=dict(l=8, r=16, t=36, b=8),
        title=dict(font=dict(size=15, color=TINTA), x=0, xanchor="left", y=0.98),
        xaxis=dict(showgrid=False, linecolor=EJE, ticks="outside", tickcolor=EJE, ticklen=4,
                   tickfont=dict(color=TINTA_TENUE, size=12), title=dict(font=dict(color=TINTA_TENUE, size=12))),
        yaxis=dict(gridcolor=REJILLA, zeroline=False, linecolor="rgba(0,0,0,0)",
                   tickfont=dict(color=TINTA_TENUE, size=12), title=dict(font=dict(color=TINTA_TENUE, size=12))),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text="",
                    font=dict(color=TINTA_2, size=12)),
        hoverlabel=dict(bgcolor=SUPERFICIE, bordercolor=EJE, font=dict(family=FUENTE, color=TINTA, size=13)),
        hovermode="x unified",
        barcornerradius=4, bargap=0.28,
        separators=".,",
    )
    t.data.scatter = [go.Scatter(line=dict(width=2), marker=dict(size=8))]
    t.data.bar = [go.Bar(marker=dict(line=dict(color=SUPERFICIE, width=2)))]
    return t


pio.templates["datacore"] = _plantilla()
pio.templates.default = "datacore"


def grafica(figura: go.Figure, alto: int = 360, clave: str | None = None) -> None:
    """Muestra una figura con el estilo de la casa y sin la barra de herramientas de Plotly."""
    # Fondo blanco explícito: el tema de Streamlit pinta el fondo de la página y dentro de los bloques se ve gris.
    figura.update_layout(height=alto, paper_bgcolor=SUPERFICIE, plot_bgcolor=SUPERFICIE)
    st.plotly_chart(figura, width="stretch", key=clave,
                    config={"displayModeBar": False, "locale": "es"})


# --- CSS y página -----------------------------------------------------------------------
CSS = f"""
<style>
  @font-face {{ font-family: "IBM Plex Sans Condensed"; font-weight: 600; font-display: swap;
               src: url("app/static/fuentes/ibm-plex-sans-condensed-600.woff2") format("woff2"); }}
  @font-face {{ font-family: "IBM Plex Sans Condensed"; font-weight: 700; font-display: swap;
               src: url("app/static/fuentes/ibm-plex-sans-condensed-700.woff2") format("woff2"); }}
  /* Encabezado tipo folio: banda marino con el título, el contexto y el sello del corte de datos. */
  .st-key-dc_folio {{ background: {MARINO}; border-radius: 8px; padding: 20px 26px 16px; margin-bottom: 18px;
                     border-bottom: 4px solid {GUINDA}; gap: .45rem; }}
  .st-key-dc_folio h1 {{ color: #FFFFFF !important; font-family: {FUENTE_CIFRAS} !important; font-size: 2.1rem !important;
                        font-weight: 700 !important; letter-spacing: 0 !important; line-height: 1.2 !important; }}
  .dc-folio {{ display: flex; justify-content: space-between; align-items: flex-end; gap: 1.5rem; }}
  .dc-folio .ctx {{ color: #C9D3E4; font-size: .95rem; min-width: 0; max-width: 75ch; }}
  @media (max-width: 700px) {{ .dc-folio {{ flex-wrap: wrap; }} }}
  .dc-sello {{ color: #FFFFFF; font-family: {FUENTE_CIFRAS}; font-weight: 600; font-size: .92rem; white-space: nowrap;
              border: 1px solid rgba(255,255,255,.35); border-radius: 4px; padding: .2rem .7rem; }}
  .dc-sello span {{ color: #C9D3E4; font-weight: 600; margin-right: .35rem; }}
  /* Momento de carga: una sola vez al dibujar la página; nada se mueve si el sistema pide menos movimiento. */
  @keyframes dc-llenar {{ from {{ transform: scaleX(0); }} to {{ transform: scaleX(1); }} }}
  @keyframes dc-barrido {{ from {{ clip-path: inset(0 100% 0 0); }} to {{ clip-path: inset(0 0 0 0); }} }}
  @keyframes dc-aparecer {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: none; }} }}
  .dc-salud div {{ transform-origin: left center; animation: dc-llenar .7s cubic-bezier(.2,.7,.2,1) both; }}
  svg.spark {{ animation: dc-barrido 1s ease-out .2s both; }}
  .st-key-dc_mapa {{ background: {SUPERFICIE}; }}
  .dc-kpi, .dc-suc {{ animation: dc-aparecer .45s ease-out both; }}
  .dc-kpi:nth-child(2), .dc-suc:nth-child(4n+2) {{ animation-delay: .06s; }}
  .dc-kpi:nth-child(3), .dc-suc:nth-child(4n+3) {{ animation-delay: .12s; }}
  .dc-kpi:nth-child(4), .dc-suc:nth-child(4n+4) {{ animation-delay: .18s; }}
  .dc-kpi:nth-child(5) {{ animation-delay: .24s; }}
  @media (prefers-reduced-motion: reduce) {{
    .dc-salud div, svg.spark, .dc-kpi, .dc-suc {{ animation: none !important; }} }}
  html, body, [class*="css"] {{ font-family: {FUENTE}; font-variant-numeric: tabular-nums; }}
  .block-container {{ padding-top: 2rem; padding-bottom: 3rem; max-width: 1360px; }}
  h1, h2, h3 {{ color: {TINTA}; letter-spacing: -0.01em; }}
  h1 {{ font-size: 1.85rem !important; font-weight: 700 !important; padding: 0 0 .15rem !important; }}
  [data-testid="stHeader"] {{ background: transparent; }}
  /* Barra lateral marino: el enlace activo lleva una marca guinda a la izquierda. */
  [data-testid="stSidebar"] {{ border-right: 0; }}
  [data-testid="stSidebarHeader"] {{ padding-top: 1.4rem; padding-bottom: .8rem; }}
  [data-testid="stSidebarHeader"] img, [data-testid="stLogo"] {{ height: 2.4rem !important; max-width: 12rem; }}
  [data-testid="stSidebarNav"] a {{ border-radius: 6px; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: rgba(255,255,255,.09); box-shadow: inset 3px 0 0 {GUINDA_CLARO}; }}
  [data-testid="stSidebarNav"] a[aria-current="page"] span {{ color: #FFFFFF; font-weight: 600; }}
  [data-testid="stSidebarNav"] a:focus-visible {{ outline: 2px solid {GUINDA_CLARO}; outline-offset: 1px; }}
  .dc-desc {{ color: {TINTA_2}; font-size: .95rem; }}
  .dc-seccion {{ margin: 1.6rem 0 .6rem; }}
  .dc-seccion b {{ color: {TINTA}; font-size: 1.05rem; font-weight: 600; }}
  .dc-seccion span {{ display: block; color: {TINTA_TENUE}; font-size: .86rem; margin-top: .1rem; }}
  /* Bloques: contenedores con borde de Streamlit en blanco y con poco radio. */
  [data-testid="stVerticalBlock"]:has(> [data-testid="stElementContainer"] .dc-bloque) {{ background: {SUPERFICIE}; border-radius: 8px; }}
  .dc-bloque {{ display: flex; align-items: baseline; flex-wrap: wrap; gap: .1rem .6rem; margin-bottom: .2rem; }}
  .dc-bloque b {{ color: {TINTA}; font-size: 1rem; font-weight: 600; }}
  .dc-bloque span {{ color: {TINTA_TENUE}; font-size: .86rem; }}
  /* Franja de indicadores: una sola pieza dividida por líneas finas. */
  .dc-franja {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(165px, 1fr)); background: {SUPERFICIE};
               border: 1px solid {EJE}; border-radius: 8px; overflow: hidden; }}
  .dc-franja.ligera {{ background: transparent; border: 0; border-radius: 0; border-top: 1px solid {REJILLA}; margin-top: .8rem; }}
  .dc-kpi {{ padding: 14px 18px 12px; border-left: 1px solid {REJILLA}; min-width: 0; }}
  .dc-kpi:first-child {{ border-left: 0; }}
  .dc-franja.ligera .dc-kpi {{ padding: 12px 18px 2px; }}
  .dc-franja.ligera .dc-kpi:first-child {{ padding-left: 0; }}
  .dc-kpi .t {{ color: {TINTA_2}; font-size: .84rem; font-weight: 500; display: flex; align-items: center; gap: .4rem; }}
  .dc-kpi .v {{ color: {TINTA}; font-family: {FUENTE_CIFRAS}; font-size: 1.95rem; font-weight: 600; line-height: 1.15;
               margin-top: .2rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .dc-franja.ligera .dc-kpi .v {{ font-size: 1.55rem; }}
  .dc-kpi .d {{ font-size: .8rem; font-weight: 600; margin-top: .1rem; }}
  .dc-kpi .n {{ color: {TINTA_TENUE}; font-size: .78rem; margin-top: .1rem; }}
  .dc-kpi svg.spark {{ display: block; width: 100%; height: 30px; margin-top: .4rem; }}
  /* Barra de salud: proporción de pares por estado, con leyenda de ícono, texto y conteo. */
  .dc-salud {{ display: flex; height: 22px; border-radius: 4px; overflow: hidden; margin: .5rem 0 .6rem; }}
  .dc-salud div {{ min-width: 3px; }}
  .dc-leyenda {{ display: flex; flex-wrap: wrap; gap: .3rem 1.4rem; color: {TINTA_2}; font-size: .86rem; }}
  .dc-leyenda b {{ color: {TINTA}; font-weight: 600; margin-left: .25rem; }}
  .dc-leyenda small {{ color: {TINTA_TENUE}; margin-left: .25rem; }}
  /* Red de sucursales. */
  .dc-red {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }}
  .dc-suc {{ background: {SUPERFICIE}; border: 1px solid {EJE}; border-radius: 6px; padding: 10px 12px 9px; min-width: 0; }}
  .dc-suc.foco {{ border-color: {ESTADO["critico"][0]}55; box-shadow: inset 0 3px 0 {ESTADO["critico"][0]}; }}
  .dc-suc .cab {{ display: flex; justify-content: space-between; align-items: baseline; gap: .5rem; }}
  .dc-suc .cab b {{ color: {TINTA}; font-size: 1rem; font-weight: 700; }}
  .dc-suc .cab span {{ color: {TINTA_TENUE}; font-size: .78rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .dc-suc .v {{ color: {TINTA}; font-family: {FUENTE_CIFRAS}; font-size: 1.35rem; font-weight: 600; margin-top: .1rem; }}
  .dc-suc svg.spark {{ display: block; width: 100%; height: 28px; margin: .2rem 0 .3rem; }}
  .dc-suc .est {{ display: flex; flex-wrap: wrap; gap: .15rem .8rem; font-size: .78rem; color: {TINTA_2}; }}
  /* ¿Por qué? de las alertas seleccionadas. */
  .dc-porque-lista {{ display: grid; gap: 8px; margin: .2rem 0 .6rem; }}
  .dc-porque {{ border-left: 3px solid {EJE}; padding: 4px 0 4px 12px; color: {TINTA_2}; font-size: .9rem; }}
  .dc-porque b {{ color: {TINTA}; font-weight: 600; }}
  .dc-porque ul {{ margin: .25rem 0 .2rem 1.1rem; padding: 0; }}
  .dc-pedido {{ color: {TINTA}; font-weight: 600; font-size: .86rem; }}
  .dc-estado {{ display: inline-flex; align-items: center; gap: .35rem; padding: .18rem .6rem; border-radius: 999px;
                font-size: .8rem; font-weight: 600; border: 1px solid; background: {SUPERFICIE}; }}
  /* Tarjetas sueltas (páginas que aún no pasan al nuevo sistema). */
  .dc-tarjeta {{ background: {SUPERFICIE}; border: 1px solid {BORDE}; border-radius: 8px; padding: 16px 18px 12px; height: 100%; }}
  .dc-tarjeta .t {{ color: {TINTA_2}; font-size: .84rem; font-weight: 600; display: flex; align-items: center; gap: .4rem; }}
  .dc-tarjeta .v {{ color: {TINTA}; font-size: 1.75rem; font-weight: 600; line-height: 1.2; margin-top: .3rem;
                    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .dc-tarjeta .d {{ font-size: .82rem; font-weight: 600; margin-top: .2rem; }}
  .dc-tarjeta .n {{ color: {TINTA_TENUE}; font-size: .78rem; margin-top: .15rem; }}
  .dc-tarjeta svg.spark {{ display: block; width: 100%; height: 38px; margin-top: .45rem; }}
  .dc-pie {{ color: {TINTA_TENUE}; font-size: .78rem; margin-top: 2.5rem; padding-top: .8rem; border-top: 1px solid {BORDE}; }}
  [data-testid="stMetric"] {{ background: {SUPERFICIE}; border: 1px solid {BORDE}; border-radius: 8px; padding: 12px 16px; }}
  [data-testid="stDataFrame"] {{ border: 1px solid {BORDE}; border-radius: 8px; }}
  div[data-baseweb="tab-list"] {{ gap: .3rem; }}
</style>
"""


def preparar(titulo_pestana: str) -> None:
    """Primera llamada de cada página: configuración, logo y estilos."""
    icono = MARCA / "icono_64.png"
    st.set_page_config(page_title=f"{titulo_pestana} · DATACORE", layout="wide",
                       page_icon=str(icono) if icono.exists() else "📦")
    logotipo = MARCA / "logotipo_oscuro.png"  # la barra lateral es marino
    if logotipo.exists():
        st.logo(str(logotipo), size="large", icon_image=str(icono))
    st.markdown(CSS, unsafe_allow_html=True)


# --- componentes ----------------------------------------------------------------------
def _corte_de_datos() -> str | None:
    """Fecha de corte del modelo activo (dd/mm/aaaa) para el sello del encabezado; None si la API no responde."""
    from datacore.dashboard import interfaz
    from datacore.dashboard.cliente import ErrorAPI
    try:
        fecha = ((interfaz.datos("/salud") or {}).get("modelo_activo") or {}).get("fecha_corte_datos")
    except ErrorAPI:
        return None
    return f"{fecha[8:10]}/{fecha[5:7]}/{fecha[:4]}" if fecha and len(fecha) >= 10 else None


def encabezado(titulo: str, descripcion: str = "", ceja: str = "NexaTech Solutions") -> None:
    """Encabezado tipo folio: banda marino con el título, el contexto y el sello del corte de datos."""
    texto = f"{ceja}. {descripcion}" if ceja and descripcion else (descripcion or ceja)
    corte = _corte_de_datos()
    sello = f'<span class="dc-sello"><span>Corte de datos</span>{corte}</span>' if corte else ""
    with st.container(key="dc_folio"):
        st.title(titulo, anchor=False)
        st.markdown(f'<div class="dc-folio"><span class="ctx">{escape(texto)}</span>{sello}</div>',
                    unsafe_allow_html=True)


def seccion(titulo: str, descripcion: str = "") -> None:
    st.markdown(f'<div class="dc-seccion"><b>{escape(titulo)}</b>'
                + (f'<span>{escape(descripcion)}</span>' if descripcion else "") + "</div>",
                unsafe_allow_html=True)


def estado(texto: str, nivel: str = "neutro") -> str:
    """HTML de una etiqueta de estado: color + ícono + texto (nunca solo color)."""
    color, icono = ESTADO[nivel]
    return (f'<span class="dc-estado" style="color:{color};border-color:{color}33">'
            f'<span aria-hidden="true">{icono}</span>{escape(texto)}</span>')


def _sparkline(valores: list[float], color: str = DESTACADO) -> str:
    puntos = [v for v in valores if v is not None]
    if len(puntos) < 2:
        return ""
    minimo, maximo = min(puntos), max(puntos)
    rango = (maximo - minimo) or 1
    n = len(puntos)
    coords = [(i * 100 / (n - 1), 34 - (v - minimo) / rango * 30) for i, v in enumerate(puntos)]
    linea = " ".join(f"{x:.2f},{y:.2f}" for x, y in coords)
    area = f"0,38 {linea} 100,38"
    ux, uy = coords[-1]
    return (f'<svg class="spark" viewBox="0 0 100 38" preserveAspectRatio="none" aria-hidden="true">'
            f'<polygon points="{area}" fill="{color}" fill-opacity=".08"/>'
            f'<polyline points="{linea}" fill="none" stroke="{color}" stroke-width="2" vector-effect="non-scaling-stroke"/>'
            f'<circle cx="{ux:.2f}" cy="{uy:.2f}" r="2.2" fill="{color}"/></svg>')


def tarjeta(titulo: str, valor: str, delta: float | None = None, delta_texto: str = "",
            nota: str = "", serie: list[float] | None = None, nivel: str | None = None,
            mayor_es_mejor: bool = True, alto: int | None = None) -> str:
    """HTML de una tarjeta de indicador. `delta` en % (con signo); `nivel` añade ícono de estado;
    `alto` (px) iguala la altura de las tarjetas de una misma fila."""
    icono = ""
    if nivel:
        color, simbolo = ESTADO[nivel]
        icono = f'<span style="color:{color}" aria-hidden="true">{simbolo}</span>'
    linea_delta = ""
    if delta is not None:
        bueno = (delta >= 0) == mayor_es_mejor
        color = ESTADO["bien"][0] if bueno else ESTADO["critico"][0]
        flecha = "▲" if delta >= 0 else "▼"
        linea_delta = (f'<div class="d" style="color:{color}">{flecha} {abs(delta):.1f} %'
                       f'<span style="color:{TINTA_TENUE};font-weight:500"> {escape(delta_texto)}</span></div>')
    estilo = f' style="min-height:{alto}px"' if alto else ""
    return (f'<div class="dc-tarjeta"{estilo}><div class="t">{icono}{escape(titulo)}</div>'
            f'<div class="v" title="{escape(valor)}">{escape(valor)}</div>{linea_delta}'
            + (f'<div class="n">{escape(nota)}</div>' if nota else "")
            + (_sparkline(serie) if serie else "") + "</div>")


def _linea_delta(delta: float | None, delta_texto: str, mayor_es_mejor: bool = True) -> str:
    if delta is None:
        return ""
    bueno = (delta >= 0) == mayor_es_mejor
    color = ESTADO["bien"][0] if bueno else ESTADO["critico"][0]
    flecha = "▲" if delta >= 0 else "▼"
    return (f'<div class="d" style="color:{color}">{flecha} {abs(delta):.1f} %'
            f'<span style="color:{TINTA_TENUE};font-weight:500"> {escape(delta_texto)}</span></div>')


def kpi(titulo: str, valor: str, delta: float | None = None, delta_texto: str = "", nota: str = "",
        serie: list[float] | None = None, nivel: str | None = None, mayor_es_mejor: bool = True) -> str:
    """HTML de una celda de indicador para `franja`. `nivel` antepone el ícono de estado."""
    icono = ""
    if nivel:
        color, simbolo = ESTADO[nivel]
        icono = f'<span style="color:{color}" aria-hidden="true">{simbolo}</span>'
    return (f'<div class="dc-kpi"><div class="t">{icono}{escape(titulo)}</div>'
            f'<div class="v" title="{escape(valor)}">{escape(valor)}</div>'
            + _linea_delta(delta, delta_texto, mayor_es_mejor)
            + (f'<div class="n">{escape(nota)}</div>' if nota else "")
            + (_sparkline(serie) if serie else "") + "</div>")


def franja(celdas: list[str], ligera: bool = False) -> None:
    """Indicadores en una sola pieza dividida por líneas finas, en lugar de tarjetas sueltas.
    `ligera` la dibuja sin caja, para usarla dentro de un bloque."""
    clase = "dc-franja ligera" if ligera else "dc-franja"
    st.markdown(f'<div class="{clase}">{"".join(celdas)}</div>', unsafe_allow_html=True)


def bloque(titulo: str, descripcion: str = ""):
    """Contenedor blanco con borde y su título; se usa con `with tema.bloque(...):`."""
    caja = st.container(border=True)
    caja.markdown(f'<div class="dc-bloque"><b>{escape(titulo)}</b>'
                  + (f'<span>{escape(descripcion)}</span>' if descripcion else "") + "</div>",
                  unsafe_allow_html=True)
    return caja


def barra_salud(segmentos: list[tuple[str, int, str]]) -> None:
    """Proporción de un total por estado: (etiqueta, conteo, nivel).
    La leyenda lleva ícono, texto, conteo y porcentaje (nunca solo color)."""
    total = sum(n for _, n, _ in segmentos) or 1
    partes = "".join(
        f'<div title="{escape(t)}: {n:,}" style="width:{n / total * 100:.2f}%;background:{ESTADO[nv][0]};'
        f'opacity:{.35 if nv == "bien" else .9}"></div>' for t, n, nv in segmentos)
    leyenda = "".join(
        f'<span><span style="color:{ESTADO[nv][0]}" aria-hidden="true">{ESTADO[nv][1]}</span> {escape(t)}'
        f'<b>{n:,}</b><small>{n / total * 100:.1f} %</small></span>' for t, n, nv in segmentos)
    st.markdown(f'<div class="dc-salud" role="img" aria-label="Pares por estado">{partes}</div>'
                f'<div class="dc-leyenda">{leyenda}</div>', unsafe_allow_html=True)


def red_sucursales(sucursales: list[dict]) -> None:
    """Cuadrícula de sucursales. Cada elemento: codigo, nombre, valor (texto), serie, estados
    [(nivel, conteo, texto)], foco (bool) y nota (texto a la derecha del código)."""
    celdas = []
    for s in sucursales:
        estados = "".join(
            f'<span><span style="color:{ESTADO[nv][0]}" aria-hidden="true">{ESTADO[nv][1]}</span> '
            f'{n:,} {escape(t)}</span>' for nv, n, t in s.get("estados", []))
        celdas.append(
            f'<div class="dc-suc{" foco" if s.get("foco") else ""}" title="{escape(s.get("nombre", ""))}">'
            f'<div class="cab"><b>{escape(s["codigo"])}</b><span>{escape(s.get("nota", ""))}</span></div>'
            f'<div class="v">{escape(s["valor"])}</div>{_sparkline(s.get("serie") or [])}'
            f'<div class="est">{estados}</div></div>')
    st.markdown(f'<div class="dc-red">{"".join(celdas)}</div>', unsafe_allow_html=True)


_ESTADOS_MX = None


def _contornos_mexico() -> list[dict]:
    """Contornos simplificados de los estados (datos/mexico_estados.json), cargados una sola vez."""
    global _ESTADOS_MX
    if _ESTADOS_MX is None:
        import json
        _ESTADOS_MX = json.loads((Path(__file__).parent / "datos" / "mexico_estados.json").read_text(encoding="utf8"))
    return _ESTADOS_MX


def mapa_red(puntos: list[dict], estados_con_sucursal: set[str], alto: int = 500, clave: str = "mapa_red") -> None:
    """Mapa de la red: cada punto es una sucursal (lon, lat, codigo, valor, hover, posicion, foco, nota_foco).
    El tamaño codifica el valor; las sucursales en foco llevan un anillo rojo y su conteo con ícono."""
    fig = go.Figure()
    for estado in _contornos_mexico():
        xs, ys = [], []
        for anillo in estado["anillos"]:
            xs += [x for x, _ in anillo] + [None]
            ys += [y for _, y in anillo] + [None]
        presente = estado["nombre"] in estados_con_sucursal
        fig.add_scatter(x=xs, y=ys, mode="lines", fill="toself", hoverinfo="skip", showlegend=False,
                        fillcolor=NIEBLA if presente else SUPERFICIE, line=dict(color=EJE, width=0.8))
    maximo = max((p["valor"] for p in puntos), default=1) or 1
    tamanos = [14 + 30 * (p["valor"] / maximo) ** 0.5 for p in puntos]
    foco = [p for p in puntos if p.get("foco")]
    if foco:
        fig.add_scatter(x=[p["lon"] for p in foco], y=[p["lat"] for p in foco], mode="markers", hoverinfo="skip",
                        showlegend=False, marker=dict(symbol="circle-open", color=ESTADO["critico"][0], line_width=2.5,
                                                      size=[t + 12 for t, p in zip(tamanos, puntos) if p.get("foco")]))
    fig.add_scatter(
        x=[p["lon"] for p in puntos], y=[p["lat"] for p in puntos], mode="markers+text", showlegend=False,
        marker=dict(size=tamanos, color=DESTACADO, opacity=.88, line=dict(color=SUPERFICIE, width=1.5)),
        text=[f"<b>{p['codigo']}</b>" + (f"<br>{ESTADO['critico'][1]} {p['nota_foco']}" if p.get("foco") else "")
              for p in puntos],
        textposition=[p.get("posicion", "top center") for p in puntos],
        textfont=dict(family=FUENTE_CIFRAS, size=13, color=TINTA),
        hovertext=[p["hover"] for p in puntos], hovertemplate="%{hovertext}<extra></extra>")
    fig.update_layout(hovermode="closest", margin=dict(l=0, r=0, t=0, b=0), plot_bgcolor=SUPERFICIE,
                      xaxis=dict(visible=False, range=[-104.6, -97.0]),
                      yaxis=dict(visible=False, range=[18.4, 26.3], scaleanchor="x", scaleratio=1.08))
    grafica(fig, alto=alto, clave=clave)


def fila_tarjetas(tarjetas: list[str]) -> None:
    for columna, html in zip(st.columns(len(tarjetas), gap="medium"), tarjetas):
        columna.markdown(html, unsafe_allow_html=True)


def pie() -> None:
    st.divider()
    st.caption("DATACORE · Datos simulados de NexaTech Solutions (empresa ficticia) — "
               "proyecto de estadía, Universidad Politécnica de Querétaro.")
