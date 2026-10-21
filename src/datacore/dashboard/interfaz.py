"""Presentación y consultas compartidas por las páginas."""

from datetime import timedelta
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from datacore.dashboard.cliente import ClienteAPI, ErrorAPI

PALETA = ["#176B87", "#36A3A8", "#D99A35", "#7959A5", "#D46764"]
PIE = "Datos simulados de NexaTech Solutions (empresa ficticia) — proyecto de estadía UPQ"


@st.cache_data(ttl=300)
def consultar(ruta, parametros, url, huella_clave):
    return ClienteAPI().obtener(ruta, **parametros)


def datos(ruta, **parametros):
    # La clave participa mediante su huella para aislar la caché entre credenciales.
    import hashlib
    clave = os.getenv("DATACORE_API_KEY", "")
    return consultar(ruta, parametros, os.getenv("DATACORE_API_URL", "http://127.0.0.1:8000"),
                     hashlib.sha256(clave.encode()).hexdigest())


def tabla(ruta, **parametros):
    return pd.DataFrame(datos(ruta, **parametros))


def moneda(valor):
    return f"$ {valor:,.2f} MXN" if valor is not None else "Sin datos"


def sucursal():
    opciones = {"Todas": None}
    opciones.update({f"{s['codigo']} · {s['nombre']}": s['id_sucursal']
                     for s in datos('/catalogos/sucursales')})
    return opciones[st.selectbox("Sucursal", list(opciones))]


def grafica(marco, tipo, x, y, **opciones):
    if marco.empty:
        st.info("No hay datos para los filtros seleccionados.")
        return
    figura = getattr(px, tipo)(marco, x=x, y=y, color_discrete_sequence=PALETA, **opciones)
    figura.update_layout(template="plotly_white", legend_title_text="", separators=".,")
    if y == 'ingreso' or (isinstance(y, list) and 'ingreso' in y):
        figura.update_yaxes(tickprefix='$ ', tickformat=',.2f', ticksuffix=' MXN')
    if 'ticket_promedio' in marco.columns:
        figura.update_traces(hovertemplate='Sucursal: %{x}<br>Ingreso: $ %{y:,.2f} MXN'
                             '<br>Ticket promedio: $ %{customdata[0]:,.2f} MXN<extra></extra>')
    st.plotly_chart(figura, width="stretch")


def inicio():
    st.title("Resumen ejecutivo")
    resumen = datos('/kpi/resumen') or {}
    tarjetas = [("Ingreso total", "ingreso_total", True),
                ("Ingreso últimos 12 meses", "ingreso_ultimos_12_meses", True),
                ("Tickets", "tickets", False), ("Ticket promedio", "ticket_promedio", True),
                ("Clientes activos · 12 meses", "clientes_activos_12_meses", False),
                ("Pares sin existencia", "pares_sin_existencia", False),
                ("Pares en exceso", "pares_exceso", False),
                ("Pares sin rotación", "pares_sin_rotacion", False),
                ("Incidencias abiertas", "incidencias_abiertas", False)]
    for posicion, (titulo, campo, es_moneda) in enumerate(tarjetas):
        if posicion % 3 == 0:
            columnas = st.columns(3)
        valor = resumen.get(campo)
        delta = resumen.get('crecimiento_pct') if campo == 'ingreso_ultimos_12_meses' else None
        columnas[posicion % 3].metric(titulo, moneda(valor) if es_moneda else
                                     (f"{valor:,.0f}" if valor is not None else "Sin datos"),
                                     delta=f"{delta:.2f} % vs. 12 meses previos" if delta is not None else None)
    st.subheader("Ventas mensuales")
    ventas = tabla('/ventas/diarias')
    if not ventas.empty:
        ventas['mes'] = pd.to_datetime(ventas.fecha).dt.to_period('M').dt.to_timestamp()
        grafica(ventas.groupby('mes', as_index=False).ingreso.sum(), 'line', 'mes', 'ingreso',
                labels={'ingreso': 'Ingreso (MXN)', 'mes': 'Mes'})
    st.subheader("Estado de la plataforma")
    salud = datos('/salud')
    etl, modelo = salud.get('ultimo_etl') or {}, salud.get('modelo_activo') or {}
    c1, c2, c3 = st.columns(3)
    c1.metric("API / base de datos", f"{salud.get('estado', '?')} / {salud.get('base_de_datos', '?')}")
    c2.metric("Último ETL", str(etl.get('fin', 'sin datos'))[:16].replace('T', ' '),
              delta="exitoso" if etl.get('exitosa') else "con fallas", delta_color="normal" if etl.get('exitosa') else "inverse")
    c3.metric("Modelo activo", f"#{modelo.get('id_modelo', '?')} · corte {modelo.get('fecha_corte_datos', '?')}")


def ventas():
    st.title("Ventas")
    serie = tabla('/ventas/diarias')
    if serie.empty:
        st.info("No hay ventas disponibles.")
        return
    minimo, maximo = pd.to_datetime(serie.fecha).min().date(), pd.to_datetime(serie.fecha).max().date()
    rango = st.date_input("Rango de fechas", (max(minimo, maximo-timedelta(days=364)), maximo),
                          min_value=minimo, max_value=maximo)
    identificador = sucursal()
    if len(rango) != 2:
        st.info("Selecciona ambas fechas.")
        return
    desde, hasta = rango
    diaria = tabla('/ventas/diarias', desde=desde.isoformat(), hasta=hasta.isoformat(), id_sucursal=identificador)
    st.subheader("Serie diaria y media móvil de 7 días")
    if not diaria.empty:
        diaria['fecha'] = pd.to_datetime(diaria.fecha)
        diaria = diaria.set_index('fecha').reindex(pd.date_range(desde, hasta, name='fecha'), fill_value=0).reset_index()
        diaria['Media móvil 7 días'] = diaria.ingreso.rolling(7, min_periods=1).mean()
        grafica(diaria, 'line', 'fecha', ['ingreso', 'Media móvil 7 días'], labels={'value': 'Ingreso (MXN)'})
    st.subheader("Ventas por sucursal")
    suc = tabla('/ventas/sucursales', desde=desde.isoformat(), hasta=hasta.isoformat())
    if identificador is not None and not suc.empty:
        suc = suc[suc.id_sucursal == identificador]
    grafica(suc, 'bar', 'codigo', 'ingreso', hover_data=['ticket_promedio'],
            labels={'ingreso': 'Ingreso (MXN)', 'codigo': 'Sucursal', 'ticket_promedio': 'Ticket promedio (MXN)'})
    st.subheader("Mezcla mensual por categoría")
    st.caption("Todas las sucursales. La API filtra meses completos; se incluyen los meses que intersectan el rango.")
    categorias = tabla('/ventas/categorias', desde=desde.replace(day=1).isoformat(), hasta=hasta.isoformat())
    grafica(categorias, 'area', 'mes', 'ingreso', color='categoria', labels={'ingreso': 'Ingreso (MXN)'})
    st.subheader("Clasificación ABC histórica · todas las sucursales")
    clase = st.selectbox("Clase ABC", ['Todas', 'A', 'B', 'C'])
    abc = tabla('/productos/abc', clase=None if clase == 'Todas' else clase, limite=5000)
    st.dataframe(abc.style.format({'ingreso': moneda}) if not abc.empty else abc, hide_index=True)


def inventario():
    st.title("Inventario")
    identificador = sucursal()
    st.subheader("Pares por estado")
    grafica(tabla('/inventario/estados', id_sucursal=identificador), 'bar', 'estado', 'pares')
    estado = st.selectbox("Estado", ['Todos', 'sin_existencia', 'bajo_minimo', 'normal', 'exceso', 'sin_rotacion'])
    st.subheader("Cobertura de inventario")
    st.caption("Cobertura basada en ventas de los últimos 90 días. Cobertura vacía: existencia sin ventas.")
    st.dataframe(tabla('/inventario/cobertura', estado=None if estado == 'Todos' else estado,
                       id_sucursal=identificador, limite=5000), hide_index=True)
    st.subheader("Tasa mensual de desabasto")
    marco = tabla('/inventario/desabasto', id_sucursal=identificador)
    if not marco.empty:
        marco['Desabasto (%)'] = marco.tasa_desabasto * 100
    grafica(marco, 'line', 'mes', 'Desabasto (%)')


def alertas():
    st.title("Alertas")
    st.caption("RIESGO_DESABASTO: existencia menor al percentil 90 de demanda durante entrega + 7 días. "
               "EXCESO_INVENTARIO: cobertura pronosticada mayor a 180 días. "
               "SIN_ROTACION: existencia positiva, sin ventas en 13 semanas y pronóstico menor a 0.25 unidades/semana.")
    identificador = sucursal()
    tipo = st.selectbox("Tipo de alerta", ['Todos', 'RIESGO_DESABASTO', 'EXCESO_INVENTARIO', 'SIN_ROTACION'])
    marco = tabla('/alertas', tipo=None if tipo == 'Todos' else tipo, id_sucursal=identificador, limite=5000)
    st.subheader("Alertas pendientes")
    if marco.empty:
        st.info("No hay alertas pendientes para estos filtros.")
        return
    grafica(marco.groupby('tipo').size().reset_index(name='total'), 'bar', 'tipo', 'total')
    st.dataframe(marco, hide_index=True)
    opciones = {f"{a['id_alerta']} · {a['sucursal']} · {a['sku']} · {a['tipo']}": a['id_alerta']
                for a in marco.to_dict('records')}
    seleccion = st.selectbox("Alerta que se atenderá", list(opciones))
    if st.button("Marcar como atendida"):
        ClienteAPI().atender(opciones[seleccion])
        consultar.clear()
        st.rerun()


def pronostico():
    st.title("Pronóstico")
    buscar = st.text_input("Buscar producto por nombre o SKU")
    productos = datos('/catalogos/productos', buscar=buscar or None, limite=5000)
    if not productos:
        st.info("No se encontraron productos.")
        return
    opciones = {f"{p['sku']} · {p['nombre']}": p['id_producto'] for p in productos}
    producto = opciones[st.selectbox("Producto", list(opciones))]
    identificador = sucursal()
    historia = tabla('/ventas/semanales', id_producto=producto, id_sucursal=identificador)
    futuro = tabla('/pronosticos', id_producto=producto, id_sucursal=identificador)
    st.subheader("Historia semanal y pronóstico de 4 semanas")
    figura = go.Figure()
    if not historia.empty:
        historia['semana_inicio'] = pd.to_datetime(historia.semana_inicio)
        ultima = historia.semana_inicio.max()
        historia = historia.set_index('semana_inicio').reindex(pd.date_range(
            ultima-timedelta(weeks=51), ultima, freq='7D', name='semana_inicio'), fill_value=0).reset_index()
        figura.add_scatter(x=historia.semana_inicio, y=historia.unidades, name='Historia', line_color=PALETA[0])
    if not futuro.empty:
        figura.add_scatter(x=futuro.semana_inicio, y=futuro.limite_inferior, line_width=0,
                           showlegend=False, hoverinfo='skip')
        figura.add_scatter(x=futuro.semana_inicio, y=futuro.limite_superior, fill='tonexty',
                           fillcolor='rgba(54,163,168,0.22)', line_width=0, name='Intervalo 80 %')
        figura.add_scatter(x=futuro.semana_inicio, y=futuro.demanda_estimada, name='Pronóstico', line_color=PALETA[1])
    else:
        st.info("No hay pronóstico publicado para esta selección.")
    figura.update_layout(template='plotly_white', yaxis_title='Unidades', xaxis_title='Semana')
    st.plotly_chart(figura, width='stretch')
    if identificador is None:
        st.caption("La API suma los límites por sucursal; el intervalo agregado no garantiza cobertura conjunta del 80 %.")
    st.subheader("Modelo activo y comparación con media móvil")
    modelo = datos('/modelo')
    st.write(f"Versión {modelo['version']} · Corte {modelo['fecha_corte_datos']} · {modelo['algoritmo']}")
    filas = []
    for horizonte, metricas in modelo.get('metricas', {}).items():
        if horizonte not in ['h1', 'h2', 'h3', 'h4']:
            continue
        filas.append({'Horizonte': horizonte, 'WAPE par (%)': metricas['wape_par']*100,
                      'WAPE media móvil 8 semanas, par (%)': metricas['wape_media_movil_8']*100,
                      'WAPE producto-semana (%)': metricas['wape_producto_semana']*100,
                      'Sesgo (%)': metricas['sesgo']*100})
    st.dataframe(pd.DataFrame(filas).round(2), hide_index=True)
    st.caption("Backtest global del modelo activo. Menor WAPE es mejor; la comparación con media móvil corresponde al par sucursal-producto.")


def calidad():
    st.title("Calidad y operación")
    st.subheader("Hallazgos de la última carga")
    marco = tabla('/calidad/ultima-carga')
    grafica(marco, 'bar', 'regla', 'conteo', color='accion', barmode='group')
    st.dataframe(marco, hide_index=True)
    st.subheader("Últimas ejecuciones del ETL")
    st.dataframe(tabla('/etl/ejecuciones', limite=50), hide_index=True)
    st.subheader("Incidencias mensuales por tipo")
    grafica(tabla('/incidencias/mensuales'), 'line', 'mes', 'total', color='tipo')


def ejecutar(pagina):
    st.set_page_config(page_title=f"DATACORE · {pagina}", layout="wide")
    try:
        {'Inicio': inicio, 'Ventas': ventas, 'Inventario': inventario, 'Alertas': alertas,
         'Pronóstico': pronostico, 'Calidad y operación': calidad}[pagina]()
    except ErrorAPI as exc:
        st.error(str(exc))
    finally:
        st.divider()
        st.caption(PIE)
