"""Datos de entrada en un servidor nuevo (no requiere base)."""

from datacore.operacion import datos


def test_genera_solo_si_no_hay_archivos(tmp_path):
    llamadas = []

    def generar(salida):
        llamadas.append(salida)
        (salida / "raw").mkdir(parents=True)
        (salida / "raw" / "ventas_2025.csv").write_text("folio\n", encoding="utf-8")

    assert not datos.hay_datos(tmp_path)
    assert datos.asegurar_datos_simulados(tmp_path, generar) is True
    assert llamadas == [tmp_path / "data"]
    assert datos.hay_datos(tmp_path)
    assert datos.asegurar_datos_simulados(tmp_path, generar) is False  # ya hay datos: no se regenera
    assert len(llamadas) == 1


def test_carpeta_vacia_cuenta_como_sin_datos(tmp_path):
    (tmp_path / "data" / "raw").mkdir(parents=True)
    assert not datos.hay_datos(tmp_path)
