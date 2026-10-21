# 05 · Modelo de pronóstico de demanda y alertas

Código: `src/datacore/ml/`. Resultados completos: [`reports/ml/backtest.md`](../reports/ml/backtest.md).

```powershell
.venv\Scripts\python -m datacore.ml evaluar    # backtest contra baselines (~4 min)
.venv\Scripts\python -m datacore.ml publicar   # entrena, pronostica 4 semanas y genera alertas (~8 min)
```

## Planteamiento

| Decisión | Elección | Motivo |
|---|---|---|
| Unidad de pronóstico | Unidades por **semana** (lunes a domingo), sucursal y producto | Por día, el 89 % de los días-par no tiene venta (EDA). Por semana baja a 57 % y coincide con el ciclo de compras. |
| Horizontes | 1 a 4 semanas, **un modelo por horizonte** (estrategia directa) | Se cubre el tiempo de entrega (2 a 10 días) más la revisión semanal sin acumular errores recursivos. |
| Algoritmo | `HistGradientBoostingRegressor` con pérdida **Poisson**, un solo modelo global para los 4,800 pares | Maneja conteos con muchos ceros, aprende patrones compartidos entre pares con poca historia y entrena en alrededor de 1 minuto por horizonte. |
| Validación | Backtest fuera de muestra: entrenamiento hasta el 28 de septiembre de 2025 y prueba en las 13 semanas siguientes | Incluye Buen Fin y Navidad, el periodo más difícil. |
| Métrica principal | **WAPE** (error absoluto ponderado) y **sesgo** | El MAPE no está definido con ceros; el WAPE pondera por volumen, que es lo que importa al negocio. |

## Variables (37)

Para el horizonte *h*, todo rezago o ventana usa datos hasta *t − h* (lo verifica la prueba `test_sin_fuga_de_informacion`).

- **Historia del par:** rezagos de 1 a 4 semanas; misma semana del año anterior (simple y suavizada); medias móviles de 4, 8, 13 y 26 semanas; desviación estándar; máximo; fracción de semanas en cero; suavizamiento exponencial; media histórica; pronóstico SBA.
- **Disponibilidad:** fracción de días sin existencia en la semana de origen y en las últimas 4 semanas. Permite al modelo distinguir "no se vendió porque no había" de "no se vendió porque no lo pidieron".
- **Contexto:** precio cobrado; media del producto en todas las sucursales; índice estacional de la categoría (la semana equivalente del año pasado contra su vecindad).
- **Calendario** (se conoce de antemano): semana del año, mes, Buen Fin, Navidad, fin de año, Reyes, Día de las Madres, Día del Niño, regreso a clases y número de quincenas en la semana.
- **Atributos:** sucursal, categoría, región, tamaño de sucursal, días de entrega del proveedor y semanas de vida del par.

## Resultados (13 semanas de prueba)

| WAPE | h=1 | h=2 | h=4 |
|---|---|---|---|
| **Modelo**, producto-semana | **26.1 %** | **26.2 %** | **26.6 %** |
| Media móvil de 8 semanas | 29.0 % | 29.6 % | 31.0 % |
| SBA (Syntetos-Boylan) | 35.7 % | 36.1 % | 36.7 % |
| Ingenuo (semana anterior) | 36.6 % | 36.6 % | 37.0 % |
| Estacional (año anterior) | 36.9 % | 37.0 % | 37.0 % |
| **Modelo**, par sucursal-producto | **77.4 %** | **77.7 %** | **77.9 %** |
| Media móvil 8, par | 81.1 % | 81.0 % | 81.2 % |

- El modelo es el mejor método en todos los horizontes y segmentos ABC, con un sesgo de −1.3 % a −0.3 %.
- Al pronosticar 4 semanas en lugar de 1, el error del modelo sube solo 0.5 puntos; el de la media móvil sube 2.
- Por sucursal-producto el error es alto porque la mayoría de los pares vende pocas unidades de forma irregular. Ningún método baja de 76 %. Por eso las alertas usan **intervalos**, no solo el valor puntual.

### Demanda censurada

Las semanas con faltante muestran menos venta que la demanda real. Como el simulador guarda la demanda no surtida (`ground_truth/demanda_perdida`), se puede medir contra la demanda real:

| Contra demanda real (producto-semana, h=1) | WAPE | Sesgo |
|---|---|---|
| Modelo entrenado con todas las semanas | 27.3 % | −6.4 % |
| Modelo que excluye semanas con 3 o más días sin existencia | 27.7 % | −9.2 % |

Excluir las semanas censuradas **empeoró** el sesgo, contra lo que se esperaba. Una explicación plausible es que las variables de disponibilidad ya le indican al modelo cuándo la venta está limitada. El modelo publicado usa todas las semanas. El −6 % residual es aproximadamente la demanda que se pierde por faltantes y que ninguna venta registra.

## Intervalos y alertas

- **Intervalo del 80 %:** binomial negativa con media igual al pronóstico y dispersión *k* estimada en el backtest (Var = μ + μ²/k).
- **Demanda en reposición:** suma de los pronósticos semanales prorrateados a (días de entrega + 7) días, con su percentil 90.

| Alerta | Regla |
|---|---|
| `RIESGO_DESABASTO` | Existencia actual < percentil 90 de la demanda en el tiempo de reposición. |
| `EXCESO_INVENTARIO` | Cobertura = existencia ÷ demanda diaria pronosticada > 180 días. |
| `SIN_ROTACION` | Existencia > 0, cero ventas en 13 semanas y pronóstico < 0.25 unidades por semana. |

### ¿Las alertas de desabasto anticipan faltantes reales?

En cada semana del periodo de prueba se aplicó la regla con el pronóstico de ese momento y la existencia al cierre de la semana. Después se revisó si en las **dos semanas siguientes** hubo al menos un día sin existencia. Fueron 60,527 casos con existencia positiva, de los cuales 3,102 (5.1 %) terminaron en faltante.

| Regla | Alertas | Aciertos | Precisión | Exhaustividad | F1 |
|---|---|---|---|---|---|
| Modelo, percentil 90 (**publicada**) | 10,359 | 1,677 | 16.2 % | **54.1 %** | 0.249 |
| Modelo, valor medio | 3,436 | 955 | **27.8 %** | 30.8 % | **0.292** |
| Promedio de 4 semanas (sin modelo) | 5,019 | 1,029 | 20.5 % | 33.2 % | 0.253 |

- Con el mismo umbral (valor medio), el modelo es **más preciso** que el promedio simple (27.8 % contra 20.5 %) y tiene la mejor F1.
- La regla publicada usa el percentil 90 a propósito: **anticipa más de la mitad de los faltantes**, a cambio de unas 5 alertas falsas por cada acierto. Para un almacén es preferible revisar alertas de más que quedarse sin producto.
- El umbral se puede ajustar según el costo relativo de un faltante frente al de revisar una alerta. Es una mejora natural para una siguiente versión.

Las alertas se escriben en `ops.alertas_inventario`; los pronósticos, en `ops.predicciones_demanda`; y la versión del modelo con sus métricas, en `ops.modelos`.

## Limitaciones

- El periodo de prueba es uno solo. Un backtest con varios orígenes (*rolling origin*) daría una estimación más robusta.
- Los productos descontinuados no tienen fecha de baja en `core`. Se excluyen de la publicación con el campo `activo`, pero sí aparecen en el entrenamiento con ceros.
- Las sucursales y los productos nuevos tienen poca historia; el modelo se apoya en categoría, región y media del producto.
