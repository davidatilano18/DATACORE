# Impacto en dinero de DATACORE (2025)

Generado por `python -m datacore.ml impacto`. Simulación diaria de 2025 sobre la **misma demanda real** de cada
par sucursal-producto (ventas + demanda no surtida de `data/ground_truth`) con dos políticas de resurtido.

## Conclusión

Con DATACORE, NexaTech habría perdido **14% menos ventas** ($ 249,403
recuperados) con **12% menos inventario** inmovilizado ($ 1.27 M en
promedio) y un nivel de servicio mayor: 96.0% contra 95.4%. El beneficio
neto estimado, entre margen recuperado y menor costo de mantener inventario, es de
**$ 346,250 al año**.

## Impacto de DATACORE (DATACORE p99 contra la política actual, 2025)

| concepto | política actual | DATACORE | diferencia |
|---|---|---|---|
| Ventas perdidas (unidades) | 46,227 | 39,745 | 14.0% menos |
| Ventas perdidas (pesos) | $ 4.63 M | $ 4.38 M | $ 249,403 recuperados |
| Margen perdido | $ 1.39 M | $ 1.37 M | $ 28,405 recuperados |
| Inventario promedio inmovilizado | $ 10.27 M | $ 9.00 M | 12.4% menos |
| Costo anual de mantener inventario | $ 2.57 M | $ 2.25 M | $ 317,846 de ahorro |
| Días-par con faltante | 8,525 | 8,459 | 0.8% menos |
| Nivel de servicio | 95.37% | 96.02% | +0.65 puntos |
| **Beneficio neto anual** | | | **$ 346,250** |

## Cómo se eligió el cuantil (sin mirar 2025)

DATACORE pide hasta cubrir un cuantil de la demanda esperada. El cuantil se calibró en **el periodo del 01/04/2024 al 31/12/2024**: es el menor de la
rejilla con el que DATACORE iguala o supera el nivel de servicio de la política actual ese año. Después se aplicó fijo
a 2025. Que el cuantil nominal sea alto indica que la incertidumbre por par está subestimada (el WAPE por par
ronda 77 %): un p99 nominal se comporta como un nivel de cobertura menor.

### Calibración (el periodo del 01/04/2024 al 31/12/2024)

| política | ventas perdidas (u) | ventas perdidas | margen perdido | inventario promedio | costo de mantener | días-par con faltante | nivel de servicio |
|---|---|---|---|---|---|---|---|
| Actual (órdenes reales) | 33,550 | $ 3.63 M | $ 1.14 M | $ 9.04 M | $ 1.70 M | 6,165 | 95.19% |
| DATACORE p90 | 66,500 | $ 8.82 M | $ 2.77 M | $ 5.98 M | $ 1.13 M | 13,811 | 90.46% |
| DATACORE p95 | 48,957 | $ 6.42 M | $ 2.03 M | $ 6.75 M | $ 1.27 M | 10,377 | 92.98% |
| DATACORE p97 | 39,596 | $ 5.12 M | $ 1.62 M | $ 7.33 M | $ 1.38 M | 8,428 | 94.32% |
| DATACORE p98 | 33,720 | $ 4.35 M | $ 1.38 M | $ 7.78 M | $ 1.47 M | 7,234 | 95.16% |
| **DATACORE p99** (calibrado) | 26,123 | $ 3.27 M | $ 1.04 M | $ 8.56 M | $ 1.61 M | 5,668 | 96.25% |
| DATACORE p99.5 | 20,561 | $ 2.58 M | $ 823,155 | $ 9.34 M | $ 1.76 M | 4,516 | 97.05% |

### Frontera en 2025 (todos los cuantiles, solo como referencia)

| política | ventas perdidas (u) | ventas perdidas | margen perdido | inventario promedio | costo de mantener | días-par con faltante | nivel de servicio |
|---|---|---|---|---|---|---|---|
| Actual (órdenes reales) | 46,227 | $ 4.63 M | $ 1.39 M | $ 10.27 M | $ 2.57 M | 8,525 | 95.37% |
| DATACORE p90 | 98,565 | $ 11.94 M | $ 3.69 M | $ 6.23 M | $ 1.56 M | 20,418 | 90.13% |
| DATACORE p95 | 72,680 | $ 8.60 M | $ 2.66 M | $ 7.06 M | $ 1.76 M | 15,234 | 92.72% |
| DATACORE p97 | 59,205 | $ 6.82 M | $ 2.12 M | $ 7.67 M | $ 1.92 M | 12,467 | 94.07% |
| DATACORE p98 | 50,878 | $ 5.78 M | $ 1.80 M | $ 8.15 M | $ 2.04 M | 10,723 | 94.90% |
| **DATACORE p99** (calibrado) | 39,745 | $ 4.38 M | $ 1.37 M | $ 9.00 M | $ 2.25 M | 8,459 | 96.02% |
| DATACORE p99.5 | 31,801 | $ 3.41 M | $ 1.07 M | $ 9.82 M | $ 2.46 M | 6,786 | 96.81% |

Cuantiles más altos compran servicio con inventario; más bajos, al revés.

## ¿Y si se repone solo cuando salta la alerta?

La alerta de desabasto se eligió para **avisar** con el mejor equilibrio entre aciertos y falsas alarmas (F1; ver
`backtest.md`), así que su umbral es la demanda *media* durante la entrega + 7 días, sin colchón. Usada como punto de
reorden, el pedido sale cuando ya solo queda la demanda promedio y llega sin margen. Cada regla, con su cuantil
calibrado en el año anterior:

| regla de disparo | cuantil calibrado | ventas perdidas (u) | inventario promedio | nivel de servicio | beneficio neto anual |
|---|---|---|---|---|---|
| Pedir siempre que la posición quede bajo el nivel objetivo (reposición) | p99 | 39,745 | $ 9.00 M | 96.02% | $ 346,250 |
| Pedir solo cuando salta la alerta de desabasto publicada | p99.5 | 105,855 | $ 7.65 M | 89.40% | $ -1.77 M |

Conclusión: la alerta sirve para **priorizar la revisión** de los pares en riesgo; la **cantidad y el momento del
pedido** deben salir del nivel objetivo (cuantil de la demanda), que es lo que se reporta arriba.

## Cómo se simuló

- **Política actual:** se reproducen las órdenes de compra reales de NexaTech en 2025, con sus fechas de llegada
  reales. El simulador da 46,227 unidades perdidas contra 47,976 de la
  simulación original; la diferencia viene de omitir mermas y ajustes de conteo en ambas políticas.
- **DATACORE:** cada domingo, con el pronóstico fuera de muestra del backtest (origen móvil: cada bloque de 13 semanas
  se pronostica con un modelo entrenado solo con lo anterior), calcula el cuantil de la demanda durante el día del
  pedido, el tiempo de entrega, el retraso esperado del proveedor y la semana de revisión, y pide lo que falte para
  cubrirlo contando la existencia y lo ya pedido. Como el modelo aprende de ventas, que subestiman la demanda cuando
  hubo faltantes, el pronóstico se divide entre (1 − fracción de días agotado en las últimas 4 semanas), hasta
  ×2.

## Supuestos (configurables en `Supuestos` o por línea de comandos)

| supuesto | valor | fuente |
|---|---|---|
| Precio y costo | lista vigente de `core.productos`, sin descuentos | catálogo |
| Margen | precio − costo de cada producto | catálogo |
| Costo anual de mantener inventario | 25% del costo | supuesto (capital, almacén, seguro, obsolescencia); `--tasa-mantener` |
| Revisión de DATACORE | semanal (pedido los lunes) | la política actual revisa a diario |
| Retraso de proveedores | sorteo con la tasa y el retraso medio de cada proveedor antes del año simulado | `ground_truth/ordenes_compra` |
| Venta perdida | la demanda sin existencia se pierde, no se acumula | igual que el generador |
| Mermas y ajustes de conteo | se omiten en ambas políticas | aislar la política de resurtido |
| Productos descontinuados | se deja de resurtir 30 días antes de la baja, en ambas | regla del generador |

**Lectura:** *días-par con faltante* son los días en que algún cliente no encontró el producto en una sucursal.
*Nivel de servicio* es la fracción de la demanda que se surtió. *Inventario promedio* es el valor a costo de la
existencia diaria promedio, y sobre él se calcula el costo de mantener.

**Limitaciones:** los pronósticos se calcularon con la historia real (la de la política actual), no con la que habría
generado DATACORE; la corrección de censura compensa una parte. El resultado vale para estos datos simulados.
