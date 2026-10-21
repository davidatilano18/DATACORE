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

## Resultados con origen móvil (52 semanas de prueba)

`python -m datacore.ml evaluar` usa por defecto **4 bloques consecutivos de 13 semanas** (de enero a diciembre de 2025). Cada bloque se pronostica con un modelo entrenado solo con las semanas anteriores a su inicio.

| WAPE producto-semana, año completo | h=1 | h=2 | h=4 |
|---|---|---|---|
| **Modelo** | **26.9 %** | **27.0 %** | **27.2 %** |
| Media móvil de 8 semanas | 28.8 % | 29.3 % | 30.2 % |
| SBA | 33.9 % | 34.2 % | 34.6 % |
| Ingenuo | 36.0 % | 36.6 % | 37.5 % |
| Estacional | 38.9 % | 39.0 % | 39.1 % |

**El modelo es el mejor método en los 12 casos** (4 bloques × 3 horizontes). Su ventaja sobre la media móvil va de 0.6 puntos (bloque de abril a junio, h=1) a 4.4 puntos (octubre a diciembre, h=4): crece justo en la temporada de Buen Fin y Navidad, cuando el calendario más importa. El sesgo se mantiene entre −1.4 % y −1.1 %. El detalle por bloque está en `reports/ml/backtest.md`.

## Resultados del primer backtest (13 semanas: octubre a diciembre de 2025)

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

*(Primer backtest de 13 semanas. Con el origen móvil de 52 semanas, 239,271 casos, los resultados se sostienen: el percentil 90 tiene 51.6 % de exhaustividad y 15.5 % de precisión; con el valor medio, el modelo logra F1 0.275 contra 0.245 del promedio simple.)*

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

## Detección de anomalías (RF-13)

`python -m datacore.ml anomalias` revisa el ingreso y los tickets diarios de cada sucursal (`kpi.ventas_diarias_sucursal`) y reemplaza `ops.anomalias` en una transacción. La API la expone en `GET /anomalias` y el dashboard la muestra en *Calidad y operación*. Lo implementó Codex; el cambio a la prueba de Poisson se hizo en la revisión.

**Valor esperado** (solo con datos pasados): la mediana de los últimos 8 días iguales de la semana (mínimo 6), multiplicada por la tendencia reciente (mediana de la razón observado/base de los 28 días previos, acotada entre 0.5 y 2).

**Prueba:**
- **Tickets:** como son conteos, se calcula la cola de Poisson (p medio) del valor observado contra el esperado y se expresa como z normal.
- **Ingreso:** z robusto con MAD de los residuos de los 56 días previos. Se publica como información adicional, pero no se usa para evaluar: los tickets grandes de los mayoristas lo hacen muy ruidoso (F1 de 0.04 por sí solo).

Las fechas especiales del calendario (Buen Fin, Reyes, 10 de mayo, Navidad, etc.) se excluyen explícitamente: con solo tres años, una referencia anual sería muy escasa. A cambio, no se detectan fallas en esos días.

**Evaluación** contra los 325 días-sucursal con falla del punto de venta (`ground_truth/fallas_sistema`, usado solo para medir):

| Detector | Umbral | Precisión | Exhaustividad | F1 |
|---|---|---|---|---|
| **Poisson sobre tickets (publicado)** | z < −2.33 (cola de 1 %) | **38.6 %** | **29.5 %** | **0.335** |
| Poisson sobre tickets | z < −2.58 (0.5 %) | 43.2 % | 22.5 % | 0.296 |
| MAD sobre ingreso y tickets (primera versión) | z < −2.5 | 23.8 % | 13.5 % | 0.173 |

Exhaustividad por duración de la falla (umbral publicado): 2-3 h, 12.7 %; 4-5 h, 15.2 %; **6-8 h, 49.6 %**. Una falla de 2 o 3 horas reduce los tickets de 17 a 25 %, una variación que el ruido normal de un día (unos 10 a 20 tickets por sucursal) ya alcanza, así que es casi indetectable con datos diarios. Las caídas largas sí se distinguen. El umbral se eligió por F1 sobre el mismo historial (selección exploratoria, no fuera de muestra). Detalle: [`reports/ml/anomalias.md`](../reports/ml/anomalias.md).

## Limitaciones

- La validación con origen móvil cubre un año (2025). Con más historia podrían usarse más bloques.
- Los productos descontinuados no tienen fecha de baja en `core`. Se excluyen de la publicación con el campo `activo`, pero sí aparecen en el entrenamiento con ceros.
- Las sucursales y los productos nuevos tienen poca historia; el modelo se apoya en categoría, región y media del producto.
