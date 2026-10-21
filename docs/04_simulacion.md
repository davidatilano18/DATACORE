# 04 · Reglas de simulación de datos

Generador: `python -m datacore.generator --seed 42 --salida data` (unos 15 s).
La configuración vive en [`src/datacore/generator/config.py`](../src/datacore/generator/config.py).

## Resultado con semilla 42

| Tabla | Filas |
|---|---|
| sucursales | 12 |
| categorias | 10 |
| proveedores | 35 |
| productos | 400 |
| clientes | 8,000 (+160 casi duplicados en el crudo) |
| ventas | 181,054 |
| detalle_venta | 640,673 |
| movimientos_inventario | 647,613 |
| inventario | 4,800 |
| incidencias | 6,720 |
| órdenes de compra (oculta) | 124,072 |

Demanda no surtida por faltante de existencia: **4.7 %**. Defectos inyectados en los crudos: **16,502**.

## Orden de generación

1. **Catálogos:** sucursales, categorías, proveedores, productos y clientes.
2. **Demanda:** tickets y renglones según afluencia, calendario y mezcla de productos.
3. **Inventario:** simulación día a día; la demanda que no alcanza existencia se pierde.
4. **Ventas finales:** se recortan los renglones a lo que realmente se surtió (en orden de llegada).
5. **Incidencias:** se derivan de eventos reales de la simulación.
6. **Exportación:** se guarda la verdad de referencia y luego se generan los crudos con defectos.

## Patrones de demanda

| Patrón | Regla |
|---|---|
| Afluencia por sucursal | Tickets por día ~ Poisson(λ): grande 19, mediana 13, pequeña 8.5. |
| Maduración | Una sucursal nueva arranca al 45 % de su afluencia y llega al 100 % en unos 6 meses. |
| Día de la semana | Lun 0.85, mar 0.85, mié 0.90, jue 0.95, vie 1.15, sáb 1.35, dom 1.00. |
| Quincena | Días 1, 15, 16 y fin de mes: ×1.15. |
| Fechas especiales | Buen Fin (viernes a lunes antes del tercer lunes de noviembre) ×1.9 con descuentos; del 18 al 24 de diciembre hasta ×1.6; 25 de diciembre y 1 de enero ×0.3; 5 de enero (Reyes) ×1.5; 30 de abril ×1.3; 10 de mayo ×1.5; 16 de septiembre ×0.6. |
| Estacionalidad por categoría | Perfiles mensuales: *plano*, *verano* (Bebidas), *fin de año* (Electrónica), *escolar* (Papelería, pico en agosto), *juguetes* (diciembre, enero y abril), *hogar* (mayo y diciembre), *dulcería* (octubre y diciembre). |
| Popularidad | Lognormal (σ = 1.1): pocos productos concentran la mayor parte de las ventas (curva ABC). |
| Tendencia por producto | Crecimiento anual ~ N(6 %, 12 %), acotado entre −35 % y +60 %. Hay productos que crecen y otros que caen. |
| Tendencia de tráfico | +3 % anual en el número de tickets. |
| Afinidad regional | Cada región tiene un multiplicador de 0.7 a 1.3 por categoría. |
| Ciclo de vida | Unos 8 % de los productos se lanzan dentro del periodo y unos 5 % se descontinúan. |
| Clientes | 30 % de los tickets son de público general. Cada cliente compra 90 % en su sucursal preferida, con frecuencia lognormal. Los mayoristas llevan +2 renglones en promedio y ×4 de cantidad. |
| Precios | Lista anual con inflación de alrededor de 5 % ± 3 %, actualizada cada enero. |
| Fallas de sistema | Unas 0.8 fallas por sucursal al mes; ese día la afluencia baja en proporción a las horas sin servicio. |

## Política de inventario

Revisión diaria con política (s, S) por par sucursal-producto:

- **s** (punto de reorden) = demanda estimada × (tiempo de entrega + días de seguridad) + 1.65·√(demanda × tiempo de entrega) + colchón de 1 a 4 pedidos típicos.
- **S** (nivel máximo) = s + demanda estimada × 10 a 35 días de cobertura.
- La **demanda estimada** tiene un error fijo por par (×0.55 a ×1.45) y se recalibra cada 90 días con las *ventas* observadas, no con la demanda. Por eso los faltantes sesgan la estimación hacia abajo (censura); para limitarlo, la estimación no baja más de 20 % por trimestre.
- **Retrasos:** cada proveedor tiene una probabilidad de retraso de 3 a 35 %; un retraso suma de 2 a 8 días.
- **Mermas:** solo productos perecederos, probabilidad diaria de 0.4 %.
- **Conteo físico:** al cierre de cada trimestre, alrededor del 12 % de los pares recibe un ajuste ~ N(0, 2.5).
- **Descontinuados:** se dejan de resurtir 30 días antes de la baja y lo que sobra queda como inventario muerto.

Esto produce de forma natural los dos problemas que el módulo de IA debe atacar: **desabasto** (estacionalidad, subestimación, retrasos) y **exceso** (sobreestimación, productos en declive o descontinuados).

## Incidencias

| Tipo | Origen | Se reporta |
|---|---|---|
| FALLA_SISTEMA | Días con el POS caído | 100 % |
| DESABASTO | Episodios de faltante con 5 o más unidades perdidas | 30 % |
| RETRASO_PROVEEDOR | Entregas con 5 o más días de retraso | 25 % |
| MERCANCIA_DANADA | Mermas de 5 o más piezas | 50 % |
| DIFERENCIA_INVENTARIO | Ajustes de conteo de 5 o más piezas | 70 % |
| QUEJA_CLIENTE | Aleatorio, unas 0.3 por sucursal al mes | — |

## Defectos inyectados en `data/raw`

Cada defecto queda en `data/ground_truth/defectos_inyectados.csv` (tabla, clave, tipo, valor original y valor sucio).

| Defecto | Tasa | Ejemplo |
|---|---|---|
| venta_duplicada | 0.4 % | El mismo ticket aparece dos veces. |
| venta_fecha_formato_alterno | 2 % | `17/11/2024 13:05` en lugar de ISO. |
| venta_fecha_futura | 0.05 % | Año 2027 o 2031. |
| venta_metodo_pago_faltante | 1 % | Vacío. |
| venta_total_inconsistente | 0.3 % | Total ×0.1, ×0.5, ×1.5 o ×10. |
| sucursal_codigo_sucio | 2 % | `qro01`, ` QRO01 `, `QRO-01`. |
| detalle_cantidad_negativa | 0.1 % | −3. |
| detalle_precio_escala | 0.1 % | Precio ×10 o ×0.1 (punto decimal mal capturado). |
| detalle_producto_inexistente | 0.05 % | SKU `NX-ZZZ-9xxxx`. |
| detalle_duplicado | 0.2 % | El mismo renglón dos veces. |
| cliente_casi_duplicado | 2 % | Mismo teléfono, nombre en mayúsculas o sin acentos; 30 % de sus compras quedan a nombre del duplicado. |
| cliente_email_faltante / telefono_faltante | 8 % / 6 % | Vacío. |
| cliente_email_invalido | 1 % | Sin `@`, `.con`, espacios. |
| cliente_estado_variante | 15 % | `Qro`, `CDMX`, `D.F.`, `Nuevo Leon`. |
| producto_categoria_faltante | 1 % | Vacío. |
| producto_costo_mayor_precio | 1 % | Costo mayor que el precio. |
| movimiento_cantidad_cero | 0.1 % | Cantidad 0. |

Además hay problemas de formato estructurales: clientes en **Windows-1252 con `;`**, catálogos en **Excel**, y ventas y movimientos **partidos por año**.

## Datos ocultos (`ground_truth/`)

Estos datos no se exportan como fuentes, pero sirven para evaluar:

- `demanda_perdida.parquet`: unidades no surtidas por día, sucursal y producto. Sirve para medir qué tanto el modelo recupera la demanda real.
- `ordenes_compra.parquet`: órdenes con su retraso real.
- `parametros_productos.parquet`: popularidad, tendencia y fecha de baja de cada producto.
- `fallas_sistema.parquet`: días con el POS caído.
