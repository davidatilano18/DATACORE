"""Pruebas del simulador de impacto con datos pequeños construidos a mano (no requieren base)."""

import numpy as np
import pandas as pd
import pytest

from datacore.ml import impacto as im


def _datos(n=2, dias=28, demanda=3.0, existencia=10.0):
    fechas = pd.date_range("2025-01-01", periods=dias, freq="D")  # 2025-01-05 es domingo
    forma = (n, dias)
    pares = pd.MultiIndex.from_tuples([(1, j + 1) for j in range(n)], names=["id_sucursal", "id_producto"])
    return im.Datos(
        pares=pares, dias=fechas, demanda=np.full(forma, demanda), vendido_real=np.full(forma, demanda),
        existencia_inicial=np.full(n, existencia), llegadas_iniciales=np.zeros(forma), llegadas_previas=np.zeros(forma),
        llegadas_actual=np.zeros(forma), vivo=np.ones(forma, dtype=bool), puede_pedir=np.ones(forma, dtype=bool),
        entrega=np.full(n, 3.0), prob_retraso=np.zeros(n), retraso_medio=np.zeros(n),
        precio=np.full(n, 100.0), costo=np.full(n, 60.0))


def _pron(datos, semanal):
    semanas = pd.date_range("2024-12-30", periods=8, freq="W-MON")
    tabla = pd.DataFrame(semanal, index=semanas, columns=datos.pares)
    return {h: tabla for h in (1, 2, 3)}


def test_motor_conserva_unidades_y_aplica_llegadas():
    demanda = np.array([[5.0, 5.0, 5.0, 5.0]])
    llegadas = np.array([[0.0, 0.0, 10.0, 0.0]])
    r = im.simular(demanda, np.array([6.0]), llegadas)
    np.testing.assert_array_equal(r.vendido + r.perdido, demanda)
    np.testing.assert_array_equal(r.vendido[0], [5, 1, 5, 5])
    np.testing.assert_array_equal(r.existencia[0], [1, 0, 5, 0])


def test_pedidos_en_camino_se_descuentan_al_llegar():
    demanda = np.zeros((1, 5))
    previas = np.array([[0.0, 4.0, 0.0, 0.0, 0.0]])
    vistos = []

    def politica(d, existencia, en_camino, vendido):
        vistos.append(float(en_camino[0]))
        return None

    im.simular(demanda, np.array([0.0]), np.zeros((1, 5)), pedidos_en_camino=previas, politica=politica)
    assert vistos == [4.0, 0.0, 0.0, 0.0, 0.0]


def test_cuantil_binomial_negativa_crece_con_el_cuantil_y_la_varianza():
    mu, var = np.array([10.0, 10.0]), np.array([10.0, 40.0])
    p90, p99 = im.cuantil_binomial_negativa(mu, var, 0.9), im.cuantil_binomial_negativa(mu, var, 0.99)
    assert (p99 >= p90).all()
    assert p90[1] > p90[0]  # más varianza, más stock de seguridad
    assert im.cuantil_binomial_negativa(np.array([0.0]), np.array([0.0]), 0.9)[0] == 0


def test_demanda_proteccion_prorratea_las_semanas():
    datos = _datos(n=1)
    pron = _pron(datos, [[14.0]] * 8)
    mu, var, sin = im.demanda_proteccion(pron, pd.Timestamp("2025-01-06"), np.array([10.0]), {1: 2.3, 2: 2.3, 3: 2.3})
    assert mu[0] == pytest.approx(20.0)  # 14 por semana = 2 por día × 10 días
    assert var[0] > mu[0] and not sin[0]


def test_politica_datacore_pide_solo_en_domingo_y_cubre_el_cuantil():
    datos = _datos(n=2)
    datos.puede_pedir[1] = False  # producto por descontinuarse: no se repone
    sup = im.Supuestos(corregir_censura=False)
    politica = im.politica_datacore(datos, _pron(datos, [[21.0, 21.0]] * 8), sup, cuantil=0.9)
    existencia, en_camino, vendido = np.array([2.0, 2.0]), np.zeros(2), np.zeros((2, 28))
    assert politica(0, existencia, en_camino, vendido) is None          # miércoles: no se revisa
    q, llega = politica(4, existencia, en_camino, vendido)              # domingo 2025-01-05
    assert q[0] > 0 and q[1] == 0
    assert llega[0] == 4 + 1 + 3                                       # pedido el lunes + 3 días de entrega
    proteccion = 1 + 3 + 7
    assert existencia[0] + q[0] >= 3 * proteccion                      # cubre al menos la media de 3 por día


def test_datacore_reduce_faltantes_frente_a_no_reponer():
    datos = _datos(n=1, dias=56, existencia=20.0)
    sup = im.Supuestos(corregir_censura=False)
    sin_reponer = im.metricas(im.simular_actual(datos), datos, sup)
    con_datacore = im.metricas(im.simular_datacore(datos, _pron(datos, [[21.0]] * 8), sup, 0.95), datos, sup)
    assert con_datacore["ventas_perdidas_unidades"] < sin_reponer["ventas_perdidas_unidades"]
    assert con_datacore["nivel_servicio"] > 0.9


def test_calibrar_elige_el_menor_cuantil_que_iguala_el_servicio():
    tabla = pd.DataFrame({"nivel_servicio": [0.95, 0.90, 0.951, 0.97]}, index=["actual", 0.9, 0.95, 0.99])
    assert im.calibrar(tabla) == 0.95
    tabla.loc[[0.9, 0.95, 0.99], "nivel_servicio"] = 0.5
    assert im.calibrar(tabla) == 0.99  # ninguno alcanza: el más alto


def test_impacto_resta_actual_menos_datacore():
    actual = {"margen_perdido_pesos": 100.0, "costo_mantener_pesos": 50.0, "ventas_perdidas_pesos": 300.0,
              "inventario_promedio_pesos": 200.0}
    datacore = {"margen_perdido_pesos": 70.0, "costo_mantener_pesos": 40.0, "ventas_perdidas_pesos": 200.0,
                "inventario_promedio_pesos": 160.0}
    r = im.impacto(actual, datacore)
    assert r["beneficio_neto_pesos"] == 40.0 and r["inventario_liberado_pesos"] == 40.0


def test_disparo_por_alerta_pide_menos_veces_que_por_nivel():
    datos = _datos(n=1, dias=56, existencia=20.0)
    pron = _pron(datos, [[21.0]] * 8)
    por_nivel = im.simular_datacore(datos, pron, im.Supuestos(corregir_censura=False, disparo="nivel"), 0.95)
    por_alerta = im.simular_datacore(datos, pron, im.Supuestos(corregir_censura=False, disparo="alerta"), 0.95)
    assert por_alerta.pedidos <= por_nivel.pedidos
