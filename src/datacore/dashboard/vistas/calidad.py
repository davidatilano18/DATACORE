"""Calidad y operación: trazabilidad de datos y servicios."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from datacore.dashboard import interfaz, tema


def _tabla(marco):
    if marco.empty:
        st.info('No hay registros disponibles.')
        return
    columnas = [c for c in marco if not c.startswith('id_') and c not in ['id', 'archivo_origen', 'archivo', 'pasos', 'fecha_resolucion']]
    marco = marco[columnas].copy()
    for c in columnas:
        if marco[c].map(lambda v: isinstance(v, (dict, list))).any():
            marco[c] = marco[c].astype(str)
    for campo in ['tipo', 'estatus', 'componente']:
        if campo in marco:
            marco[campo] = marco[campo].str.replace('_', ' ').str.capitalize().replace({'Api': 'API', 'Etl': 'ETL'})
    if 'tamano_bytes' in marco:
        marco['tamano_bytes'] = marco['tamano_bytes'] / 1e6
    # Celdas de texto vacías: en blanco, no "None".
    for c in marco.select_dtypes(include=['object', 'str']):
        marco[c] = marco[c].fillna('')
    config = {c: st.column_config.Column(c.replace('_', ' ').capitalize()) for c in columnas}
    nombres = {'descripcion': 'Descripción', 'metrica': 'Métrica', 'detectada_en': 'Detectada en', 'latencia_ms': 'Latencia (ms)', 'tamano_bytes': 'Tamaño (MB)', 'fecha_reporte': 'Fecha de reporte', 'mensaje_error': 'Mensaje de error'}
    for campo, nombre in nombres.items():
        if campo in columnas:
            config[campo] = st.column_config.Column(nombre)
    for campo in ['inicio', 'fin', 'revisado_en', 'detectada_en']:
        if campo in marco:
            marco[campo] = pd.to_datetime(marco[campo])
            config[campo] = st.column_config.DatetimeColumn(nombres.get(campo, campo.replace('_', ' ').capitalize()), format='DD/MM/YYYY HH:mm')
    for c in ['filas_leidas', 'filas_cargadas', 'filas_rechazadas']:
        if c in columnas:
            config[c] = st.column_config.NumberColumn({'filas_leidas': 'Filas leídas', 'filas_cargadas': 'Filas cargadas', 'filas_rechazadas': 'Filas descartadas'}[c], format='%d')
    if 'tamano_bytes' in columnas:
        config['tamano_bytes'] = st.column_config.NumberColumn('Tamaño (MB)', format='%.1f')
    st.dataframe(marco, hide_index=True, column_config=config, width='stretch')


def mostrar():
    tema.encabezado('Calidad y operación', 'Revisa la confiabilidad de la carga, los eventos atípicos y la continuidad de la plataforma.')
    calidad, anomalias, incidencias, plataforma = st.tabs(['Calidad de datos', 'Anomalías', 'Incidencias', 'Plataforma'])
    with calidad:
        tema.seccion('Hallazgos de la última carga', 'Distingue los registros corregidos, marcados para revisión y rechazados por cada regla.')
        marco = interfaz.tabla('/calidad/ultima-carga')
        if not marco.empty:
            matriz = marco.pivot_table(index='regla', columns='accion', values='conteo', aggfunc='sum', fill_value=0)
            matriz = matriz.loc[matriz.sum(axis=1).sort_values().index]
            fig = go.Figure()
            for i, accion in enumerate(['corregido', 'marcado', 'rechazado']):
                if accion in matriz:
                    fig.add_bar(y=matriz.index, x=matriz[accion], orientation='h', name=accion.capitalize(), marker_color=tema.SERIES[i], hovertemplate='%{y}: %{x:,.0f}<extra>'+accion+'</extra>')
            fig.update_layout(barmode='stack', legend=dict(traceorder='normal'), xaxis_title='Hallazgos', hovermode='closest')
            fig.update_yaxes(tickvals=matriz.index, ticktext=[r.replace('_', ' ').capitalize() for r in matriz.index])
            tema.grafica(fig, alto=max(380, len(matriz)*30))
        tema.seccion('Ejecuciones del ETL', 'Compara filas leídas, cargadas y descartadas; revisa el estado y el mensaje de error.')
        _tabla(interfaz.tabla('/etl/ejecuciones', limite=50))
    with anomalias:
        tema.seccion('Anomalías de tickets diarios', 'Las caídas y los picos señalan días para investigar. Se excluyen eventos festivos conocidos.')
        opciones = interfaz.datos('/catalogos/sucursales')
        sucursal = st.selectbox('Sucursal para anomalías', opciones, format_func=lambda s: s['codigo']+' · '+s['nombre'])
        if sucursal:
            diaria = interfaz.tabla('/ventas/diarias', id_sucursal=sucursal['id_sucursal'])
            puntos = interfaz.tabla('/anomalias', id_sucursal=sucursal['id_sucursal'])
            fig = go.Figure()
            if not diaria.empty:
                diaria['fecha'] = pd.to_datetime(diaria.fecha)
                diaria = diaria.set_index('fecha').reindex(pd.date_range(diaria.fecha.min(), diaria.fecha.max(), name='fecha'), fill_value=0).reset_index()
                fig.add_scatter(x=diaria.fecha, y=diaria.tickets, name='Tickets diarios', line_color=tema.SERIES[0])
                fig.add_annotation(x=diaria.fecha.iloc[-1], y=diaria.tickets.iloc[-1], text='Tickets', showarrow=False, yshift=16, font_color=tema.TINTA)
            if not puntos.empty:
                puntos = puntos[puntos.metrica == 'tickets']
                for i, tipo in enumerate(['caida', 'pico'], start=1):
                    g = puntos[puntos.tipo == tipo]
                    fig.add_scatter(x=g.fecha, y=g.valor, name='Caídas' if tipo == 'caida' else 'Picos', mode='markers', marker=dict(color=tema.SERIES[i], size=9, symbol='diamond' if tipo == 'caida' else 'triangle-up'), hovertemplate='%{x}: %{y:,.0f} tickets<extra>'+tipo+'</extra>')
            fig.update_yaxes(title='Tickets')
            fig.update_xaxes(tickformat='%m/%Y')
            tema.grafica(fig, alto=420)
            _tabla(puntos)
    with incidencias:
        tema.seccion('Incidencias mensuales', 'Compara la composición de los eventos reportados y consulta los que siguen abiertos.')
        marco = interfaz.tabla('/incidencias/mensuales')
        tipos = ['FALLA_SISTEMA', 'DESABASTO', 'RETRASO_PROVEEDOR', 'MERCANCIA_DANADA', 'DIFERENCIA_INVENTARIO', 'QUEJA_CLIENTE']
        fig = go.Figure()
        if not marco.empty:
            for i, tipo in enumerate(tipos):
                g = marco[marco.tipo == tipo]
                nombre = tipo.replace('_', ' ').capitalize()
                fig.add_bar(x=g.mes, y=g.total, name=nombre, marker_color=tema.SERIES[i], text=g.total if i == 5 else None, textposition='inside', textfont_color=tema.TINTA, hovertemplate='%{x}: %{y} incidencias<extra>'+nombre+'</extra>')
            fig.update_layout(barmode='stack', legend=dict(traceorder='normal'), yaxis_title='Incidencias', xaxis_tickformat='%m/%Y')
            tema.grafica(fig, alto=420)
            _tabla(marco.assign(tipo=marco.tipo.str.replace('_', ' ').str.capitalize()))
        tema.seccion('Incidencias abiertas', 'Eventos abiertos o en proceso, ordenados por fecha de reporte.')
        _tabla(interfaz.tabla('/incidencias/abiertas'))
    with plataforma:
        tema.seccion('Estado de la plataforma', 'Disponibilidad actual de servicios y último resultado de los procesos principales.')
        salud = interfaz.datos('/salud')
        etl, modelo = salud.get('ultimo_etl') or {}, salud.get('modelo_activo') or {}
        estados = [('API', salud.get('estado') == 'ok'), ('Base de datos', salud.get('base_de_datos') == 'ok'), ('ETL', bool(etl.get('exitosa'))), ('Modelo activo', bool(modelo))]
        st.markdown(' '.join(tema.estado(nombre+' · '+('Disponible' if ok else 'Revisar'), 'bien' if ok else 'critico') for nombre, ok in estados), unsafe_allow_html=True)
        for titulo, descripcion, ruta in [('Últimos chequeos de monitoreo', 'Estado, latencia y detalle de cada componente revisado.', '/operacion/monitoreo'), ('Últimos respaldos', 'Verificado indica que la restauración de prueba coincidió con el origen.', '/operacion/respaldos'), ('Últimas corridas diarias', 'Resultado del proceso diario y detalle de sus pasos.', '/operacion/corridas')]:
            tema.seccion(titulo, descripcion)
            registros = interfaz.tabla(ruta)
            _tabla(registros)
            if ruta.endswith('corridas') and not registros.empty:
                for corrida in registros.to_dict('records'):
                    with st.expander('Pasos · '+str(corrida['inicio'])[:16]):
                        _tabla(pd.DataFrame(corrida.get('pasos') or []))
