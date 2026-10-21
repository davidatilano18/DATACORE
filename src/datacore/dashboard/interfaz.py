"""Presentación y consultas compartidas por las páginas."""

import os

import pandas as pd
import streamlit as st

from datacore.dashboard.cliente import ClienteAPI, ErrorAPI

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


def sucursal():
    opciones = {"Todas": None}
    opciones.update({f"{s['codigo']} · {s['nombre']}": s['id_sucursal']
                     for s in datos('/catalogos/sucursales')})
    return opciones[st.selectbox("Sucursal", list(opciones))]


def ejecutar(pagina):
    from datacore.dashboard import tema
    from datacore.dashboard.vistas import inicio, ventas, inventario, alertas, pronostico, calidad
    tema.preparar(pagina)
    try:
        {'Inicio': inicio.mostrar, 'Ventas': ventas.mostrar, 'Inventario': inventario.mostrar,
         'Alertas': alertas.mostrar, 'Pronóstico': pronostico.mostrar,
         'Calidad y operación': calidad.mostrar}[pagina]()
    except ErrorAPI as exc:
        st.error(str(exc))
    finally:
        tema.pie()
