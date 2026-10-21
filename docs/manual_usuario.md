# Manual de usuario de DATACORE

Para quien consulta la información de NexaTech Solutions (empresa ficticia): dirección, compras, almacén y sucursales.
Se usa desde el navegador, en el **dashboard**.

## Antes de empezar

- El dashboard se abre en la dirección que te dé el equipo de sistemas (en local: `http://localhost:8501`).
- Los datos se actualizan una vez al día, de madrugada. La fecha de la última actualización aparece en *Inicio → Estado de la plataforma*.
- Los montos están en pesos mexicanos (MXN).
- Las tablas se pueden ordenar haciendo clic en el encabezado y descargar como CSV desde el menú de la propia tabla.

## Páginas

### Inicio: resumen ejecutivo
Tarjetas con los indicadores principales: ingreso total y de los últimos 12 meses (con su crecimiento frente a los 12 meses previos), tickets, ticket promedio, clientes activos, cuántas combinaciones de sucursal y producto están sin existencia, en exceso o sin rotación, e incidencias abiertas. Debajo están la tendencia de ventas mensuales y el estado de la plataforma.

### Ventas
1. Elige el **rango de fechas** (por defecto, el último año) y, si quieres, una **sucursal**.
2. **Serie diaria:** las ventas de cada día y su media móvil de 7 días (la línea suave muestra la tendencia).
3. **Ventas por sucursal:** pasa el cursor sobre una barra para ver el ticket promedio.
4. **Mezcla por categoría:** cómo se reparte el ingreso entre categorías mes con mes.
5. **Clasificación ABC:** los productos A generan el 80 % del ingreso; los B, el siguiente 15 %; los C, el resto.

### Inventario
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

Para registrar que una alerta ya se atendió, selecciónala en la lista y pulsa **Marcar como atendida**. Desaparece de los pendientes.

> La alerta de desabasto es conservadora a propósito: en las pruebas anticipó alrededor de la mitad de los faltantes reales, a cambio de varias alertas que al final no terminaron en faltante. Úsala como lista de revisión, no como orden de compra automática.

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
