# Reporte de calidad del ETL

Generado por `python -m datacore.etl --evaluar`. Compara el resultado del ETL contra `data/ground_truth` (datos limpios y bitácora de defectos inyectados).

## Carga por tabla

| tabla | leidas | cargadas | descartadas |
|---|---|---|---|
| sucursales | 12 | 12 | 0 |
| categorias | 10 | 10 | 0 |
| proveedores | 35 | 35 | 0 |
| productos | 400 | 400 | 0 |
| clientes | 8160 | 8000 | 160 |
| ventas | 181778 | 181045 | 733 |
| detalle_venta | 641954 | 640353 | 1601 |
| movimientos_inventario | 647613 | 647613 | 0 |
| inventario | 4800 | 4800 | 0 |
| incidencias | 6720 | 6720 | 0 |

## Detección de defectos inyectados

*Exhaustividad* = defectos encontrados / inyectados. *Precisión* = aciertos / registros señalados por la regla.

| defecto | inyectados | detectados | aciertos | exhaustividad | precision |
|---|---|---|---|---|---|
| cliente_casi_duplicado | 160 | 160 | 160 | 100.0% | 100.0% |
| cliente_email_faltante | 640 | 640 | 640 | 100.0% | 100.0% |
| cliente_email_invalido | 74 | 72 | 72 | 97.3% | 100.0% |
| cliente_estado_variante | 1200 | 1200 | 1200 | 100.0% | 100.0% |
| cliente_telefono_faltante | 480 | 480 | 480 | 100.0% | 100.0% |
| detalle_cantidad_negativa | 641 | 641 | 641 | 100.0% | 100.0% |
| detalle_duplicado | 1281 | 1281 | 1281 | 100.0% | 100.0% |
| detalle_precio_escala | 641 | 641 | 641 | 100.0% | 100.0% |
| detalle_producto_inexistente | 320 | 320 | 320 | 100.0% | 100.0% |
| movimiento_cantidad_cero | 648 | 648 | 648 | 100.0% | 100.0% |
| producto_categoria_faltante | 4 | 4 | 4 | 100.0% | 100.0% |
| producto_costo_mayor_precio | 4 | 4 | 4 | 100.0% | 100.0% |
| sucursal_codigo_sucio | 3621 | 3621 | 3621 | 100.0% | 100.0% |
| venta_duplicada | 724 | 724 | 724 | 100.0% | 100.0% |
| venta_fecha_formato_alterno | 3621 | 3621 | 3621 | 100.0% | 100.0% |
| venta_fecha_futura | 89 | 89 | 89 | 100.0% | 100.0% |
| venta_metodo_pago_faltante | 1811 | 1811 | 1811 | 100.0% | 100.0% |
| venta_total_inconsistente | 543 | 543 | 543 | 100.0% | 100.0% |

## Fidelidad contra la referencia

Fracción de registros cuyo valor final coincide con el original. *faltantes* = registros de la referencia que no llegaron a la tabla limpia.

| tabla | filas_referencia | filas_limpias | faltantes | fecha_hora | id_sucursal | id_cliente | metodo_pago | total | id_producto | cantidad | precio_unitario | subtotal | email | telefono | estado | costo_unitario |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ventas | 181054 | 181045 | 9 | 98.0% | 100.0% | 100.0% | 99.0% | 99.8% | — | — | — | — | — | — | — | — |
| detalle_venta | 640673 | 640353 | 320 | — | — | — | — | — | 100.0% | 100.0% | 100.0% | 100.0% | — | — | — | — |
| clientes | 8000 | 8000 | 0 | — | — | — | — | — | — | — | — | — | 91.8% | 94.1% | 100.0% | — |
| productos | 400 | 400 | 0 | — | — | — | — | — | — | — | — | — | — | — | — | 99.0% |
| movimientos_inventario | 647613 | 647613 | 0 | — | — | — | — | — | — | 100.0% | — | — | — | — | — | — |
