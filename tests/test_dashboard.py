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
    ('Inicio.py', 'Resumen ejecutivo', 'markdown'),
    ('pages/1_Ventas.py', 'Ventas', 'radio'),
    ('pages/2_Inventario.py', 'Inventario', 'dataframe'),
    ('pages/3_Alertas.py', 'Alertas', 'selectbox'),
    ('pages/4_Pronóstico.py', 'Pronóstico', 'text_input'),
    ('pages/5_Calidad_y_operación.py', 'Calidad y operación', 'dataframe'),
])
def test_paginas_api_real(api_disponible, archivo, titulo, elemento):
    aplicacion = AppTest.from_file(str(RAIZ / 'src/datacore/dashboard' / archivo)).run(timeout=60)
    assert not aplicacion.exception
    assert not aplicacion.error, [error.value for error in aplicacion.error]
    assert aplicacion.title[0].value == titulo
    assert len(getattr(aplicacion, elemento)) > 0
    if archivo == 'Inicio.py':
        tarjetas = sum(m.value.count('class="dc-tarjeta"') for m in aplicacion.markdown)
        assert tarjetas == 8  # 4 de negocio + 4 de salud del inventario
    assert any('empresa ficticia' in texto.value for texto in aplicacion.caption)

@pytest.mark.parametrize('archivo,tarjetas,graficas', [
    ('pages/1_Ventas.py', 4, 4), ('pages/2_Inventario.py', 5, 2),
    ('pages/3_Alertas.py', 3, 1), ('pages/4_Pronóstico.py', 4, 3),
])
def test_componentes_del_sistema_visual(api_disponible, archivo, tarjetas, graficas):
    aplicacion = AppTest.from_file(str(RAIZ / 'src/datacore/dashboard' / archivo)).run(timeout=60)
    assert not aplicacion.exception and not aplicacion.error
    assert sum(m.value.count('class="dc-tarjeta"') for m in aplicacion.markdown) == tarjetas
    assert len(aplicacion.get('plotly_chart')) >= graficas
    if 'Alertas' in archivo:
        assert aplicacion.button[0].label == 'Marcar como atendidas'
        assert aplicacion.button[0].disabled
    if 'Ventas' in archivo:
        aplicacion.radio[0].set_value('Personalizado').run(timeout=60)
        assert len(aplicacion.date_input) == 1
        assert not aplicacion.exception and not aplicacion.error


def test_pestanas_calidad(api_disponible):
    aplicacion = AppTest.from_file(str(RAIZ / 'src/datacore/dashboard/pages/5_Calidad_y_operación.py')).run(timeout=60)
    assert not aplicacion.exception and not aplicacion.error
    assert [t.label for t in aplicacion.tabs] == ['Calidad de datos', 'Anomalías', 'Incidencias', 'Plataforma']
    assert any('Últimos respaldos' in m.value for m in aplicacion.markdown)
