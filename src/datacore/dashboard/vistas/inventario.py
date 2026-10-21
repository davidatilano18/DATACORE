"""Inventario: disponibilidad y cobertura por sucursal."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datacore.dashboard import interfaz, tema

ESTADOS = {'sin_existencia': ('Sin existencia', 'critico'), 'bajo_minimo': ('Bajo mínimo', 'serio'), 'exceso': ('Exceso', 'aviso'), 'sin_rotacion': ('Sin rotación', 'neutro'), 'normal': ('Normal', 'bien')}


def mostrar():
    tema.encabezado('Inventario', 'Localiza faltantes, exceso y productos inmovilizados antes de decidir la reposición.')
    marco = interfaz.tabla('/inventario/cobertura', limite=5000)
    total = len(marco)
    tema.fila_tarjetas([tema.tarjeta(nombre, tema.entero((marco.estado == estado).sum() if total else 0), nivel=nivel, nota=tema.pct(100*(marco.estado == estado).sum()/total) + ' del total' if total else 'Sin datos', alto=130) for estado, (nombre, nivel) in ESTADOS.items()])
    tema.seccion('Distribución por sucursal', 'Cada segmento representa pares sucursal-producto; revisa dónde se concentran los faltantes.')
    if total:
        grupos = marco.groupby(['sucursal', 'estado']).size().unstack(fill_value=0)
        grupos = grupos.loc[grupos.sum(axis=1).sort_values().index]
        fig = go.Figure()
        for estado, (nombre, nivel) in ESTADOS.items():
            valores = grupos[estado] if estado in grupos else pd.Series(0, index=grupos.index)
            fig.add_bar(y=grupos.index, x=valores, orientation='h', name=tema.ESTADO[nivel][1]+' '+nombre, marker_color=tema.ESTADO[nivel][0], hovertemplate='%{y}<br>%{x:,.0f} pares<extra>'+nombre+'</extra>')
        fig.update_layout(barmode='stack', legend=dict(traceorder='normal'), xaxis_title='Pares sucursal-producto', hovermode='closest')
        tema.grafica(fig, alto=420)
    tema.seccion('Desabasto a lo largo del tiempo', 'Un tono más oscuro indica una mayor tasa de días sin existencia.')
    filas = []
    for suc in interfaz.datos('/catalogos/sucursales'):
        d = interfaz.tabla('/inventario/desabasto', id_sucursal=suc['id_sucursal'])
        if not d.empty:
            d['sucursal'] = suc['codigo']
            filas.append(d)
    if filas:
        matriz = pd.concat(filas).pivot(index='sucursal', columns='mes', values='tasa_desabasto')*100
        fig = go.Figure(go.Heatmap(x=matriz.columns, y=matriz.index, z=matriz.values, colorscale=tema.SECUENCIAL, colorbar=dict(title='Tasa (%)'), hovertemplate='%{y} · %{x}<br>Desabasto: %{z:.1f} %<extra></extra>'))
        fig.update_xaxes(tickformat='%m/%Y')
        tema.grafica(fig, alto=400)
    tema.seccion('Cobertura de inventario', 'Días estimados con las ventas de los últimos 90 días. Sin cobertura significa existencia sin ventas.')
    a, b, c = st.columns([1, 1, 2])
    with a:
        estado = st.selectbox('Estado', ['Todos']+list(ESTADOS), format_func=lambda x: ESTADOS[x][0] if x in ESTADOS else x)
    with b:
        sucursal = interfaz.sucursal()
    with c:
        buscar = st.text_input('Buscar SKU o producto')
    if not total:
        st.info('No hay inventario disponible.')
        return
    if estado != 'Todos':
        marco = marco[marco.estado == estado]
    if sucursal is not None:
        marco = marco[marco.id_sucursal == sucursal]
    if buscar:
        marco = marco[marco.sku.str.contains(buscar, case=False, regex=False) | marco.producto.str.contains(buscar, case=False, regex=False)]
    marco = marco.copy()
    marco['estado'] = marco.estado.map(lambda e: tema.ESTADO[ESTADOS[e][1]][1]+' '+ESTADOS[e][0])
    columnas = ['sucursal', 'sku', 'producto', 'estado', 'existencia', 'stock_minimo', 'stock_maximo', 'cobertura_dias']
    columnas = [c for c in columnas if c in marco]
    config = {c: st.column_config.TextColumn(c.replace('_', ' ').capitalize()) for c in columnas}
    config['cobertura_dias'] = st.column_config.ProgressColumn('Cobertura (días)', min_value=0, max_value=max(180, float(marco.cobertura_dias.max() or 180)) if not marco.empty else 180, format='%.1f días')
    st.dataframe(marco[columnas], hide_index=True, column_config=config, width='stretch')
