"""Alertas: priorización, pedido sugerido y seguimiento de inventario."""
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datacore.dashboard import interfaz, tema
from datacore.dashboard.cliente import ClienteAPI

TIPOS = {'RIESGO_DESABASTO': ('Riesgo de desabasto', 'critico'), 'EXCESO_INVENTARIO': ('Exceso de inventario', 'aviso'), 'SIN_ROTACION': ('Sin rotación', 'neutro')}


def _por_que(caja, seleccion):
    """Explicación completa de las alertas seleccionadas: sus 2 o 3 factores principales."""
    bloques = []
    for a in seleccion.itertuples():
        nivel = TIPOS[a.tipo][1]
        color, icono = tema.ESTADO[nivel]
        factores = ''.join(f'<li>{escape(f)}</li>' for f in str(a.motivos or '').split('; ') if f)
        pedido = ''
        if a.tipo == 'RIESGO_DESABASTO' and pd.notna(getattr(a, 'cantidad_sugerida', None)):
            pedido = (f'<div class="dc-pedido">Pedir {int(a.cantidad_sugerida):,} u a más tardar el '
                      f'{pd.Timestamp(a.fecha_limite):%d/%m/%Y} (demanda esperada en la reposición: '
                      f'{float(a.demanda_estimada):,.1f} u)</div>')
        bloques.append(f'<div class="dc-porque"><b><span style="color:{color}" aria-hidden="true">{icono}</span> '
                       f'{escape(a.sucursal)} · {escape(a.producto)}</b><ul>{factores}</ul>{pedido}</div>')
    caja.markdown('<div class="dc-porque-lista"><span class="dc-desc">¿Por qué?</span>' + ''.join(bloques) + '</div>',
                  unsafe_allow_html=True)


def mostrar():
    tema.encabezado('Alertas', 'Prioriza la revisión de inventario y registra las alertas que el equipo ya atendió.')
    marco = interfaz.tabla('/alertas', limite=5000)
    tema.franja([tema.kpi(nombre, tema.entero((marco.tipo == tipo).sum() if not marco.empty else 0), nivel=nivel, nota='pendientes de revisión') for tipo, (nombre, nivel) in TIPOS.items()])
    st.write('')
    with st.expander('Cómo interpretar las alertas'):
        st.write('Riesgo de desabasto: existencia menor a la demanda esperada durante el plazo de entrega más siete días, corregida si el producto estuvo agotado en las últimas cuatro semanas (en ese caso vendió menos de lo que se le pidió). Exceso: cobertura pronosticada superior a 180 días. Sin rotación: existencia positiva, sin ventas en 13 semanas y pronóstico menor a 0.25 unidades semanales.')
    caja = tema.bloque('Alertas pendientes', 'Filtra, revisa y selecciona las filas atendidas para marcarlas')
    a, b, c, d = caja.columns([1, 1, 1, 2])
    with a:
        tipo = st.selectbox('Tipo', ['Todos']+list(TIPOS), format_func=lambda x: TIPOS[x][0] if x in TIPOS else x)
    with b:
        sucursal = interfaz.sucursal()
    with c:
        categoria = st.selectbox('Categoría', ['Todas']+sorted(marco.categoria.unique()) if not marco.empty else ['Todas'])
    with d:
        buscar = st.text_input('Buscar SKU o producto')
    if marco.empty:
        caja.info('No hay alertas pendientes.')
        return
    if tipo != 'Todos':
        marco = marco[marco.tipo == tipo]
    if sucursal is not None:
        marco = marco[marco.id_sucursal == sucursal]
    if categoria != 'Todas':
        marco = marco[marco.categoria == categoria]
    if buscar:
        marco = marco[marco.sku.str.contains(buscar, case=False, regex=False) | marco.producto.str.contains(buscar, case=False, regex=False)]
    riesgo = marco[marco.tipo == 'RIESGO_DESABASTO']
    if not riesgo.empty and 'cantidad_sugerida' in riesgo:
        limite = pd.to_datetime(riesgo.fecha_limite)
        corte = pd.Timestamp(((interfaz.datos('/salud') or {}).get('modelo_activo') or {}).get('fecha_corte_datos')
                             or limite.min() - pd.Timedelta(days=1))
        urgentes = int((limite <= corte + pd.Timedelta(days=7)).sum())
        caja.markdown(
            f'<div class="dc-desc">Pedido sugerido para las {len(riesgo):,} alertas de desabasto filtradas: '
            f'<b>{int(riesgo.cantidad_sugerida.sum()):,} unidades</b>; {urgentes:,} deben pedirse en los próximos 7 días. '
            'Las más urgentes aparecen primero.</div>', unsafe_allow_html=True)
    visibles = marco.copy().reset_index(drop=True)
    visibles['tipo'] = visibles.tipo.map(lambda x: tema.ESTADO[TIPOS[x][1]][1]+' '+TIPOS[x][0])
    if 'fecha_limite' in visibles:
        visibles['fecha_limite'] = pd.to_datetime(visibles.fecha_limite)
    if 'motivos' in visibles:
        visibles['motivo'] = visibles.motivos.fillna('').str.split('; ').str[0]
    columnas = [c for c in ['sucursal', 'sku', 'producto', 'tipo', 'cantidad_sugerida', 'fecha_limite', 'existencia',
                            'dias_cobertura', 'motivo'] if c in visibles]
    config = {c: st.column_config.TextColumn(c.replace('_', ' ').capitalize()) for c in columnas}
    config['dias_cobertura'] = st.column_config.NumberColumn('Cobertura (días)', format='%.1f')
    for campo in columnas:
        config[campo] = st.column_config.Column(campo.replace('_', ' ').capitalize(), width='medium' if campo in ['producto', 'tipo'] else 'small')
    config['dias_cobertura'] = st.column_config.NumberColumn('Cobertura (días)', format='%.1f', width='small')
    config['sku'] = st.column_config.TextColumn('SKU', width='small')
    config['cantidad_sugerida'] = st.column_config.NumberColumn(
        'Pedir (u)', format='%d', width='small',
        help='Unidades para llegar al nivel objetivo: demanda esperada en entrega + 7 días más stock de seguridad (p99)')
    config['fecha_limite'] = st.column_config.DateColumn(
        'Pedir a más tardar', format='DD/MM/YYYY', width='medium',
        help='Último día para pedir y recibir antes de agotarse, al ritmo de venta esperado')
    config['motivo'] = st.column_config.TextColumn(
        'Motivo principal', width='large',
        help='El factor que más pesa en la alerta; selecciona la fila para ver la explicación completa')
    seleccion = caja.dataframe(visibles[columnas], hide_index=True, column_config=config, on_select='rerun', selection_mode='multi-row', key=f"alertas_pendientes_{st.session_state.get('revision_alertas', 0)}", width='stretch')
    filas = seleccion.selection.rows
    if filas and 'motivos' in marco:
        _por_que(caja, marco.iloc[filas[:5]])
        if len(filas) > 5:
            caja.caption(f'Se muestran 5 de las {len(filas)} filas seleccionadas.')
    if caja.button('Marcar como atendidas', disabled=not filas):
        for fila in filas:
            ClienteAPI().atender(int(marco.iloc[fila].id_alerta))
        interfaz.consultar.clear()
        st.session_state['revision_alertas'] = st.session_state.get('revision_alertas', 0)+1
        st.rerun()
    grupos = marco.groupby(['sucursal', 'tipo']).size().unstack(fill_value=0)
    grupos = grupos.loc[grupos.sum(axis=1).sort_values().index]
    fig = go.Figure()
    for tipo, (nombre, nivel) in TIPOS.items():
        if tipo in grupos:
            fig.add_bar(y=grupos.index, x=grupos[tipo], orientation='h', name=tema.ESTADO[nivel][1]+' '+nombre, marker_color=tema.ESTADO[nivel][0], hovertemplate='%{y}: %{x} alertas<extra>'+nombre+'</extra>')
    fig.update_layout(barmode='stack', legend=dict(traceorder='normal'), xaxis_title='Alertas pendientes', hovermode='closest')
    st.write('')
    with tema.bloque('Alertas por sucursal', 'La composición ayuda a repartir la revisión entre sucursales'):
        tema.grafica(fig, alto=420)
