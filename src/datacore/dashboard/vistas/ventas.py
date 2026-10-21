"""Ventas: evolución, mezcla comercial y contribución de productos."""
from datetime import timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from datacore.dashboard import interfaz, tema
from datacore.dashboard.vistas.inicio import _barras, _variacion


DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


def _colores_categoria() -> dict[str, str]:
    """Color fijo por categoría según su ingreso en TODO el historial (no cambia con los filtros):
    las 7 principales toman SERIES en orden; el resto va a "Otras" en gris de contexto."""
    total = interfaz.tabla('/ventas/categorias').groupby('categoria').ingreso.sum().sort_values(ascending=False)
    colores = {nombre: tema.SERIES[i] for i, nombre in enumerate(total.index[:7])}
    colores['Otras'] = tema.CONTEXTO
    return colores


def _mezcla_categorias(cat: pd.DataFrame) -> None:
    colores = _colores_categoria()
    cat = cat.assign(categoria=cat.categoria.where(cat.categoria.isin(colores), 'Otras'))
    orden = [c for c in colores if c in set(cat.categoria)]  # orden fijo: por peso histórico, "Otras" al final
    if cat.mes.nunique() < 3:
        # Uno o dos meses: una barra por categoría lee mejor que una o dos columnas apiladas.
        parte = cat.groupby('categoria').ingreso.sum()
        parte = (parte / parte.sum() * 100).reindex(orden)
        fig = go.Figure(go.Bar(x=parte.values, y=parte.index, orientation='h',
                               marker_color=[colores[c] for c in parte.index],
                               text=[f'{v:.1f} %' for v in parte.values], textposition='outside',
                               textfont=dict(color=tema.TINTA_2), cliponaxis=False,
                               hovertemplate='%{y}: %{x:.1f} %<extra></extra>'))
        fig.update_layout(hovermode='closest', margin=dict(r=56), xaxis=dict(visible=False),
                          yaxis=dict(autorange='reversed', tickfont=dict(color=tema.TINTA_2)))
        tema.grafica(fig, alto=max(260, 34 * len(parte)), clave='mezcla')
        return
    mezcla = cat.pivot_table(index='mes', columns='categoria', values='ingreso', aggfunc='sum', fill_value=0)
    mezcla = mezcla.div(mezcla.sum(axis=1), axis=0) * 100
    fig = go.Figure()
    for nombre in orden:
        fig.add_bar(x=pd.to_datetime(mezcla.index), y=mezcla[nombre], name=nombre, marker_color=colores[nombre],
                    hovertemplate='%{y:.1f} %<extra>' + nombre + '</extra>')
    fig.update_layout(barmode='stack', bargap=0.15, legend=dict(traceorder='normal'),
                      yaxis=dict(title='Participación (%)', ticksuffix=' %', range=[0, 100]))
    fig.update_xaxes(tickformat='%b %Y')
    tema.grafica(fig, clave='mezcla')


def _patron_semanal(d: pd.DataFrame) -> None:
    """Días en su orden natural (lunes a domingo): son una escala ordinal, no un ranking."""
    patron = d.groupby(d.fecha.dt.dayofweek).ingreso.mean().reindex(range(7))
    fig = go.Figure(go.Bar(x=DIAS, y=patron.values, marker_color=tema.DESTACADO,
                           text=[tema.mxn_corto(v) for v in patron.values], textposition='outside',
                           textfont=dict(color=tema.TINTA_2, size=12), cliponaxis=False,
                           hovertemplate='%{x}: $ %{y:,.0f}<extra></extra>'))
    fig.update_layout(hovermode='closest', yaxis=dict(visible=False), margin=dict(t=24))
    tema.grafica(fig, alto=300, clave='patron')


def mostrar():
    tema.encabezado("Ventas", "Compara el periodo, identifica patrones y revisa qué productos sostienen el ingreso.")
    base = interfaz.tabla('/ventas/diarias')
    if base.empty:
        st.info("No hay ventas disponibles.")
        return
    corte = pd.to_datetime(base.fecha).max().date()
    izquierda, derecha = st.columns([4, 1])
    with izquierda:
        periodo = st.radio("Periodo", ['Últimos 30 días', '90 días', '12 meses', 'Año 2025', 'Todo', 'Personalizado'], horizontal=True)
        dias = {'Últimos 30 días': 30, '90 días': 90, '12 meses': 365}
        desde = corte - timedelta(days=dias.get(periodo, 365)-1)
        hasta = corte
        if periodo == 'Año 2025':
            desde, hasta = pd.Timestamp('2025-01-01').date(), pd.Timestamp('2025-12-31').date()
        if periodo == 'Todo':
            desde = pd.to_datetime(base.fecha).min().date()
        if periodo == 'Personalizado':
            rango = st.date_input('Rango personalizado', (desde, hasta))
            if len(rango) != 2:
                st.info('Selecciona ambas fechas.')
                return
            desde, hasta = rango
    with derecha:
        sucursal = interfaz.sucursal()
    duracion = (hasta-desde).days+1
    completa = interfaz.tabla('/ventas/diarias', desde=(desde-timedelta(days=duracion)).isoformat(), hasta=hasta.isoformat(), id_sucursal=sucursal)
    if completa.empty:
        st.info('No hay ventas en este periodo.')
        return
    completa['fecha'] = pd.to_datetime(completa.fecha)
    completa = completa.set_index('fecha').reindex(pd.date_range(desde-timedelta(days=duracion), hasta, name='fecha'), fill_value=0).reset_index()
    d, previo = completa.tail(duracion).copy(), completa.head(duracion)
    d['ticket_promedio'] = d.ingreso.div(d.tickets.where(d.tickets.ne(0))).fillna(0)
    tarjetas = []
    for titulo, campo in [('Ingreso', 'ingreso'), ('Tickets', 'tickets'), ('Ticket promedio', 'ticket_promedio'), ('Unidades', 'unidades')]:
        actual = d.ingreso.sum()/d.tickets.sum() if campo == 'ticket_promedio' and d.tickets.sum() else d[campo].sum()
        anterior = previo.ingreso.sum()/previo.tickets.sum() if campo == 'ticket_promedio' and previo.tickets.sum() else previo[campo].sum()
        valor = {'ingreso': tema.mxn_corto, 'ticket_promedio': tema.mxn}.get(campo, tema.entero)(actual)
        tarjetas.append(tema.tarjeta(titulo, valor, delta=_variacion(actual, anterior), delta_texto='vs. periodo anterior', serie=d[campo].tolist(), alto=160))
    tema.fila_tarjetas(tarjetas)
    tema.seccion('Ingreso diario y tendencia', 'La media de siete días permite distinguir la tendencia del movimiento diario.')
    fig = go.Figure(go.Bar(x=d.fecha, y=d.ingreso, name='Ingreso diario', marker_color=tema.CONTEXTO, hovertemplate='$ %{y:,.0f}<extra>Ingreso diario</extra>'))
    media = d.ingreso.rolling(7, min_periods=1).mean()
    fig.add_scatter(x=d.fecha, y=media, name='Media móvil 7 días', line_color=tema.DESTACADO, hovertemplate='$ %{y:,.0f}<extra>Media 7 días</extra>')
    fig.add_annotation(x=d.fecha.iloc[-1], y=media.iloc[-1], text='Media 7 días', showarrow=False, yshift=15, font_color=tema.TINTA)
    fig.update_yaxes(title='Ingreso (MXN)', tickprefix='$ ')
    fig.update_xaxes(tickformat='%d/%m')
    tema.grafica(fig)
    izq, der = st.columns(2)
    with izq:
        tema.seccion('Patrón semanal', 'Ingreso promedio por día de la semana; compara días con igual exposición.')
        _patron_semanal(d)
    with der:
        tema.seccion('Ventas por sucursal', 'Sucursales ordenadas por ingreso dentro del periodo seleccionado.')
        suc = interfaz.tabla('/ventas/sucursales', desde=desde.isoformat(), hasta=hasta.isoformat())
        if sucursal is not None:
            suc = suc[suc.id_sucursal == sucursal]
        _barras(suc, 'codigo', 'ingreso', 'ventas_sucursal')
    tema.seccion('Mezcla por categoría', 'Participación en el ingreso. Cada categoría conserva su color en todos los filtros; '
                 'las de menor peso histórico se agrupan en "Otras".')
    cat = interfaz.tabla('/ventas/categorias', desde=desde.isoformat(), hasta=hasta.isoformat(), id_sucursal=sucursal)
    if not cat.empty:
        _mezcla_categorias(cat)
    tema.seccion('Clasificación ABC histórica', 'Todas las sucursales y todo el historial. El acumulado muestra la concentración del ingreso.')
    buscar = st.text_input('Buscar SKU o producto')
    abc = interfaz.tabla('/productos/abc', limite=5000)
    if not abc.empty:
        if buscar:
            abc = abc[abc.astype(str).apply(lambda c: c.str.contains(buscar, case=False, regex=False)).any(axis=1)]
        abc['clase'] = abc.clase.map(lambda x: [x])
        visibles = [c for c in abc if not c.startswith('id_')]
        configuracion = {c: st.column_config.TextColumn(c.replace('_', ' ').capitalize()) for c in visibles}
        configuracion['clase'] = st.column_config.MultiselectColumn('Clase ABC', options=['A', 'B', 'C'], color=tema.CONTEXTO)
        configuracion['sku'] = st.column_config.TextColumn('SKU')
        configuracion['nombre'] = st.column_config.TextColumn('Producto')
        configuracion['categoria'] = st.column_config.TextColumn('Categoría')
        configuracion['ingreso'] = st.column_config.NumberColumn('Ingreso', format='$ %.2f')
        for c in visibles:
            if 'acumulad' in c:
                configuracion[c] = st.column_config.ProgressColumn('Ingreso acumulado (%)', min_value=0, max_value=100, format='%.1f %%')
        st.dataframe(abc[visibles], hide_index=True, column_config=configuracion, width='stretch')
