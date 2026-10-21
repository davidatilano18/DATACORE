# Evaluación del modelo de demanda semanal

Backtest fuera de muestra: entrenamiento con semanas anteriores a **2025-09-29**; prueba en las 13 semanas siguientes (incluye Buen Fin y Navidad). Generado por `python -m datacore.ml evaluar`.

**WAPE** = Σ|real − pronóstico| / Σ real (menor es mejor). **Sesgo** = Σ(pronóstico − real) / Σ real (negativo = subestima). *par* = sucursal-producto-semana; *producto-semana* = suma de sucursales.

## Contra ventas observadas

### par (todos)

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -4.2% | -2.6% | -2.6% | 76.7% | 76.9% | 77.2% |
| gbm | -1.3% | -0.3% | -0.7% | 77.4% | 77.7% | 77.9% |
| media_movil_8 | -1.1% | -1.4% | -1.7% | 81.1% | 81.0% | 81.2% |
| sba | 1.4% | 1.3% | 1.3% | 85.1% | 85.2% | 85.4% |
| estacional | 1.3% | 1.3% | 1.3% | 99.3% | 99.2% | 99.2% |
| ingenuo | -0.6% | -1.0% | -0.1% | 100.9% | 99.8% | 99.7% |

### producto-semana

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm | -1.3% | -0.3% | -0.7% | 26.1% | 26.2% | 26.6% |
| gbm_sin_censura | -4.2% | -2.6% | -2.6% | 26.2% | 26.2% | 26.6% |
| media_movil_8 | -1.1% | -1.4% | -1.7% | 29.0% | 29.6% | 31.0% |
| sba | 1.4% | 1.3% | 1.3% | 35.7% | 36.1% | 36.7% |
| ingenuo | -0.6% | -1.0% | -0.1% | 36.6% | 36.6% | 37.0% |
| estacional | 1.3% | 1.3% | 1.3% | 36.9% | 37.0% | 37.0% |

### clase A

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -1.8% | -0.2% | 0.4% | 58.2% | 58.1% | 58.8% |
| gbm | -0.3% | 1.4% | 0.9% | 58.0% | 58.5% | 58.8% |
| media_movil_8 | -1.7% | -2.2% | -2.8% | 61.2% | 61.2% | 61.7% |
| sba | 2.7% | 2.6% | 2.5% | 68.0% | 68.0% | 68.3% |
| ingenuo | -0.6% | -1.2% | -0.4% | 79.3% | 77.6% | 78.0% |
| estacional | 7.2% | 7.1% | 7.1% | 80.9% | 80.9% | 80.9% |

### clase B

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -5.5% | -3.8% | -4.1% | 83.8% | 84.1% | 84.2% |
| gbm | -2.1% | -1.1% | -1.8% | 84.5% | 84.8% | 84.9% |
| media_movil_8 | -0.2% | -0.3% | -0.3% | 89.1% | 88.8% | 89.0% |
| sba | -0.4% | -0.4% | -0.2% | 89.4% | 89.4% | 89.5% |
| estacional | -1.8% | -1.8% | -1.8% | 108.8% | 108.8% | 108.8% |
| ingenuo | -0.5% | -1.0% | 0.4% | 111.2% | 109.7% | 109.9% |

### clase C

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -8.3% | -7.1% | -8.0% | 113.0% | 113.4% | 113.3% |
| gbm | -2.9% | -3.2% | -3.1% | 115.5% | 115.5% | 115.4% |
| media_movil_8 | -0.9% | -1.0% | -1.4% | 119.5% | 119.4% | 119.0% |
| sba | 0.5% | 0.5% | 0.4% | 122.0% | 122.1% | 122.3% |
| estacional | -8.8% | -8.8% | -8.7% | 131.4% | 131.2% | 131.3% |
| ingenuo | -0.8% | -0.6% | 0.0% | 140.1% | 141.2% | 139.1% |

## Contra demanda real

La demanda real (ventas + demanda no surtida) solo existe en la simulación. Mide si el modelo recupera la demanda que los faltantes ocultan.

### par (todos)

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -9.2% | -7.7% | -7.7% | 76.2% | 76.1% | 76.4% |
| gbm | -6.4% | -5.4% | -5.8% | 76.9% | 76.9% | 77.1% |
| media_movil_8 | -6.2% | -6.5% | -6.8% | 80.0% | 80.2% | 80.5% |
| sba | -3.9% | -3.9% | -4.0% | 84.2% | 84.4% | 84.6% |
| estacional | -3.9% | -3.9% | -3.9% | 97.3% | 97.2% | 97.2% |
| ingenuo | -5.8% | -6.1% | -5.3% | 97.1% | 97.5% | 97.7% |

### producto-semana

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm | -6.4% | -5.4% | -5.8% | 27.3% | 27.3% | 27.6% |
| gbm_sin_censura | -9.2% | -7.7% | -7.7% | 27.7% | 27.4% | 27.7% |
| media_movil_8 | -6.2% | -6.5% | -6.8% | 29.7% | 30.4% | 31.8% |
| ingenuo | -5.8% | -6.1% | -5.3% | 35.9% | 36.6% | 37.0% |
| estacional | -3.9% | -3.9% | -3.9% | 37.2% | 37.2% | 37.3% |
| sba | -3.9% | -3.9% | -4.0% | 36.9% | 37.3% | 37.9% |

### clase A

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -6.1% | -4.6% | -4.0% | 57.8% | 57.6% | 58.2% |
| gbm | -4.6% | -3.0% | -3.6% | 57.9% | 57.9% | 58.3% |
| media_movil_8 | -6.0% | -6.5% | -7.0% | 60.5% | 60.8% | 61.3% |
| sba | -1.8% | -1.9% | -2.0% | 67.4% | 67.6% | 67.9% |
| ingenuo | -5.0% | -5.5% | -4.8% | 76.5% | 75.9% | 76.7% |
| estacional | 2.5% | 2.4% | 2.4% | 79.5% | 79.4% | 79.4% |

### clase B

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -10.9% | -9.2% | -9.6% | 83.0% | 83.1% | 83.2% |
| gbm | -7.6% | -6.7% | -7.3% | 83.7% | 83.9% | 84.0% |
| media_movil_8 | -5.9% | -5.9% | -5.9% | 87.5% | 87.6% | 88.0% |
| sba | -6.0% | -6.0% | -5.9% | 88.3% | 88.5% | 88.6% |
| estacional | -7.4% | -7.4% | -7.3% | 106.0% | 106.0% | 106.0% |
| ingenuo | -6.1% | -6.6% | -5.3% | 106.4% | 106.7% | 107.3% |

### clase C

| método | sesgo h=1 | sesgo h=2 | sesgo h=4 | wape h=1 | wape h=2 | wape h=4 |
|---|---|---|---|---|---|---|
| gbm_sin_censura | -14.3% | -13.1% | -13.9% | 111.4% | 111.6% | 111.5% |
| gbm | -9.2% | -9.5% | -9.3% | 113.8% | 113.6% | 113.5% |
| media_movil_8 | -7.3% | -7.4% | -7.7% | 117.0% | 117.2% | 116.9% |
| sba | -5.9% | -6.0% | -6.1% | 119.7% | 119.8% | 120.0% |
| estacional | -14.7% | -14.7% | -14.6% | 128.4% | 128.3% | 128.4% |
| ingenuo | -7.2% | -7.0% | -6.5% | 134.2% | 137.1% | 135.6% |

## Intervalos

Dispersión binomial negativa estimada en la prueba (Var = μ + μ²/k): h=1: k=2.31, h=2: k=2.35, h=4: k=2.33.

## Evaluación de las alertas de desabasto

60,527 casos (par × semana de origen) en el periodo de prueba, con existencia positiva al cierre. Un *faltante real* es al menos un día sin existencia en las dos semanas siguientes. La alerta se dispara si la existencia es menor que la demanda esperada durante el tiempo de entrega + 7 días.

| regla | alertas | faltantes reales | aciertos | precisión | exhaustividad | F1 |
|---|---|---|---|---|---|---|
| modelo (p90) | 10,359 | 3,102 | 1,677 | 16.2% | 54.1% | 0.249 |
| modelo (media) | 3,436 | 3,102 | 955 | 27.8% | 30.8% | 0.292 |
| promedio 4 semanas | 5,019 | 3,102 | 1,029 | 20.5% | 33.2% | 0.253 |
