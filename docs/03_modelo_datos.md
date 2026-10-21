# 03 · Modelo entidad-relación y diccionario de datos

El DDL de tablas está en [`db/schema.sql`](../db/schema.sql) y el de indicadores en
[`db/vistas.sql`](../db/vistas.sql). Los esquemas de origen son:

- **`core`**: datos de negocio ya validados.
- **`ops`**: operación de la plataforma (ETL, calidad, modelos, predicciones, alertas).

## Diagrama entidad-relación (`core`)

```mermaid
erDiagram
    SUCURSALES ||--o{ VENTAS : registra
    SUCURSALES ||--o{ INVENTARIO : mantiene
    SUCURSALES ||--o{ MOVIMIENTOS_INVENTARIO : ocurre_en
    SUCURSALES ||--o{ INCIDENCIAS : reporta
    SUCURSALES ||--o{ CLIENTES : "es preferida por"
    CLIENTES |o--o{ VENTAS : realiza
    VENTAS ||--|{ DETALLE_VENTA : contiene
    PRODUCTOS ||--o{ DETALLE_VENTA : "se vende en"
    PRODUCTOS ||--o{ INVENTARIO : "se almacena en"
    PRODUCTOS ||--o{ MOVIMIENTOS_INVENTARIO : afecta
    PRODUCTOS |o--o{ INCIDENCIAS : involucra
    CATEGORIAS ||--o{ PRODUCTOS : agrupa
    PROVEEDORES ||--o{ PRODUCTOS : surte

    SUCURSALES { smallint id_sucursal PK  varchar codigo UK  varchar region  varchar tamano  date fecha_apertura }
    CATEGORIAS { smallint id_categoria PK  varchar nombre UK }
    PROVEEDORES { int id_proveedor PK  varchar rfc UK  smallint dias_entrega }
    PRODUCTOS { int id_producto PK  varchar sku UK  smallint id_categoria FK  int id_proveedor FK  numeric precio_unitario  numeric costo_unitario }
    CLIENTES { int id_cliente PK  varchar tipo_cliente  date fecha_registro  smallint id_sucursal_preferida FK }
    VENTAS { bigint id_venta PK  varchar folio UK  timestamp fecha_hora  smallint id_sucursal FK  int id_cliente FK  numeric total }
    DETALLE_VENTA { bigint id_detalle PK  bigint id_venta FK  int id_producto FK  int cantidad  numeric subtotal }
    INVENTARIO { smallint id_sucursal PK  int id_producto PK  int existencia  int stock_minimo  int stock_maximo }
    MOVIMIENTOS_INVENTARIO { bigint id_movimiento PK  date fecha  varchar tipo  int cantidad  int existencia_resultante }
    INCIDENCIAS { int id_incidencia PK  date fecha_reporte  varchar tipo  varchar severidad  varchar estatus }
```

## Diagrama entidad-relación (`ops`)

```mermaid
erDiagram
    ETL_EJECUCIONES ||--o{ CALIDAD_HALLAZGOS : produce
    MODELOS ||--o{ PREDICCIONES_DEMANDA : genera
    PREDICCIONES_DEMANDA }o--|| SUCURSALES : para
    PREDICCIONES_DEMANDA }o--|| PRODUCTOS : de
    ALERTAS_INVENTARIO }o--|| SUCURSALES : en
    ALERTAS_INVENTARIO }o--|| PRODUCTOS : sobre
```

## Diccionario de datos

Convenciones: las llaves primarias se llaman `id_<entidad>`, los nombres van en español sin acentos y en `snake_case`, los montos en pesos mexicanos (MXN) con `NUMERIC(…,2)`, y las fechas sin zona horaria (hora local del Centro de México).

### core.sucursales (12 filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_sucursal | SMALLINT | No | Llave primaria. |
| codigo | VARCHAR(10) | No | Código de negocio único (`QRO01`, `CDMX02`…). Es el que usan los archivos crudos. |
| nombre | VARCHAR(80) | No | Nombre comercial. |
| ciudad, estado | VARCHAR | No | Ubicación. |
| region | VARCHAR(20) | No | Bajío, Centro, Occidente o Norte. |
| tamano | VARCHAR(10) | No | `grande`, `mediana` o `pequena`; determina la afluencia. |
| fecha_apertura | DATE | No | Dos sucursales abren dentro del periodo (QRO03 en abril de 2024 y MOR01 en septiembre de 2024). |

### core.categorias (10 filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_categoria | SMALLINT | No | Llave primaria. |
| nombre | VARCHAR(40) | No | Abarrotes, Bebidas, Limpieza, Cuidado personal, Electrónica, Papelería, Juguetes, Hogar, Mascotas, Dulcería y botanas. |

### core.proveedores (35 filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_proveedor | INTEGER | No | Llave primaria. |
| nombre | VARCHAR(120) | No | Razón social. |
| rfc | VARCHAR(13) | No | RFC de persona moral (ficticio). |
| ciudad, estado, telefono, email | VARCHAR | Sí | Contacto. |
| dias_entrega | SMALLINT | No | Tiempo de entrega comprometido, de 2 a 10 días. |
| activo | BOOLEAN | No | Proveedor vigente. |

### core.productos (400 filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_producto | INTEGER | No | Llave primaria. |
| sku | VARCHAR(20) | No | Código único `NX-<CAT>-<nnnnn>`. Es el que usan los archivos crudos. |
| nombre | VARCHAR(120) | No | Artículo + marca ficticia + presentación. |
| id_categoria | SMALLINT | No | FK a categorías. En el Excel crudo viene el **nombre** de la categoría. |
| id_proveedor | INTEGER | No | FK a proveedores. |
| precio_unitario | NUMERIC(10,2) | No | Precio de lista vigente (2025). Los precios históricos están en `detalle_venta`. |
| costo_unitario | NUMERIC(10,2) | No | Costo de adquisición; debe ser menor que el precio. |
| unidad | VARCHAR(10) | No | Unidad de venta (`pieza`). |
| fecha_alta | DATE | No | Inicio de comercialización. Unos 8 % de los productos se lanzan dentro del periodo. |
| activo | BOOLEAN | No | `false` si se descontinuó (unos 5 %). |

### core.clientes (8,000 filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_cliente | INTEGER | No | Llave primaria. |
| nombre, apellido_paterno, apellido_materno | VARCHAR | No / No / Sí | Nombre completo (ficticio). |
| email | VARCHAR(120) | Sí | Correo electrónico. |
| telefono | VARCHAR(15) | Sí | 10 dígitos con lada de su ciudad. |
| ciudad, estado | VARCHAR | Sí | Domicilio (el de su sucursal preferida). |
| tipo_cliente | VARCHAR(10) | No | `minorista` (90 %) o `mayorista` (10 %; compra más renglones y volumen). |
| fecha_registro | DATE | No | Alta en el CRM; siempre anterior a su primera compra. |
| id_sucursal_preferida | SMALLINT | Sí | FK a sucursales; hace ahí alrededor del 90 % de sus compras. |

### core.ventas (unas 181 mil filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_venta | BIGINT | No | Llave primaria. |
| folio | VARCHAR(20) | No | `<codigo_sucursal>-<consecutivo>`, único. |
| fecha_hora | TIMESTAMP | No | Momento del ticket (de 9:00 a 21:00). |
| id_sucursal | SMALLINT | No | FK a sucursales. |
| id_cliente | INTEGER | Sí | FK a clientes; `NULL` = venta a público general (unos 30 %). |
| metodo_pago | VARCHAR(20) | Sí | `efectivo`, `tarjeta_debito`, `tarjeta_credito` o `transferencia`. |
| total | NUMERIC(12,2) | No | Suma de los `subtotal` del detalle. |
| estatus | VARCHAR(12) | No | `completada` o `cancelada` (alrededor del 1 %; no descuenta inventario). |

### core.detalle_venta (unas 641 mil filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_detalle | BIGINT | No | Llave primaria. |
| id_venta | BIGINT | No | FK a ventas. Un producto aparece una sola vez por ticket. |
| id_producto | INTEGER | No | FK a productos. En el CSV crudo viene el **SKU**. |
| cantidad | INTEGER | No | Unidades, mayor que 0. |
| precio_unitario | NUMERIC(10,2) | No | Precio de lista del año de la venta (se actualiza cada enero, con inflación de alrededor del 5 %). |
| descuento_pct | NUMERIC(4,3) | No | 0.05 para mayoristas; de 0.10 a 0.25 en Buen Fin para Electrónica, Juguetes y Hogar. |
| subtotal | NUMERIC(12,2) | No | `cantidad × precio_unitario × (1 − descuento_pct)`. |

### core.inventario (4,800 filas)

Foto de la existencia al cierre del periodo, por sucursal y producto.

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_sucursal, id_producto | — | No | Llave primaria compuesta. |
| existencia | INTEGER | No | Unidades disponibles (≥ 0). |
| stock_minimo | INTEGER | No | Punto de reorden vigente. |
| stock_maximo | INTEGER | No | Nivel objetivo al resurtir. |
| fecha_actualizacion | DATE | No | Fecha de la foto. |

### core.movimientos_inventario (unas 648 mil filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_movimiento | BIGINT | No | Llave primaria; respeta el orden cronológico. |
| fecha | DATE | No | Día del movimiento. |
| id_sucursal, id_producto | — | No | FK. En el CSV crudo vienen el código de sucursal y el SKU. |
| tipo | VARCHAR(20) | No | `INVENTARIO_INICIAL`, `ENTRADA_COMPRA`, `SALIDA_VENTA` (consolidado diario), `MERMA` o `AJUSTE_CONTEO`. |
| cantidad | INTEGER | No | Con signo: **+ entra, − sale**. |
| existencia_resultante | INTEGER | No | Existencia después del movimiento. La suma acumulada de `cantidad` debe dar este valor. |
| referencia | VARCHAR(20) | Sí | Orden de compra (`OC-…`) en las entradas. |

### core.incidencias (unas 6,700 filas)

| Columna | Tipo | Nulo | Descripción |
|---|---|---|---|
| id_incidencia | INTEGER | No | Llave primaria. |
| fecha_reporte | DATE | No | Fecha de reporte. |
| id_sucursal | SMALLINT | No | FK. |
| id_producto | INTEGER | Sí | FK cuando aplica (desabasto, retraso, merma, diferencia). |
| tipo | VARCHAR(25) | No | `FALLA_SISTEMA`, `DESABASTO`, `RETRASO_PROVEEDOR`, `MERCANCIA_DANADA`, `DIFERENCIA_INVENTARIO` o `QUEJA_CLIENTE`. |
| severidad | VARCHAR(5) | No | `baja`, `media` o `alta`. |
| descripcion | VARCHAR(250) | No | Texto libre. |
| estatus | VARCHAR(12) | No | `abierta`, `en_proceso` o `resuelta`. |
| fecha_resolucion | DATE | Sí | Solo si está resuelta. |

### Esquema ops

| Tabla | Propósito |
|---|---|
| `etl_ejecuciones` | Una fila por proceso ETL ejecutado: archivo, duración, filas leídas, cargadas y rechazadas, error. |
| `calidad_hallazgos` | Una fila por registro afectado por una regla de calidad: regla, severidad, acción (`corregido`, `rechazado`, `marcado`), valores antes y después. |
| `modelos` | Versiones de modelos entrenados con sus métricas (`JSONB`) y la marca de cuál está activo. |
| `predicciones_demanda` | Pronóstico semanal por sucursal y producto, con intervalo. |
| `alertas_inventario` | Alertas `RIESGO_DESABASTO`, `EXCESO_INVENTARIO` y `SIN_ROTACION`, con su cobertura en días. |

## Indicadores (esquema kpi)

Se aplican con `python -m datacore.db_setup`, sin `--reset`. El lector tiene
USAGE del esquema y SELECT sobre vistas actuales y futuras creadas por el rol app.
Las ventas se filtran a `completada`; el ingreso diario usa la cabecera, mientras
que categoría, producto y ABC usan subtotales del detalle para evitar duplicaciones.

| Vista | Qué mide | Columnas clave |
|---|---|---|
| `ventas_diarias_sucursal` | Tickets, unidades, ingreso y ticket promedio diario por sucursal. | `fecha`, `id_sucursal`, `codigo`, `tickets`, `unidades`, `ingreso`, `ticket_promedio` |
| `ventas_mensuales_categoria` | Ingreso y unidades por categoría; participación porcentual dentro del mes. | `mes`, `id_categoria`, `categoria`, `unidades`, `ingreso`, `participacion_pct` |
| `ventas_semanales_producto` (materializada) | Demanda semanal, únicamente combinaciones con ventas; semana inicia en lunes. | `semana_inicio`, `id_sucursal`, `id_producto`, `unidades`, `ingreso`, `tickets` |
| `abc_productos` | Pareto histórico por ingreso, incluidos productos sin ventas. | `id_producto`, `sku`, `nombre`, `categoria`, `ingreso`, `pct_acumulado`, `clase` |
| `cobertura_inventario` | Existencia actual frente a la demanda de los últimos 90 días. | `id_sucursal`, `id_producto`, `existencia`, `stock_minimo`, `stock_maximo`, `unidades_90d`, `venta_diaria_90d`, `cobertura_dias`, `estado` |
| `desabasto_mensual` (materializada) | Días-par sin existencia al cierre / días-par activos del mes. | `mes`, `id_sucursal`, `pares_activos`, `dias_par_sin_existencia`, `tasa_desabasto` |
| `incidencias_mensuales` | Reportes por tipo y severidad; pendientes y duración media de los resueltos. | `mes`, `id_sucursal`, `tipo`, `severidad`, `total`, `abiertas`, `dias_promedio_resolucion` |
| `calidad_ultima_carga` | Hallazgos por regla y acción de todos los procesos con el último `inicio`. | `regla`, `accion`, `conteo` |
| `resumen_ejecutivo` | Una fila con ventas históricas y recientes, crecimiento, clientes, inventario e incidencias pendientes. | `ingreso_total`, `ingreso_ultimos_12_meses`, `crecimiento_pct`, `tickets`, `ticket_promedio`, `clientes_activos_12_meses`, `pares_sin_existencia`, `pares_exceso`, `pares_sin_rotacion`, `incidencias_abiertas` |

ABC ordena por ingreso descendente y desempata por `id_producto`. A corresponde al
acumulado incluido el producto ≤80 %, B ≤95 % y C al resto (también ingresos cero).
El producto que cruza un umbral pasa a la clase inferior; esto difiere del EDA actual,
que usa el acumulado previo y lo conserva en la clase anterior.

La cobertura usa 90 fechas inclusivas hasta la fecha máxima de `core.ventas`,
divide las unidades entre 90 y devuelve NULL si no hubo venta. Prevalecen, en orden:
`sin_existencia`, `sin_rotacion` (existencia positiva sin ventas), `exceso`
(cobertura >180 días), `bajo_minimo` y `normal`.

Desabasto toma el último `id_movimiento` de cada día y arrastra su
`existencia_resultante` con `generate_series` hasta el siguiente cierre. Un par
es activo desde su primer `INVENTARIO_INICIAL`, inclusive, hasta la fecha máxima
entre movimientos, ventas y foto de inventario. `pares_activos` cuenta productos
distintos activos al menos un día del mes; la tasa usa los días-par reales,
incluidos meses parciales. Se materializa por el costo de expandir la historia diaria.

Las ventanas ejecutivas se anclan al día posterior a la última venta: últimos
12 meses y los 12 meses anteriores, sin solapamiento. Crecimiento es NULL si el
ingreso anterior es cero; clientes activos excluye público general. Incidencias
abiertas incluye `abierta` y `en_proceso`; la duración media solo incluye resueltas.

Las dos materializadas tienen índices únicos por sus dimensiones. Para actualizarlas:
`python -m datacore.db_setup --refrescar` (imprime segundos por vista). El ETL
llama a `refrescar_vistas(engine)` después de confirmar la carga; el refresco es
atómico entre las materializadas y un fallo se propaga sin deshacer los datos ya
confirmados. Las vistas ordinarias se evalúan al consultarlas; ABC lee el agregado
semanal y refleja su último refresco.
