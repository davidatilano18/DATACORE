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

FUENTE = '"Segoe UI", "Inter", system-ui, -apple-system, sans-serif'


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
    figura.update_layout(height=alto)
    st.plotly_chart(figura, width="stretch", key=clave,
                    config={"displayModeBar": False, "locale": "es"})


# --- CSS y página -----------------------------------------------------------------------
CSS = f"""
<style>
  html, body, [class*="css"] {{ font-family: {FUENTE}; }}
  .block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1400px; }}
  h1, h2, h3 {{ color: {TINTA}; letter-spacing: -0.01em; }}
  h1 {{ font-size: 2.05rem !important; font-weight: 750 !important; padding: .1rem 0 .3rem !important; }}
  [data-testid="stSidebar"] {{ border-right: 1px solid {BORDE}; }}
  [data-testid="stSidebarHeader"] {{ padding-top: 1.4rem; padding-bottom: .6rem; }}
  [data-testid="stSidebarHeader"] img, [data-testid="stLogo"] {{ height: 2.6rem !important; max-width: 13rem; }}
  [data-testid="stHeader"] {{ background: transparent; }}
  .dc-encabezado {{ margin: 0 0 1.4rem 0; }}
  .dc-ceja {{ color: {GUINDA}; font-size: .78rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }}
  .dc-titulo {{ color: {TINTA}; font-size: 2.05rem; font-weight: 750; line-height: 1.15; margin: .25rem 0 .35rem; }}
  .dc-desc {{ color: {TINTA_2}; font-size: .98rem; max-width: 70ch; }}
  .dc-seccion {{ margin: 1.9rem 0 .7rem; }}
  .dc-seccion b {{ color: {TINTA}; font-size: 1.12rem; font-weight: 700; }}
  .dc-seccion span {{ display: block; color: {TINTA_TENUE}; font-size: .86rem; margin-top: .15rem; }}
  .dc-tarjeta {{ background: {SUPERFICIE}; border: 1px solid {BORDE}; border-radius: 14px; padding: 16px 18px 12px;
                 box-shadow: 0 1px 2px rgba(27,42,74,.04); height: 100%; }}
  .dc-tarjeta .t {{ color: {TINTA_2}; font-size: .84rem; font-weight: 600; display: flex; align-items: center; gap: .4rem; }}
  .dc-tarjeta .v {{ color: {TINTA}; font-size: 1.85rem; font-weight: 750; line-height: 1.2; margin-top: .3rem;
                    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .dc-tarjeta .d {{ font-size: .82rem; font-weight: 600; margin-top: .2rem; }}
  .dc-tarjeta .n {{ color: {TINTA_TENUE}; font-size: .78rem; margin-top: .15rem; }}
  .dc-tarjeta svg.spark {{ display: block; width: 100%; height: 38px; margin-top: .45rem; }}
  .dc-estado {{ display: inline-flex; align-items: center; gap: .35rem; padding: .18rem .6rem; border-radius: 999px;
                font-size: .8rem; font-weight: 600; border: 1px solid; background: {SUPERFICIE}; }}
  .dc-pie {{ color: {TINTA_TENUE}; font-size: .78rem; margin-top: 2.5rem; padding-top: .8rem; border-top: 1px solid {BORDE}; }}
  [data-testid="stMetric"] {{ background: {SUPERFICIE}; border: 1px solid {BORDE}; border-radius: 14px; padding: 12px 16px; }}
  [data-testid="stDataFrame"] {{ border: 1px solid {BORDE}; border-radius: 12px; }}
  div[data-baseweb="tab-list"] {{ gap: .3rem; }}
</style>
"""


def preparar(titulo_pestana: str) -> None:
    """Primera llamada de cada página: configuración, logo y estilos."""
    icono = MARCA / "icono_64.png"
    st.set_page_config(page_title=f"{titulo_pestana} · DATACORE", layout="wide",
                       page_icon=str(icono) if icono.exists() else "📦")
    logotipo = MARCA / "logotipo.png"
    if logotipo.exists():
        st.logo(str(logotipo), size="large", icon_image=str(icono))
    st.markdown(CSS, unsafe_allow_html=True)


# --- componentes ----------------------------------------------------------------------
def encabezado(titulo: str, descripcion: str = "", ceja: str = "NexaTech Solutions") -> None:
    st.markdown(f'<div class="dc-ceja">{escape(ceja)}</div>', unsafe_allow_html=True)
    st.title(titulo, anchor=False)
    if descripcion:
        st.markdown(f'<div class="dc-desc dc-encabezado">{escape(descripcion)}</div>', unsafe_allow_html=True)


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


def fila_tarjetas(tarjetas: list[str]) -> None:
    for columna, html in zip(st.columns(len(tarjetas), gap="medium"), tarjetas):
        columna.markdown(html, unsafe_allow_html=True)


def pie() -> None:
    st.divider()
    st.caption("DATACORE · Datos simulados de NexaTech Solutions (empresa ficticia) — "
               "proyecto de estadía, Universidad Politécnica de Querétaro.")
