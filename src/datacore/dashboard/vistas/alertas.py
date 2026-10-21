"""Alertas: priorización y seguimiento de inventario."""
import plotly.graph_objects as go
import streamlit as st
from datacore.dashboard import interfaz, tema
from datacore.dashboard.cliente import ClienteAPI

TIPOS = {'RIESGO_DESABASTO': ('Riesgo de desabasto', 'critico'), 'EXCESO_INVENTARIO': ('Exceso de inventario', 'aviso'), 'SIN_ROTACION': ('Sin rotación', 'neutro')}


def mostrar():
    tema.encabezado('Alertas', 'Prioriza la revisión de inventario y registra las alertas que el equipo ya atendió.')
    marco = interfaz.tabla('/alertas', limite=5000)
    tema.fila_tarjetas([tema.tarjeta(nombre, tema.entero((marco.tipo == tipo).sum() if not marco.empty else 0), nivel=nivel, nota='pendientes de revisión', alto=130) for tipo, (nombre, nivel) in TIPOS.items()])
    with st.expander('Cómo interpretar las alertas'):
        st.write('Riesgo de desabasto: existencia menor al percentil 90 de demanda durante el plazo de entrega más siete días. Exceso: cobertura pronosticada superior a 180 días. Sin rotación: existencia positiva, sin ventas en 13 semanas y pronóstico menor a 0.25 unidades semanales.')
    a, b, c, d = st.columns([1, 1, 1, 2])
    with a:
        tipo = st.selectbox('Tipo', ['Todos']+list(TIPOS), format_func=lambda x: TIPOS[x][0] if x in TIPOS else x)
    with b:
        sucursal = interfaz.sucursal()
    with c:
        categoria = st.selectbox('Categoría', ['Todas']+sorted(marco.categoria.unique()) if not marco.empty else ['Todas'])
    with d:
        buscar = st.text_input('Buscar SKU o producto')
    if marco.empty:
        st.info('No hay alertas pendientes.')
        return
    if tipo != 'Todos':
        marco = marco[marco.tipo == tipo]
    if sucursal is not None:
        marco = marco[marco.id_sucursal == sucursal]
    if categoria != 'Todas':
        marco = marco[marco.categoria == categoria]
    if buscar:
        marco = marco[marco.sku.str.contains(buscar, case=False, regex=False) | marco.producto.str.contains(buscar, case=False, regex=False)]
    tema.seccion('Alertas pendientes', 'Selecciona las filas revisadas para marcarlas como atendidas.')
    visibles = marco.copy().reset_index(drop=True)
    visibles['tipo'] = visibles.tipo.map(lambda x: tema.ESTADO[TIPOS[x][1]][1]+' '+TIPOS[x][0])
    columnas = [c for c in ['sucursal', 'sku', 'producto', 'tipo', 'existencia', 'demanda_estimada', 'dias_cobertura'] if c in visibles]
    config = {c: st.column_config.TextColumn(c.replace('_', ' ').capitalize()) for c in columnas}
    config['dias_cobertura'] = st.column_config.NumberColumn('Cobertura (días)', format='%.1f')
    for campo in columnas:
        config[campo] = st.column_config.Column(campo.replace('_', ' ').capitalize(), width='medium' if campo in ['producto', 'tipo'] else 'small')
    config['dias_cobertura'] = st.column_config.NumberColumn('Cobertura (días)', format='%.1f', width='small')
    config['sku'] = st.column_config.TextColumn('SKU', width='small')
    config['demanda_estimada'] = st.column_config.NumberColumn('Demanda', format='%.1f', width='small', help='Demanda esperada durante reposición (percentil 90)')
    seleccion = st.dataframe(visibles[columnas], hide_index=True, column_config=config, on_select='rerun', selection_mode='multi-row', key=f"alertas_pendientes_{st.session_state.get('revision_alertas', 0)}", width='stretch')
    filas = seleccion.selection.rows
    if st.button('Marcar como atendidas', disabled=not filas):
        for fila in filas:
            ClienteAPI().atender(int(marco.iloc[fila].id_alerta))
        interfaz.consultar.clear()
        st.session_state['revision_alertas'] = st.session_state.get('revision_alertas', 0)+1
        st.rerun()
    tema.seccion('Alertas por sucursal', 'La composición ayuda a distribuir la revisión entre sucursales.')
    grupos = marco.groupby(['sucursal', 'tipo']).size().unstack(fill_value=0)
    grupos = grupos.loc[grupos.sum(axis=1).sort_values().index]
    fig = go.Figure()
    for tipo, (nombre, nivel) in TIPOS.items():
        if tipo in grupos:
            fig.add_bar(y=grupos.index, x=grupos[tipo], orientation='h', name=tema.ESTADO[nivel][1]+' '+nombre, marker_color=tema.ESTADO[nivel][0], hovertemplate='%{y}: %{x} alertas<extra>'+nombre+'</extra>')
    fig.update_layout(barmode='stack', legend=dict(traceorder='normal'), xaxis_title='Alertas pendientes', hovermode='closest')
    tema.grafica(fig, alto=420)
