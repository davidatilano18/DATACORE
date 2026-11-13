"""Explicación de las alertas: reglas sobre filas construidas a mano (no requieren base)."""

import pandas as pd

from datacore.ml import explicaciones as ex


def _fila(**valores):
    base = {"tipo": "RIESGO_DESABASTO", "existencia": 10, "dias_entrega": 6, "demanda_diaria": 2.0,
            "cobertura_dias": 5.0, "tendencia_pct": None, "media_semanal": 14.0, "unidades_13_semanas": 100,
            "evento_proximo": None, "indice_temporada": 1.0, "mes_siguiente": "enero", "categoria": "Juguetes",
            "dias_agotado_28": 0, "precio": 50.0}
    base.update(valores)
    return pd.Series(base)


def test_desabasto_explica_cobertura_contra_entrega():
    m = ex.motivos(_fila())
    assert m.startswith("La existencia alcanza para 5 días y un pedido tarda 6 días")


def test_desabasto_ordena_por_gravedad_y_limita_a_tres():
    fila = _fila(existencia=0, tendencia_pct=40.0, evento_proximo="el Día de Reyes", indice_temporada=1.6,
                 dias_agotado_28=20, dias_entrega=9)
    partes = ex.motivos(fila).split("; ")
    assert len(partes) == ex.MAX_FACTORES
    assert partes[0].startswith("Ya no hay existencia")
    assert partes[1][0].islower()  # los factores siguientes continúan la oración
    assert any("agotado 20 de los últimos 28 días" in p for p in partes)


def test_factores_solo_si_superan_su_umbral():
    tranquila = ex.factores(_fila(tendencia_pct=5.0, dias_agotado_28=1, indice_temporada=1.05, dias_entrega=3))
    assert len(tranquila) == 1  # solo la cobertura
    assert any("40 % más" in f for _, f in ex.factores(_fila(tendencia_pct=40.0)))


def test_exceso_y_sin_rotacion():
    exceso = ex.motivos(_fila(tipo="EXCESO_INVENTARIO", cobertura_dias=300, tendencia_pct=-50.0, media_semanal=0.5))
    assert exceso.startswith("La existencia cubre 300 días") and "50 % menos" in exceso
    parada = ex.motivos(_fila(tipo="SIN_ROTACION", existencia=8))
    assert parada.startswith("No se ha vendido en las últimas 13 semanas")
    assert "8 piezas paradas ($ 400 a precio de lista)" in parada
