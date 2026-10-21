"""Pruebas del cliente y de las páginas con el servicio local real."""

from pathlib import Path

import httpx
import pytest
from streamlit.testing.v1 import AppTest

from datacore.dashboard.cliente import ClienteAPI, ErrorAPI


RAIZ = Path(__file__).resolve().parents[1]


def test_error_conexion():
    def fallar(solicitud):
        raise httpx.ConnectError("Sin conexión", request=solicitud)

    with pytest.raises(ErrorAPI, match="No se pudo conectar con la API"):
        ClienteAPI(httpx.MockTransport(fallar)).obtener('/salud')


def test_configuracion_y_atencion(monkeypatch):
    monkeypatch.setenv('DATACORE_API_URL', 'http://api.local')
    monkeypatch.setenv('DATACORE_API_KEY', 'clave-de-prueba')

    def responder(solicitud):
        assert solicitud.headers['X-API-Key'] == 'clave-de-prueba'
        assert str(solicitud.url) == 'http://api.local/alertas/12/atender'
        assert solicitud.method == 'POST'
        return httpx.Response(200, json={'id_alerta': 12, 'atendida': True})

    assert ClienteAPI(httpx.MockTransport(responder)).atender(12)['atendida']


@pytest.mark.parametrize('estado', [401, 404, 500])
def test_error_http(estado):
    cliente = ClienteAPI(httpx.MockTransport(lambda solicitud: httpx.Response(estado)))
    with pytest.raises(ErrorAPI, match=f'HTTP {estado}'):
        cliente.obtener('/modelo')


def test_inicio_api_no_disponible(monkeypatch):
    from datacore.dashboard import interfaz

    def fallar(*args, **kwargs):
        raise ErrorAPI('No se pudo conectar con la API de DATACORE.')

    monkeypatch.setattr(interfaz, 'datos', fallar)
    aplicacion = AppTest.from_file(str(RAIZ / 'src/datacore/dashboard/Inicio.py')).run()
    assert not aplicacion.exception
    assert 'No se pudo conectar' in aplicacion.error[0].value


@pytest.fixture
def api_disponible():
    try:
        ClienteAPI().obtener('/salud')
    except ErrorAPI as exc:
        pytest.skip(f'API no disponible: {exc}')


@pytest.mark.parametrize('archivo,titulo,elemento', [
    ('Inicio.py', 'Resumen ejecutivo', 'metric'),
    ('pages/1_Ventas.py', 'Ventas', 'date_input'),
    ('pages/2_Inventario.py', 'Inventario', 'dataframe'),
    ('pages/3_Alertas.py', 'Alertas', 'selectbox'),
    ('pages/4_Pronostico.py', 'Pronóstico', 'text_input'),
    ('pages/5_Calidad_y_operacion.py', 'Calidad y operación', 'dataframe'),
])
def test_paginas_api_real(api_disponible, archivo, titulo, elemento):
    aplicacion = AppTest.from_file(str(RAIZ / 'src/datacore/dashboard' / archivo)).run(timeout=60)
    assert not aplicacion.exception
    assert not aplicacion.error, [error.value for error in aplicacion.error]
    assert aplicacion.title[0].value == titulo
    assert len(getattr(aplicacion, elemento)) > 0
    if archivo == 'Inicio.py':
        assert len(aplicacion.metric) == 12  # 9 indicadores + 3 de estado de la plataforma
    assert any('empresa ficticia' in texto.value for texto in aplicacion.caption)
