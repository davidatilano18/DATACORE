# Manual de usuario de DATACORE

Para quien consulta la información de NexaTech Solutions (empresa ficticia): dirección, compras, almacén y sucursales.
Se usa desde el navegador, en el **dashboard**.

## Antes de empezar

- El dashboard se abre en la dirección que te dé el equipo de sistemas (en local: `http://localhost:8501`).
- Los datos se actualizan una vez al día, de madrugada. Cada página muestra arriba a la derecha el sello **Corte de datos** con la fecha de la información; el detalle de la última carga está en *Inicio → Estado de la plataforma*.
- Los montos están en pesos mexicanos (MXN).
- Las tablas se pueden ordenar haciendo clic en el encabezado y descargar como CSV desde el menú de la propia tabla.

## Páginas

### Inicio: resumen ejecutivo
- **Franja de indicadores:** ingreso, tickets y ticket promedio de los últimos 12 meses (con su variación frente a los 12 meses previos) y clientes activos.
- **Salud del inventario:** una barra reparte los 4,800 pares sucursal-producto por estado (sin existencia, bajo mínimo, exceso, sin rotación y normal). Debajo están las alertas pendientes de cada tipo y las incidencias abiertas.
- **Red de sucursales:** un mapa con las 12 sucursales; el tamaño del punto es su ingreso de 12 meses y el anillo rojo marca las tres con más alertas pendientes. Pasa el cursor sobre un punto para ver su detalle. El mapa es esquemático: las sucursales de una misma ciudad aparecen ligeramente separadas. Debajo, una tarjeta por sucursal con su ingreso, su tendencia mensual y sus alertas por tipo.
- **Ingreso mensual y categorías:** el año en curso contra los dos anteriores y el ingreso por categoría.
- **Estado de la plataforma:** si la API, el último ETL y el modelo están al día.

### Ventas
1. Elige el **rango de fechas** (por defecto, el último año) y, si quieres, una **sucursal**.
2. **Serie diaria:** las ventas de cada día y su media móvil de 7 días (la línea suave muestra la tendencia).
3. **Ventas por sucursal:** pasa el cursor sobre una barra para ver el ticket promedio.
4. **Mezcla por categoría:** cómo se reparte el ingreso entre categorías mes con mes.
5. **Clasificación ABC:** los productos A generan el 80 % del ingreso; los B, el siguiente 15 %; los C, el resto.

### Inventario
Arriba, una barra reparte todos los pares sucursal-producto por estado, con su cantidad y porcentaje; debajo, las mismas cifras una por una.

- **Pares por estado:**
  - *sin existencia*: no hay piezas;
  - *bajo mínimo*: hay menos que el punto de reorden;
  - *normal*;
  - *exceso*: alcanza para más de 180 días;
  - *sin rotación*: hay piezas pero nada se vendió en 90 días.
- **Cobertura:** cuántos días alcanza la existencia al ritmo de venta de los últimos 90 días.
- **Tasa de desabasto mensual:** porcentaje de días en que los productos estuvieron sin existencia.

### Alertas
Las genera el modelo de pronóstico cada día:

| Alerta | Qué significa | Qué hacer |
|---|---|---|
| **RIESGO_DESABASTO** | La existencia probablemente no alcanza hasta que llegue un nuevo pedido (tiempo de entrega + 1 semana). | Revisar y adelantar el pedido al proveedor. |
| **EXCESO_INVENTARIO** | Al ritmo pronosticado, la existencia dura más de 180 días. | Frenar las compras, considerar promociones o traspasos a otras sucursales. |
| **SIN_ROTACION** | Hay piezas, no se vende nada desde hace 13 semanas y no se espera demanda. | Evaluar liquidar o descontinuar. |

Cada alerta de **riesgo de desabasto** trae dos columnas para actuar:

- **Pedir (u):** las unidades para llegar al nivel recomendado (la demanda esperada mientras llega el pedido, más un colchón para la variación). No descuenta pedidos que ya estén en camino: réstalos tú.
- **Pedir a más tardar:** el último día para pedir y recibir antes de que se agote, al ritmo de venta esperado. La lista muestra primero las más urgentes y, arriba de la tabla, el total de unidades sugeridas.

La columna **Motivo principal** dice por qué salió la alerta (por ejemplo, "Ya no hay existencia y un pedido tarda 6 días en llegar"). Si **seleccionas una o varias filas**, debajo de la tabla aparece la explicación completa de cada una, con 2 o 3 factores (temporada, tendencia, días que estuvo agotado…) y el pedido sugerido.

Para registrar que una alerta ya se atendió, selecciónala en la lista y pulsa **Marcar como atendidas**. Desaparece de los pendientes.

> En las pruebas, una de cada cuatro alertas de desabasto terminó en un faltante real, y las alertas anticiparon cerca de un tercio de los faltantes. Úsala como lista de revisión priorizada, no como orden de compra automática. Si el producto estuvo agotado en las últimas semanas, la alerta lo toma en cuenta: en ese tiempo se vendió menos de lo que los clientes pidieron.

### Pronóstico
1. Busca un producto por nombre o SKU y elige la sucursal (o todas).
2. La gráfica muestra las ventas de las últimas 52 semanas y el **pronóstico de las próximas 4**, con una banda sombreada: el intervalo donde se espera que caiga la demanda 8 de cada 10 veces.
3. Abajo están la precisión del modelo y su comparación con una media móvil simple.

### Calidad y operación
- **Hallazgos de la última carga:** cuántos registros corrigió, rechazó o marcó el proceso de calidad, por regla (por ejemplo, fechas en otro formato o clientes duplicados).
- **Últimas ejecuciones del ETL:** filas leídas, cargadas y rechazadas de cada tabla.
- **Incidencias mensuales:** reportes de desabasto, retrasos de proveedor, fallas del sistema, etc.

## Preguntas frecuentes

**¿Por qué el total de ventas no coincide exactamente con el del sistema de punto de venta?**
El proceso de calidad elimina tickets duplicados y descarta los renglones con productos inexistentes. Los detalles están en *Calidad y operación*.

**¿Por qué una sucursal tiene menos historia?**
QRO03 (abril de 2024) y MOR01 (septiembre de 2024) abrieron dentro del periodo.

**La página muestra un mensaje rojo de conexión.**
El servicio de datos (API) no está disponible. Avisa al equipo de sistemas.
