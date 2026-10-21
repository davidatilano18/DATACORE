"""Pronóstico: demanda esperada e incertidumbre del modelo."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datacore.dashboard import interfaz, tema
from datacore.dashboard.vistas.inicio import _variacion


def _comparacion(esperado: float, real: float) -> str:
    variacion = _variacion(esperado, real)
    if variacion is None:
        return 'Unidades vendidas'
    sentido = 'más' if variacion >= 0 else 'menos'
    return f'Unidades vendidas · el pronóstico espera {abs(variacion):.0f} % {sentido}'


def mostrar():
    tema.encabezado('Pronóstico', 'Planea las próximas cuatro semanas con la demanda esperada y su intervalo de incertidumbre.')
    buscar = st.text_input('Buscar producto por nombre o SKU')
    productos = interfaz.datos('/catalogos/productos', buscar=buscar or None, limite=5000)
    if not productos:
        st.info('No se encontraron productos.')
        return
    producto = st.selectbox('Producto', productos, format_func=lambda p: p['sku']+' · '+p['nombre'])
    identificador = producto['id_producto']
    historia = interfaz.tabla('/ventas/semanales', id_producto=identificador)
    futuro = interfaz.tabla('/pronosticos', id_producto=identificador)
    if futuro.empty:
        st.info('No hay pronóstico publicado para este producto.')
        return
    historia['semana_inicio'] = pd.to_datetime(historia.semana_inicio)
    corte = historia.semana_inicio.max()
    historia = historia.set_index('semana_inicio').reindex(pd.date_range(corte-pd.Timedelta(weeks=51), corte, freq='7D', name='semana_inicio'), fill_value=0).reset_index()
    resumen = interfaz.datos('/pronosticos/resumen', id_producto=identificador)
    esperado = resumen['demanda_estimada']
    real = historia.tail(4).unidades.sum()
    inventario = interfaz.tabla('/inventario/cobertura', limite=5000)
    existencia = inventario.loc[inventario.id_producto == identificador, 'existencia'].sum()
    tema.fila_tarjetas([
        tema.tarjeta('Demanda · próximas 4 semanas', tema.entero(esperado), nota=f"Intervalo 80 %: {tema.entero(resumen['limite_inferior'])}–{tema.entero(resumen['limite_superior'])}", serie=futuro.demanda_estimada.tolist(), alto=150),
        # Que el pronóstico supere o no a la venta reciente no es bueno ni malo: va como dato neutro, sin color.
        tema.tarjeta('Últimas 4 semanas reales', tema.entero(real), nota=_comparacion(esperado, real), alto=150),
        tema.tarjeta('Existencia actual', tema.entero(existencia), nota='Todas las sucursales', alto=150),
        tema.tarjeta('Clase ABC', producto.get('clase_abc') or 'Sin clase', nota='Clasificación histórica por ingreso', alto=150)])
    st.caption('Intervalo total aproximado del 80 %, suponiendo independencia entre semanas y sucursales. Puede subestimar la incertidumbre si los errores están correlacionados.')
    tema.seccion('Historia y próximas cuatro semanas', 'La banda muestra el intervalo del 80 %; una banda amplia indica mayor incertidumbre.')
    fig = go.Figure(go.Scatter(x=historia.semana_inicio, y=historia.unidades, name='Venta real', mode='lines', line_color=tema.CONTEXTO))
    fig.add_scatter(x=futuro.semana_inicio, y=futuro.limite_inferior, mode='lines', line_color=tema.DESTACADO, line_width=0, showlegend=False, hoverinfo='skip')
    fig.add_scatter(x=futuro.semana_inicio, y=futuro.limite_superior, mode='lines', fill='tonexty', fillcolor='rgba(46,90,156,0.16)', line_color=tema.DESTACADO, line_width=0, name='Intervalo 80 %', hovertemplate='Límite superior: %{y:,.0f}<extra></extra>')
    fig.add_scatter(x=futuro.semana_inicio, y=futuro.demanda_estimada, name='Pronóstico', mode='lines', line_color=tema.DESTACADO, hovertemplate='%{y:,.1f} unidades<extra>Pronóstico</extra>')
    for x, y, texto in [(historia.semana_inicio.iloc[-1], historia.unidades.iloc[-1], 'Venta real'), (futuro.semana_inicio.iloc[-1], futuro.demanda_estimada.iloc[-1], 'Pronóstico')]:
        fig.add_annotation(x=x, y=y, text=texto, showarrow=False, yshift=18, font_color=tema.TINTA)
    hoy = pd.Timestamp(interfaz.datos('/modelo')['fecha_corte_datos'])
    fig.add_shape(type='line', x0=hoy, x1=hoy, y0=0, y1=1, yref='paper', line=dict(color=tema.TINTA_TENUE, dash='dot'))
    fig.add_annotation(x=hoy, y=1, yref='paper', text='Hoy · corte de datos', showarrow=False, font_color=tema.TINTA)
    fig.update_layout(yaxis_title='Unidades', xaxis_title='Semana', xaxis_tickformat='%m/%Y')
    tema.grafica(fig, alto=420)
    tema.seccion('Próxima semana por sucursal', 'Demanda esperada ordenada de mayor a menor para orientar la distribución.')
    filas = []
    for suc in interfaz.datos('/catalogos/sucursales'):
        pred = interfaz.datos('/pronosticos', id_producto=identificador, id_sucursal=suc['id_sucursal'])
        if pred:
            filas.append({'sucursal': suc['codigo'], 'demanda': pred[0]['demanda_estimada']})
    if filas:
        marco = pd.DataFrame(filas).sort_values('demanda')
        fig = go.Figure(go.Bar(x=marco.demanda, y=marco.sucursal, orientation='h', marker_color=tema.DESTACADO, text=marco.demanda.round(1), textposition='outside', textfont_color=tema.TINTA, cliponaxis=False, hovertemplate='%{y}: %{x:,.1f} unidades<extra></extra>'))
        fig.update_layout(margin=dict(r=60), xaxis_title='Unidades esperadas')
        tema.grafica(fig, alto=400)
    tema.seccion('Qué tan bueno es el modelo', 'WAPE mide el error absoluto como porcentaje del volumen real; un valor menor es mejor.')
    metricas = interfaz.datos('/modelo').get('metricas', {})
    fig = go.Figure()
    horizontes = [h for h in ['h1', 'h2', 'h3', 'h4'] if h in metricas]
    for nombre, clave, color in [('Modelo', 'wape_par', tema.DESTACADO), ('Media móvil 8 semanas', 'wape_media_movil_8', tema.CONTEXTO)]:
        valores = [metricas[h][clave]*100 for h in horizontes]
        fig.add_bar(y=['Semana '+h[1:] for h in horizontes], x=valores, orientation='h', name=nombre, marker_color=color, text=[f'{v:.1f} %' for v in valores], textposition='outside', textfont_color=tema.TINTA, cliponaxis=False, hovertemplate='%{y}: %{x:.1f} %<extra>'+nombre+'</extra>')
    fig.update_layout(barmode='group', xaxis_title='WAPE por par sucursal-producto (%)', margin=dict(r=60))
    tema.grafica(fig)
