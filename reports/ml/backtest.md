# Evaluación del modelo de demanda semanal

Backtest fuera de muestra: validación con **origen móvil**: 4 bloques consecutivos de 13 semanas desde **2024-12-30** (52 semanas de prueba); cada bloque se pronostica con un modelo entrenado solo con las semanas anteriores. Las tablas agregan todos los bloques. Generado por `python -m datacore.ml evaluar`.

**WAPE** = Σ|real − pronóstico| / Σ real (menor es mejor). **Sesgo** = Σ(pronóstico − real) / Σ real (negativo = subestima). *par* = sucursal-producto-semana; *producto-semana* = suma de sucursales.

## Contra ventas observadas

### par (todos)

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -3.1% | -2.6% | -2.6% | 76.9% | 77.1% | 77.4% |
| gbm | -1.4% | -1.3% | -1.1% | 77.5% | 77.7% | 78.0% |
| media_movil_8 | 0.4% | 0.4% | 0.5% | 81.1% | 81.1% | 81.5% |
| sba | 2.8% | 2.8% | 2.9% | 84.4% | 84.4% | 84.7% |
| ingenuo | -0.1% | 0.1% | 0.4% | 100.5% | 99.6% | 99.9% |
| estacional | 5.2% | 5.2% | 5.1% | 100.9% | 100.9% | 101.0% |

### producto-semana

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -3.1% | -2.6% | -2.6% | 26.9% | 27.0% | 27.2% |
| gbm | -1.4% | -1.3% | -1.1% | 26.9% | 27.0% | 27.2% |
| media_movil_8 | 0.4% | 0.4% | 0.5% | 28.8% | 29.3% | 30.2% |
| sba | 2.8% | 2.8% | 2.9% | 33.9% | 34.2% | 34.6% |
| ingenuo | -0.1% | 0.1% | 0.4% | 36.0% | 36.6% | 37.5% |
| estacional | 5.2% | 5.2% | 5.1% | 38.9% | 39.0% | 39.1% |

### clase A

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -1.3% | -0.3% | -0.3% | 58.8% | 59.1% | 59.3% |
| gbm | -0.9% | -0.8% | -0.0% | 58.7% | 59.0% | 59.4% |
| media_movil_8 | 0.9% | 1.2% | 1.5% | 61.9% | 62.0% | 62.5% |
| sba | 5.0% | 5.1% | 5.4% | 67.4% | 67.3% | 67.6% |
| ingenuo | -0.1% | 0.3% | 0.9% | 79.1% | 78.1% | 79.4% |
| estacional | 11.2% | 11.2% | 11.3% | 85.1% | 85.1% | 85.1% |

### clase B

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -3.4% | -3.0% | -3.2% | 82.1% | 82.2% | 82.4% |
| gbm | -1.6% | -1.1% | -1.4% | 82.6% | 82.9% | 83.0% |
| sba | 0.4% | 0.4% | 0.5% | 87.1% | 87.1% | 87.2% |
| media_movil_8 | 0.8% | 0.9% | 1.1% | 87.1% | 87.0% | 87.3% |
| estacional | 0.9% | 1.0% | 1.1% | 106.1% | 106.1% | 106.2% |
| ingenuo | -0.0% | 0.2% | 0.8% | 108.8% | 107.6% | 107.7% |

### clase C

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -6.8% | -7.3% | -7.0% | 110.4% | 110.7% | 111.4% |
| gbm | -2.4% | -2.6% | -3.1% | 112.6% | 113.0% | 113.5% |
| media_movil_8 | -1.5% | -1.8% | -2.7% | 116.1% | 116.2% | 116.6% |
| sba | 1.0% | 0.9% | 0.5% | 119.0% | 119.3% | 120.1% |
| estacional | -2.3% | -2.6% | -3.1% | 129.0% | 129.3% | 130.1% |
| ingenuo | -0.4% | -0.4% | -1.6% | 137.1% | 137.0% | 135.8% |

## Contra demanda real

La demanda real (ventas + demanda no surtida) solo existe en la simulación. Mide si el modelo recupera la demanda que los faltantes ocultan.

### par (todos)

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -7.8% | -7.3% | -7.3% | 76.4% | 76.4% | 76.7% |
| gbm | -6.2% | -6.0% | -5.9% | 77.1% | 77.1% | 77.3% |
| media_movil_8 | -4.5% | -4.4% | -4.4% | 80.0% | 80.3% | 80.7% |
| sba | -2.2% | -2.2% | -2.1% | 83.5% | 83.6% | 83.9% |
| ingenuo | -4.9% | -4.7% | -4.5% | 97.0% | 97.3% | 98.1% |
| estacional | 0.1% | 0.1% | 0.1% | 98.9% | 99.0% | 99.1% |

### producto-semana

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm | -6.2% | -6.0% | -5.9% | 27.8% | 27.9% | 28.1% |
| gbm_sin_censura | -7.8% | -7.3% | -7.3% | 27.9% | 28.0% | 28.1% |
| media_movil_8 | -4.5% | -4.4% | -4.4% | 29.4% | 30.0% | 31.0% |
| sba | -2.2% | -2.2% | -2.1% | 34.9% | 35.2% | 35.6% |
| ingenuo | -4.9% | -4.7% | -4.5% | 35.3% | 36.4% | 37.3% |
| estacional | 0.1% | 0.1% | 0.1% | 38.8% | 38.9% | 39.0% |

### clase A

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -4.9% | -3.9% | -3.9% | 58.5% | 58.8% | 59.0% |
| gbm | -4.5% | -4.4% | -3.7% | 58.6% | 58.6% | 59.0% |
| media_movil_8 | -2.7% | -2.5% | -2.1% | 61.3% | 61.6% | 62.2% |
| sba | 1.2% | 1.3% | 1.6% | 66.8% | 67.0% | 67.2% |
| ingenuo | -3.7% | -3.3% | -2.7% | 76.8% | 76.6% | 78.3% |
| estacional | 7.2% | 7.2% | 7.3% | 83.8% | 83.7% | 83.7% |

### clase B

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -8.7% | -8.3% | -8.4% | 81.2% | 81.1% | 81.3% |
| gbm | -6.9% | -6.5% | -6.7% | 81.8% | 81.8% | 82.0% |
| media_movil_8 | -4.7% | -4.6% | -4.4% | 85.4% | 85.7% | 86.2% |
| sba | -5.1% | -5.0% | -5.0% | 85.8% | 86.0% | 86.2% |
| estacional | -4.5% | -4.5% | -4.4% | 103.5% | 103.5% | 103.6% |
| ingenuo | -5.4% | -5.2% | -4.6% | 104.3% | 104.6% | 105.3% |

### clase C

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -13.0% | -13.5% | -13.3% | 108.5% | 108.6% | 109.4% |
| gbm | -8.9% | -9.1% | -9.6% | 110.6% | 110.7% | 111.3% |
| media_movil_8 | -8.0% | -8.4% | -9.2% | 113.2% | 113.7% | 114.3% |
| sba | -5.7% | -5.9% | -6.3% | 116.4% | 116.8% | 117.6% |
| estacional | -8.8% | -9.1% | -9.7% | 125.6% | 126.0% | 126.8% |
| ingenuo | -7.0% | -7.0% | -8.2% | 130.7% | 132.5% | 132.0% |

## WAPE producto-semana por bloque

Muestra si la ventaja del modelo se sostiene en distintas épocas del año.

| h | bloque desde | gbm | gbm_sin_censura | media_movil_8 | sba | ingenuo | estacional |
|---|---|---|---|---|---|---|---|
| 1 | 2024-12-30 | 26.7% | 26.4% | 29.0% | 32.4% | 35.9% | 39.5% |
| 1 | 2025-03-31 | 26.7% | 27.1% | 27.3% | 32.3% | 35.5% | 39.0% |
| 1 | 2025-06-30 | 27.9% | 27.8% | 30.0% | 35.0% | 36.2% | 40.3% |
| 1 | 2025-09-29 | 26.1% | 26.2% | 29.0% | 35.7% | 36.6% | 36.9% |
| 2 | 2024-12-30 | 26.7% | 26.9% | 29.5% | 32.7% | 36.6% | 39.6% |
| 2 | 2025-03-31 | 26.9% | 27.0% | 27.5% | 32.4% | 35.9% | 39.0% |
| 2 | 2025-06-30 | 28.2% | 28.0% | 30.8% | 35.4% | 37.2% | 40.4% |
| 2 | 2025-09-29 | 26.2% | 26.2% | 29.6% | 36.1% | 36.6% | 37.0% |
| 4 | 2024-12-30 | 27.3% | 27.0% | 30.3% | 32.8% | 38.2% | 39.9% |
| 4 | 2025-03-31 | 26.7% | 26.9% | 27.9% | 32.9% | 36.2% | 39.0% |
| 4 | 2025-06-30 | 28.2% | 28.2% | 31.8% | 35.9% | 38.7% | 40.5% |
| 4 | 2025-09-29 | 26.6% | 26.6% | 31.0% | 36.7% | 37.0% | 37.0% |

## Intervalos

Dispersión binomial negativa estimada en la prueba (Var = μ + μ²/k): h=1: k=2.30, h=2: k=2.28, h=4: k=2.30.

## Evaluación de las alertas de desabasto

239,271 casos (par × semana de origen) en el periodo de prueba, con existencia positiva al cierre. Un *faltante real* es al menos un día sin existencia en las dos semanas siguientes. La alerta se dispara si la existencia es menor que la demanda esperada durante el tiempo de entrega + 7 días.

| regla | alertas | faltantes reales | aciertos | precisión | exhaustividad | F1 |
|---|---|---|---|---|---|---|
| modelo (p90) | 36,907 | 11,118 | 5,736 | 15.5% | 51.6% | 0.239 |
| modelo (media) | 12,107 | 11,118 | 3,194 | 26.4% | 28.7% | 0.275 |
| promedio 4 semanas | 18,785 | 11,118 | 3,657 | 19.5% | 32.9% | 0.245 |
