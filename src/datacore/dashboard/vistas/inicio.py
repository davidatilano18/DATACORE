"""Inicio: resumen ejecutivo. Página de referencia del sistema visual (ver tema.py).

Orden de lectura: indicadores del negocio, salud del inventario, red de sucursales y,
al final, el detalle (ingreso mensual y categorías) y el estado de la plataforma.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from datacore.dashboard import tema
from datacore.dashboard import interfaz

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Estados de cobertura de kpi.cobertura_inventario → (etiqueta, nivel de tema.ESTADO), en orden de gravedad.
ESTADOS_INVENTARIO = {
    "sin_existencia": ("Sin existencia", "critico"),
    "bajo_minimo": ("Bajo mínimo", "serio"),
    "exceso": ("Exceso", "aviso"),
    "sin_rotacion": ("Sin rotación", "neutro"),
    "normal": ("Normal", "bien"),
}
TIPOS_ALERTA = [("RIESGO_DESABASTO", "critico", "desabasto"), ("EXCESO_INVENTARIO", "aviso", "exceso"),
                ("SIN_ROTACION", "neutro", "sin rotación")]
SUCURSALES_EN_FOCO = 3  # las sucursales con más alertas pendientes llevan la franja roja

# Ubicación de cada sucursal para el mapa (solo presentación) y posición de su etiqueta. El mapa es
# esquemático: las tres sucursales de Querétaro y las dos de la Ciudad de México están a pocos kilómetros,
# así que se separan un poco para que cada punto se distinga.
UBICACION = {
    "QRO01": (-100.50, 20.28, "middle left"), "QRO02": (-100.80, 20.95, "top center"),
    "QRO03": (-99.95, 20.85, "middle right"), "CDMX01": (-99.13, 19.25, "bottom center"),
    "CDMX02": (-99.45, 19.65, "middle left"), "GDL01": (-103.39, 20.72, "middle left"),
    "MTY01": (-100.30, 25.75, "middle right"), "LEO01": (-101.68, 21.12, "middle left"),
    "SLP01": (-100.98, 22.15, "top right"), "PUE01": (-98.22, 19.03, "middle right"),
    "AGS01": (-102.29, 21.88, "top left"), "MOR01": (-101.19, 19.70, "bottom left"),
}


def _mensual(diaria: pd.DataFrame) -> pd.DataFrame:
    d = diaria.assign(mes=pd.to_datetime(diaria["fecha"]).dt.to_period("M").dt.to_timestamp())
    m = d.groupby("mes", as_index=False)[["ingreso", "tickets"]].sum()
    m["ticket_promedio"] = m["ingreso"] / m["tickets"]
    return m


def _variacion(actual: float, previo: float) -> float | None:
    return (actual / previo - 1) * 100 if previo else None


def _franja_negocio(m: pd.DataFrame, resumen: dict) -> None:
    ult, prev = m.tail(12), m.iloc[-24:-12]
    ingreso, tickets = ult["ingreso"].sum(), ult["tickets"].sum()
    ticket = ingreso / tickets if tickets else None
    ticket_prev = prev["ingreso"].sum() / prev["tickets"].sum() if len(prev) else None
    tema.franja([
        tema.kpi("Ingreso · últimos 12 meses", tema.mxn_corto(ingreso),
                 delta=resumen.get("crecimiento_pct"), delta_texto="vs. 12 meses previos",
                 serie=ult["ingreso"].tolist()),
        tema.kpi("Tickets · últimos 12 meses", tema.entero(tickets),
                 delta=_variacion(tickets, prev["tickets"].sum()), delta_texto="vs. 12 meses previos",
                 serie=ult["tickets"].tolist()),
        tema.kpi("Ticket promedio", tema.mxn(ticket),
                 delta=_variacion(ticket, ticket_prev) if ticket and ticket_prev else None,
                 delta_texto="vs. 12 meses previos", serie=ult["ticket_promedio"].tolist()),
        tema.kpi("Clientes activos", tema.entero(resumen.get("clientes_activos_12_meses")),
                 nota="con al menos una compra en 12 meses"),
    ])


def _salud_inventario(resumen: dict, alertas: pd.DataFrame) -> None:
    estados = interfaz.tabla("/inventario/estados")
    conteo = dict(zip(estados["estado"], estados["pares"])) if not estados.empty else {}
    total = sum(conteo.values())
    with tema.bloque("Salud del inventario", f"{total:,} pares sucursal-producto según su cobertura"):
        if conteo:
            tema.barra_salud([(etiqueta, int(conteo.get(clave, 0)), nivel)
                              for clave, (etiqueta, nivel) in ESTADOS_INVENTARIO.items()])
        por_tipo = alertas["tipo"].value_counts() if not alertas.empty else pd.Series(dtype=int)
        tema.franja([
            tema.kpi("Riesgo de desabasto", tema.entero(por_tipo.get("RIESGO_DESABASTO", 0)), nivel="critico",
                     nota="pares que no llegan a la próxima reposición"),
            tema.kpi("Exceso de inventario", tema.entero(por_tipo.get("EXCESO_INVENTARIO", 0)), nivel="aviso",
                     nota="cobertura pronosticada > 180 días"),
            tema.kpi("Sin rotación", tema.entero(por_tipo.get("SIN_ROTACION", 0)), nivel="neutro",
                     nota="sin ventas en 13 semanas"),
            tema.kpi("Incidencias abiertas", tema.entero(resumen.get("incidencias_abiertas")), nivel="serio",
                     nota="abiertas o en proceso"),
        ], ligera=True)


def _red_sucursales(desde: str, alertas: pd.DataFrame) -> None:
    catalogo = interfaz.tabla("/catalogos/sucursales")
    ventas = interfaz.tabla("/ventas/sucursales", desde=desde)
    if catalogo.empty or ventas.empty:
        return
    ingreso = dict(zip(ventas["codigo"], ventas["ingreso"]))
    pendientes = (alertas.groupby(["sucursal", "tipo"]).size() if not alertas.empty
                  else pd.Series(dtype=int))
    totales = {c: int(pendientes.get(c, pd.Series(dtype=int)).sum()) for c in catalogo["codigo"]}
    foco = set(sorted(totales, key=totales.get, reverse=True)[:SUCURSALES_EN_FOCO])
    tarjetas, puntos = [], []
    for _, s in catalogo.assign(ingreso=catalogo["codigo"].map(ingreso)).sort_values("ingreso", ascending=False).iterrows():
        diaria = interfaz.tabla("/ventas/diarias", desde=desde, id_sucursal=int(s["id_sucursal"]))
        serie = _mensual(diaria)["ingreso"].tolist() if not diaria.empty else []
        tarjetas.append({
            "codigo": s["codigo"], "nombre": s["nombre"], "valor": tema.mxn_corto(s["ingreso"]),
            "serie": serie, "foco": s["codigo"] in foco, "nota": s["nombre"],
            "estados": [(nivel, int(pendientes.get((s["codigo"], tipo), 0)), texto)
                        for tipo, nivel, texto in TIPOS_ALERTA],
        })
        if s["codigo"] in UBICACION:
            lon, lat, posicion = UBICACION[s["codigo"]]
            detalle = "<br>".join(f"{tema.ESTADO[nivel][1]} {n:,} {texto}" for nivel, n, texto in tarjetas[-1]["estados"])
            puntos.append({
                "codigo": s["codigo"], "lon": lon, "lat": lat, "posicion": posicion,
                "valor": float(s["ingreso"] or 0), "foco": s["codigo"] in foco,
                "nota_foco": f"{totales[s['codigo']]} alertas",
                "hover": f"<b>{s['codigo']}</b> {s['nombre']}<br>Ingreso 12 meses: {tema.mxn_corto(s['ingreso'])}<br>{detalle}",
            })
    tema.seccion("Red de sucursales",
                 f"El tamaño de cada punto es su ingreso de los últimos 12 meses. El anillo rojo marca las "
                 f"{SUCURSALES_EN_FOCO} sucursales con más alertas pendientes; el detalle de cada una está debajo del mapa.")
    if puntos:
        with st.container(border=True, key="dc_mapa"):
            tema.mapa_red(puntos, set(catalogo["estado"]))
            st.caption("Ubicación esquemática: las sucursales de una misma ciudad se separan para que se distingan.")
    st.write("")
    tema.red_sucursales(tarjetas)


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
    fig.update_layout(showlegend=False, margin=dict(r=48, t=12), yaxis=dict(tickprefix="$ ", tickformat="~s"))
    tema.grafica(fig, alto=320, clave="anual")


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
        tema.estado(f"Modelo #{modelo.get('id_modelo', '?')} con datos al {modelo.get('fecha_corte_datos', '?')}",
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
    tema.encabezado("Resumen ejecutivo", "Ventas, inventario y operación de las 12 sucursales.")
    m = _mensual(diaria)
    _franja_negocio(m, resumen)

    st.write("")
    alertas = interfaz.tabla("/alertas", limite=5000)
    _salud_inventario(resumen, alertas)

    desde = (corte - pd.DateOffset(months=12) + pd.Timedelta(days=1)).date().isoformat()
    _red_sucursales(desde, alertas)

    st.write("")
    izquierda, derecha = st.columns([1.55, 1], gap="medium")
    with izquierda:
        with tema.bloque("Ingreso mensual", "El año en curso contra los dos anteriores"):
            _grafica_anual(m)
    with derecha:
        with tema.bloque("Categorías", "Ingreso de los últimos 12 meses"):
            cat = interfaz.tabla("/ventas/categorias", desde=desde)
            if not cat.empty:
                _barras(cat.groupby("categoria", as_index=False)["ingreso"].sum(), "categoria", "ingreso", "categorias")

    tema.seccion("Estado de la plataforma")
    _plataforma(interfaz.datos("/salud") or {})
