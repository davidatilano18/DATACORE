"""Inicio: resumen ejecutivo. Página de referencia del sistema visual (ver tema.py)."""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from datacore.dashboard import tema
from datacore.dashboard import interfaz

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def _mensual(diaria: pd.DataFrame) -> pd.DataFrame:
    d = diaria.assign(mes=pd.to_datetime(diaria["fecha"]).dt.to_period("M").dt.to_timestamp())
    m = d.groupby("mes", as_index=False)[["ingreso", "tickets"]].sum()
    m["ticket_promedio"] = m["ingreso"] / m["tickets"]
    return m


def _variacion(actual: float, previo: float) -> float | None:
    return (actual / previo - 1) * 100 if previo else None


def _tarjetas_negocio(m: pd.DataFrame, resumen: dict) -> None:
    ult, prev = m.tail(12), m.iloc[-24:-12]
    ingreso, tickets = ult["ingreso"].sum(), ult["tickets"].sum()
    ticket = ingreso / tickets if tickets else None
    ticket_prev = prev["ingreso"].sum() / prev["tickets"].sum() if len(prev) else None
    alto = 162
    tema.fila_tarjetas([
        tema.tarjeta("Ingreso · últimos 12 meses", tema.mxn_corto(ingreso),
                     delta=resumen.get("crecimiento_pct"), delta_texto="vs. 12 meses previos",
                     serie=ult["ingreso"].tolist(), alto=alto),
        tema.tarjeta("Tickets · últimos 12 meses", tema.entero(tickets),
                     delta=_variacion(tickets, prev["tickets"].sum()), delta_texto="vs. 12 meses previos",
                     serie=ult["tickets"].tolist(), alto=alto),
        tema.tarjeta("Ticket promedio", tema.mxn(ticket),
                     delta=_variacion(ticket, ticket_prev) if ticket and ticket_prev else None,
                     delta_texto="vs. 12 meses previos", serie=ult["ticket_promedio"].tolist(), alto=alto),
        tema.tarjeta("Clientes activos", tema.entero(resumen.get("clientes_activos_12_meses")),
                     nota="con al menos una compra en 12 meses", alto=alto),
    ])


def _tarjetas_inventario(resumen: dict) -> None:
    alertas = interfaz.tabla("/alertas", limite=5000)
    conteo = alertas["tipo"].value_counts() if not alertas.empty else pd.Series(dtype=int)
    alto = 134
    tema.fila_tarjetas([
        tema.tarjeta("Riesgo de desabasto", tema.entero(conteo.get("RIESGO_DESABASTO", 0)), nivel="critico",
                     nota="pares que no llegan a la próxima reposición", alto=alto),
        tema.tarjeta("Exceso de inventario", tema.entero(conteo.get("EXCESO_INVENTARIO", 0)), nivel="aviso",
                     nota="cobertura pronosticada > 180 días", alto=alto),
        tema.tarjeta("Sin rotación", tema.entero(conteo.get("SIN_ROTACION", 0)), nivel="neutro",
                     nota="sin ventas en 13 semanas", alto=alto),
        tema.tarjeta("Incidencias abiertas", tema.entero(resumen.get("incidencias_abiertas")), nivel="serio",
                     nota="abiertas o en proceso", alto=alto),
    ])


def _grafica_anual(m: pd.DataFrame) -> None:
    """Un año protagonista y los anteriores como contexto: la comparación se lee sin leyenda."""
    m = m.assign(anio=m["mes"].dt.year, n=m["mes"].dt.month)
    anios = sorted(m["anio"].unique())
    fig = go.Figure()
    for anio in anios:
        g = m[m["anio"] == anio]
        actual = anio == anios[-1]
        color = tema.DESTACADO if actual else tema.CONTEXTO
        fig.add_scatter(x=[MESES[i - 1] for i in g["n"]], y=g["ingreso"], name=str(anio), mode="lines+markers",
                        line=dict(color=color, width=3 if actual else 2), marker=dict(size=7 if actual else 5),
                        hovertemplate=f"{anio}: $ %{{y:,.0f}}<extra></extra>")
        fig.add_annotation(x=MESES[g["n"].iloc[-1] - 1], y=g["ingreso"].iloc[-1], text=f"<b>{anio}</b>" if actual
                           else str(anio), showarrow=False, xanchor="left", xshift=10,
                           font=dict(color=tema.TINTA if actual else tema.TINTA_TENUE, size=12))
    fig.update_layout(showlegend=False, margin=dict(r=48), yaxis=dict(tickprefix="$ ", tickformat="~s"))
    tema.grafica(fig, alto=340, clave="anual")


def _barras(marco: pd.DataFrame, etiqueta: str, valor: str, clave: str) -> None:
    """Barras horizontales ordenadas, un solo color y el valor escrito al final de cada barra."""
    marco = marco.sort_values(valor)
    fig = go.Figure(go.Bar(x=marco[valor], y=marco[etiqueta], orientation="h", marker_color=tema.DESTACADO,
                           text=[tema.mxn_corto(v) for v in marco[valor]], textposition="outside",
                           textfont=dict(color=tema.TINTA_2, size=12), cliponaxis=False,
                           hovertemplate="%{y}: $ %{x:,.0f}<extra></extra>"))
    fig.update_layout(hovermode="closest", margin=dict(l=8, r=64, t=8),
                      xaxis=dict(visible=False), yaxis=dict(gridcolor="rgba(0,0,0,0)", tickfont=dict(color=tema.TINTA_2)))
    tema.grafica(fig, alto=max(260, 30 * len(marco)), clave=clave)


def _plataforma(salud: dict) -> None:
    etl, modelo = salud.get("ultimo_etl") or {}, salud.get("modelo_activo") or {}
    chips = [
        tema.estado("API y base de datos en línea", "bien") if salud.get("estado") == "ok"
        else tema.estado("Servicio degradado", "critico"),
        tema.estado(f"Último ETL {str(etl.get('fin', ''))[:16].replace('T', ' ')}", "bien" if etl.get("exitosa")
                    else "critico"),
        tema.estado(f"Modelo #{modelo.get('id_modelo', '?')} · datos al {modelo.get('fecha_corte_datos', '?')}",
                    "bien" if modelo else "aviso"),
    ]
    st.markdown(" ".join(chips), unsafe_allow_html=True)


def mostrar() -> None:
    resumen = interfaz.datos("/kpi/resumen") or {}
    diaria = interfaz.tabla("/ventas/diarias")
    if diaria.empty:
        st.info("Todavía no hay ventas cargadas.")
        return
    corte = pd.to_datetime(diaria["fecha"]).max()
    tema.encabezado("Resumen ejecutivo",
                    f"Ventas, inventario y operación de las 12 sucursales. Datos al {corte:%d/%m/%Y}.")
    m = _mensual(diaria)
    _tarjetas_negocio(m, resumen)

    tema.seccion("Salud del inventario", "Alertas generadas por el modelo de pronóstico; detalle en la página Alertas.")
    _tarjetas_inventario(resumen)

    tema.seccion("Ingreso mensual", "El año en curso contra los anteriores: noviembre y diciembre concentran la temporada alta.")
    _grafica_anual(m)

    desde = (corte - pd.DateOffset(months=12) + pd.Timedelta(days=1)).date().isoformat()
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        tema.seccion("Categorías · últimos 12 meses")
        cat = interfaz.tabla("/ventas/categorias", desde=desde)
        if not cat.empty:
            _barras(cat.groupby("categoria", as_index=False)["ingreso"].sum(), "categoria", "ingreso", "categorias")
    with derecha:
        tema.seccion("Sucursales · últimos 12 meses")
        suc = interfaz.tabla("/ventas/sucursales", desde=desde)
        if not suc.empty:
            _barras(suc, "codigo", "ingreso", "sucursales")

    tema.seccion("Estado de la plataforma")
    _plataforma(interfaz.datos("/salud") or {})
