"""El reporte se reproduce con datos simulados y sin consultar tablas ocultas."""

from dataclasses import replace
from datetime import date

import pandas as pd

from datacore.eda.reporte import TABLAS, generar_reporte
from datacore.generator.config import GeneratorConfig
from datacore.generator.run import generar


def test_reporte_eda(tmp_path, monkeypatch):
    cfg = replace(GeneratorConfig(), fecha_fin=date(2023, 6, 30), n_productos=60, n_clientes=500)
    generar(cfg, tmp_path / "datos")
    leer = pd.read_parquet
    leidas = []

    def leer_core(ruta):
        assert ruta.stem in TABLAS
        leidas.append(ruta.stem)
        return leer(ruta)

    monkeypatch.setattr(pd, "read_parquet", leer_core)
    salida = tmp_path / "eda"
    reporte = generar_reporte(tmp_path / "datos" / "ground_truth", salida)
    texto = reporte.read_text(encoding="utf-8")
    assert set(leidas) == set(TABLAS)
    assert "Implicaciones para el modelo de demanda" in texto
    for nombre in ("ventas_mensuales", "categorias_mes", "sucursales", "pareto_productos",
                   "calendario", "mezcla", "inventario", "incidencias"):
        archivo = salida / f"{nombre}.png"
        assert archivo.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
        assert f"]({nombre}.png)" in texto
    cobertura = pd.read_csv(salida / "cobertura_inventario.csv")
    assert (cobertura.loc[cobertura.existencia == 0, "cobertura_dias"] == 0).all()
    assert (salida / "alertas_inventario.csv").exists()
