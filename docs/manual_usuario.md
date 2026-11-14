# Manual de usuario de DATACORE

Para quien consulta la información de NexaTech Solutions (empresa ficticia): dirección, compras, almacén y sucursales.
Se usa desde el navegador, en el **dashboard**.

## Antes de empezar

- El dashboard está en https://datacore-dashboard-production.up.railway.app (en local: `http://localhost:8501`).
- Los datos se actualizan cada lunes, de madrugada. Cada página muestra arriba a la derecha el sello **Corte de datos** con la fecha de la información; el detalle de la última carga está en *Inicio → Estado de la plataforma*.
- Los montos están en pesos mexicanos (MXN).
- Las tablas se pueden ordenar haciendo clic en el encabezado y descargar como CSV desde el menú de la propia tabla.

## Páginas

### Inicio: resumen ejecutivo
- **Franja de indicadores:** ingreso, tickets y ticket promedio de los últimos 12 meses (con su variación frente a los 12 meses previos) y clientes activos.
- **Salud del inventario:** una barra reparte todos los pares sucursal-producto por estado (sin existencia, bajo mínimo, exceso, sin rotación y normal). Debajo están las alertas pendientes de cada tipo y las incidencias abiertas.
- **Red de sucursales:** un mapa con las 12 sucursales; el tamaño del punto es su ingreso de 12 meses y el anillo rojo marca las tres con más alertas pendientes. Pasa el cursor sobre un punto para ver su detalle. El mapa es esquemático: las sucursales de una misma ciudad aparecen ligeramente separadas. Debajo, una tarjeta por sucursal con su ingreso, su tendencia mensual y sus alertas por tipo.
- **Ingreso mensual y categorías:** el año en curso contra los dos anteriores y el ingreso por categoría.
- **Estado de la plataforma:** si la API, el último ETL y el modelo están al día.

### Ventas
1. Elige el **Periodo** (Últimos 30 días, 90 días, 12 meses, Año 2025, Todo o Personalizado; por defecto, los últimos 30 días) y, si quieres, una **sucursal**.
2. **Franja de indicadores:** ingreso, tickets, ticket promedio y unidades del periodo, con su variación frente al periodo anterior de la misma duración.
3. **Ingreso diario y tendencia:** el ingreso de cada día y su media móvil de 7 días (la línea suave muestra la tendencia).
4. **Patrón semanal:** el ingreso promedio de cada día de la semana, de lunes a domingo.
5. **Ventas por sucursal:** el ingreso de cada sucursal en el periodo, ordenado de mayor a menor.
6. **Mezcla por categoría:** cómo se reparte el ingreso entre categorías mes con mes.
7. **Clasificación ABC histórica:** con todas las sucursales y todo el historial, los productos A generan el 80 % del ingreso; los B, el siguiente 15 %; los C, el resto. Usa el buscador para encontrar un SKU o producto.

### Inventario
Arriba, una barra reparte todos los pares sucursal-producto por estado, con su cantidad y porcentaje; debajo, las mismas cifras una por una.

- **Pares por estado:**
  - *sin existencia*: no hay piezas;
  - *bajo mínimo*: hay menos piezas que el stock mínimo;
  - *exceso*: alcanza para más de 180 días;
  - *sin rotación*: hay piezas pero nada se vendió en 90 días;
  - *normal*.
- **Distribución por sucursal:** los pares de cada sucursal por estado, para ver dónde se concentran los faltantes.
- **Desabasto a lo largo del tiempo:** un mapa de calor por sucursal y mes con el porcentaje de días en que los productos estuvieron sin existencia; un tono más oscuro indica más desabasto.
- **Cobertura de inventario:** tabla con cuántos días alcanza la existencia al ritmo de venta de los últimos 90 días. Se filtra por estado y sucursal, y tiene un buscador de SKU o producto.

### Alertas
Las genera el modelo de pronóstico cada día. Arriba se ve cuántas hay pendientes de cada tipo:

| Alerta | Qué significa | Qué hacer |
|---|---|---|
| **Riesgo de desabasto** | La existencia probablemente no alcanza hasta que llegue un nuevo pedido (tiempo de entrega + 1 semana). | Revisar y adelantar el pedido al proveedor. |
| **Exceso de inventario** | Al ritmo pronosticado, la existencia dura más de 180 días. | Frenar las compras, considerar promociones o traspasos a otras sucursales. |
| **Sin rotación** | Hay piezas, no se vende nada desde hace 13 semanas y no se espera demanda. | Evaluar liquidar o descontinuar. |

El desplegable **Cómo interpretar las alertas** repite estas reglas. La tabla **Alertas pendientes** se filtra por tipo, sucursal y categoría, y tiene un buscador de SKU o producto.

Cada alerta de **riesgo de desabasto** trae dos columnas para actuar:

- **Pedir (u):** las unidades para llegar al nivel recomendado (la demanda esperada mientras llega el pedido, más un colchón para la variación). No descuenta pedidos que ya estén en camino: réstalos tú.
- **Pedir a más tardar:** el último día para pedir y recibir antes de que se agote, al ritmo de venta esperado. La lista muestra primero las más urgentes y, arriba de la tabla, el total de unidades sugeridas.

La columna **Motivo principal** dice por qué salió la alerta (por ejemplo, "Ya no hay existencia y un pedido tarda 6 días en llegar"). Si **seleccionas una o varias filas**, debajo de la tabla aparece en **¿Por qué?** la explicación completa de cada una (de hasta 5 filas a la vez), con 2 o 3 factores (temporada, tendencia, días que estuvo agotado…) y el pedido sugerido.

Para registrar que una alerta ya se atendió, selecciónala en la lista y pulsa **Marcar como atendidas**. Desaparece de los pendientes.

Al final, la gráfica **Alertas por sucursal** muestra cuántas alertas de cada tipo tiene cada sucursal, para repartir la revisión.

> En las pruebas, una de cada cuatro alertas de desabasto terminó en un faltante real, y las alertas anticiparon cerca de un tercio de los faltantes. Úsala como lista de revisión priorizada, no como orden de compra automática. Si el producto estuvo agotado en las últimas semanas, la alerta lo toma en cuenta: en ese tiempo se vendió menos de lo que los clientes pidieron.

### Pronóstico
1. Busca un producto por nombre o SKU y elígelo de la lista. El pronóstico es del total de las sucursales.
2. **Franja de indicadores:** demanda esperada de las próximas 4 semanas (con su intervalo del 80 %), lo que se vendió en las últimas 4 semanas, la existencia actual en todas las sucursales y la clase ABC del producto.
3. **Historia y próximas cuatro semanas:** la gráfica muestra las ventas de las últimas 52 semanas y el **pronóstico de las próximas 4**, con una banda sombreada: el intervalo donde se espera que caiga la demanda 8 de cada 10 veces. La línea punteada marca el corte de datos.
4. **Próxima semana por sucursal:** la demanda esperada de cada sucursal, de mayor a menor.
5. **Qué tan bueno es el modelo:** su error (WAPE, el error absoluto como porcentaje del volumen real; menor es mejor) para cada una de las 4 semanas, comparado con una media móvil de 8 semanas.

### Calidad y operación
La página tiene cuatro pestañas:

- **Calidad de datos:**
  - *Hallazgos de la última carga:* cuántos registros corrigió, rechazó o marcó el proceso de calidad, por regla (por ejemplo, fechas en otro formato o clientes duplicados).
  - *Ejecuciones del ETL:* filas leídas, cargadas y descartadas de cada tabla, con su estado y mensaje de error.
- **Anomalías:** elige una sucursal para ver sus tickets diarios con las caídas y los picos fuera de lo normal (sin contar días festivos conocidos), que señalan días para investigar.
- **Incidencias:** las *Incidencias mensuales* (reportes de desabasto, retrasos de proveedor, fallas del sistema, etc.) y la lista de *Incidencias abiertas* o en proceso.
- **Plataforma:** si la API, la base de datos, el ETL y el modelo están disponibles, y los últimos chequeos de monitoreo, respaldos y corridas diarias.

## Preguntas frecuentes

**¿Por qué el total de ventas no coincide exactamente con el del sistema de punto de venta?**
El proceso de calidad elimina tickets duplicados y descarta los renglones con productos inexistentes. Los detalles están en *Calidad y operación → Calidad de datos*.

**¿Por qué una sucursal tiene menos historia?**
QRO03 (abril de 2024) y MOR01 (septiembre de 2024) abrieron dentro del periodo.

**La página muestra un mensaje rojo de conexión.**
El servicio de datos (API) no está disponible. Avisa al equipo de sistemas.
