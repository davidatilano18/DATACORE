-- DATACORE · Esquema de base de datos (PostgreSQL 16+)
-- core: datos de negocio ya limpios y validados por el ETL.
-- ops:  datos operativos de la propia plataforma (ejecuciones ETL, calidad,
--       predicciones y alertas).

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS ops;
-- Indicadores derivados y materializados: se aplican después desde db/vistas.sql.
CREATE SCHEMA IF NOT EXISTS kpi;

-- =========================================================================
-- core: catálogos
-- =========================================================================

CREATE TABLE core.sucursales (
    id_sucursal     SMALLINT PRIMARY KEY,
    codigo          VARCHAR(10)  NOT NULL UNIQUE,
    nombre          VARCHAR(80)  NOT NULL,
    ciudad          VARCHAR(80)  NOT NULL,
    estado          VARCHAR(40)  NOT NULL,
    region          VARCHAR(20)  NOT NULL,
    tamano          VARCHAR(10)  NOT NULL CHECK (tamano IN ('grande', 'mediana', 'pequena')),
    fecha_apertura  DATE         NOT NULL
);

CREATE TABLE core.categorias (
    id_categoria    SMALLINT PRIMARY KEY,
    nombre          VARCHAR(40) NOT NULL UNIQUE
);

CREATE TABLE core.proveedores (
    id_proveedor    INTEGER PRIMARY KEY,
    nombre          VARCHAR(120) NOT NULL,
    rfc             VARCHAR(13)  NOT NULL UNIQUE,
    ciudad          VARCHAR(80),
    estado          VARCHAR(40),
    telefono        VARCHAR(15),
    email           VARCHAR(120),
    dias_entrega    SMALLINT     NOT NULL CHECK (dias_entrega > 0),
    activo          BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE core.productos (
    id_producto     INTEGER PRIMARY KEY,
    sku             VARCHAR(20)   NOT NULL UNIQUE,
    nombre          VARCHAR(120)  NOT NULL,
    id_categoria    SMALLINT      NOT NULL REFERENCES core.categorias,
    id_proveedor    INTEGER       NOT NULL REFERENCES core.proveedores,
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario > 0),
    costo_unitario  NUMERIC(10,2) NOT NULL CHECK (costo_unitario > 0),
    unidad          VARCHAR(10)   NOT NULL DEFAULT 'pieza',
    fecha_alta      DATE          NOT NULL,
    activo          BOOLEAN       NOT NULL DEFAULT TRUE,
    CONSTRAINT costo_menor_a_precio CHECK (costo_unitario < precio_unitario)
);

CREATE TABLE core.clientes (
    id_cliente            INTEGER PRIMARY KEY,
    nombre                VARCHAR(80)  NOT NULL,
    apellido_paterno      VARCHAR(60)  NOT NULL,
    apellido_materno      VARCHAR(60),
    email                 VARCHAR(120),
    telefono              VARCHAR(15),
    ciudad                VARCHAR(80),
    estado                VARCHAR(40),
    tipo_cliente          VARCHAR(10)  NOT NULL CHECK (tipo_cliente IN ('minorista', 'mayorista')),
    fecha_registro        DATE         NOT NULL,
    id_sucursal_preferida SMALLINT     REFERENCES core.sucursales
);

-- =========================================================================
-- core: transacciones
-- =========================================================================

CREATE TABLE core.ventas (
    id_venta     BIGINT PRIMARY KEY,
    folio        VARCHAR(20)   NOT NULL UNIQUE,
    fecha_hora   TIMESTAMP     NOT NULL,
    id_sucursal  SMALLINT      NOT NULL REFERENCES core.sucursales,
    id_cliente   INTEGER       REFERENCES core.clientes,  -- NULL = público general
    metodo_pago  VARCHAR(20)   CHECK (metodo_pago IN ('efectivo', 'tarjeta_debito', 'tarjeta_credito', 'transferencia')),
    total        NUMERIC(12,2) NOT NULL CHECK (total >= 0),
    estatus      VARCHAR(12)   NOT NULL CHECK (estatus IN ('completada', 'cancelada'))
);
CREATE INDEX ix_ventas_fecha ON core.ventas (fecha_hora);
CREATE INDEX ix_ventas_sucursal_fecha ON core.ventas (id_sucursal, fecha_hora);
CREATE INDEX ix_ventas_cliente ON core.ventas (id_cliente);

CREATE TABLE core.detalle_venta (
    id_detalle      BIGINT PRIMARY KEY,
    id_venta        BIGINT        NOT NULL REFERENCES core.ventas ON DELETE CASCADE,
    id_producto     INTEGER       NOT NULL REFERENCES core.productos,
    cantidad        INTEGER       NOT NULL CHECK (cantidad > 0),
    precio_unitario NUMERIC(10,2) NOT NULL CHECK (precio_unitario > 0),
    descuento_pct   NUMERIC(4,3)  NOT NULL DEFAULT 0 CHECK (descuento_pct BETWEEN 0 AND 0.9),
    subtotal        NUMERIC(12,2) NOT NULL,
    UNIQUE (id_venta, id_producto)
);
CREATE INDEX ix_detalle_producto ON core.detalle_venta (id_producto);

CREATE TABLE core.inventario (
    id_sucursal         SMALLINT NOT NULL REFERENCES core.sucursales,
    id_producto         INTEGER  NOT NULL REFERENCES core.productos,
    existencia          INTEGER  NOT NULL CHECK (existencia >= 0),
    stock_minimo        INTEGER  NOT NULL CHECK (stock_minimo >= 0),
    stock_maximo        INTEGER  NOT NULL,
    fecha_actualizacion DATE     NOT NULL,
    PRIMARY KEY (id_sucursal, id_producto),
    CHECK (stock_maximo >= stock_minimo)
);

CREATE TABLE core.movimientos_inventario (
    id_movimiento         BIGINT PRIMARY KEY,
    fecha                 DATE        NOT NULL,
    id_sucursal           SMALLINT    NOT NULL REFERENCES core.sucursales,
    id_producto           INTEGER     NOT NULL REFERENCES core.productos,
    tipo                  VARCHAR(20) NOT NULL CHECK (tipo IN
                          ('INVENTARIO_INICIAL', 'ENTRADA_COMPRA', 'SALIDA_VENTA', 'MERMA', 'AJUSTE_CONTEO')),
    cantidad              INTEGER     NOT NULL CHECK (cantidad <> 0),  -- + entra, - sale
    existencia_resultante INTEGER     NOT NULL CHECK (existencia_resultante >= 0),
    referencia            VARCHAR(20)                                   -- p. ej. OC-0000123
);
CREATE INDEX ix_mov_sucursal_producto_fecha ON core.movimientos_inventario (id_sucursal, id_producto, fecha);

CREATE TABLE core.incidencias (
    id_incidencia    INTEGER PRIMARY KEY,
    fecha_reporte    DATE         NOT NULL,
    id_sucursal      SMALLINT     NOT NULL REFERENCES core.sucursales,
    id_producto      INTEGER      REFERENCES core.productos,
    tipo             VARCHAR(25)  NOT NULL CHECK (tipo IN ('FALLA_SISTEMA', 'DESABASTO', 'RETRASO_PROVEEDOR',
                                  'MERCANCIA_DANADA', 'DIFERENCIA_INVENTARIO', 'QUEJA_CLIENTE')),
    severidad        VARCHAR(5)   NOT NULL CHECK (severidad IN ('baja', 'media', 'alta')),
    descripcion      VARCHAR(250) NOT NULL,
    estatus          VARCHAR(12)  NOT NULL CHECK (estatus IN ('abierta', 'en_proceso', 'resuelta')),
    fecha_resolucion DATE,
    CHECK (fecha_resolucion IS NULL OR fecha_resolucion >= fecha_reporte),
    CHECK ((estatus = 'resuelta') = (fecha_resolucion IS NOT NULL))
);

-- =========================================================================
-- ops: operación de la plataforma
-- =========================================================================

CREATE TABLE ops.etl_ejecuciones (
    id_ejecucion       BIGSERIAL PRIMARY KEY,
    proceso            VARCHAR(60) NOT NULL,          -- p. ej. carga_ventas
    archivo_origen     VARCHAR(255),
    inicio             TIMESTAMP   NOT NULL DEFAULT now(),
    fin                TIMESTAMP,
    estatus            VARCHAR(10) NOT NULL CHECK (estatus IN ('en_curso', 'exitosa', 'fallida')),
    filas_leidas       INTEGER,
    filas_cargadas     INTEGER,
    filas_rechazadas   INTEGER,
    mensaje_error      TEXT
);

CREATE TABLE ops.calidad_hallazgos (
    id_hallazgo   BIGSERIAL PRIMARY KEY,
    id_ejecucion  BIGINT      NOT NULL REFERENCES ops.etl_ejecuciones,
    tabla         VARCHAR(40) NOT NULL,
    clave         VARCHAR(40) NOT NULL,              -- llave del registro afectado
    regla         VARCHAR(60) NOT NULL,              -- p. ej. cantidad_negativa
    severidad     VARCHAR(12) NOT NULL CHECK (severidad IN ('advertencia', 'error')),
    accion        VARCHAR(12) NOT NULL CHECK (accion IN ('corregido', 'rechazado', 'marcado')),
    valor_original TEXT,
    valor_final    TEXT,
    detectado_en  TIMESTAMP   NOT NULL DEFAULT now()
);
CREATE INDEX ix_hallazgos_regla ON ops.calidad_hallazgos (regla);

CREATE TABLE ops.modelos (
    id_modelo        SERIAL PRIMARY KEY,
    nombre           VARCHAR(60) NOT NULL,
    version          VARCHAR(20) NOT NULL,
    algoritmo        VARCHAR(60) NOT NULL,
    entrenado_en     TIMESTAMP   NOT NULL DEFAULT now(),
    fecha_corte_datos DATE       NOT NULL,
    metricas         JSONB       NOT NULL,           -- MAE, RMSE, WAPE, etc.
    activo           BOOLEAN     NOT NULL DEFAULT FALSE,
    UNIQUE (nombre, version)
);

CREATE TABLE ops.predicciones_demanda (
    id_modelo      INTEGER       NOT NULL REFERENCES ops.modelos,
    id_sucursal    SMALLINT      NOT NULL REFERENCES core.sucursales,
    id_producto    INTEGER       NOT NULL REFERENCES core.productos,
    semana_inicio  DATE          NOT NULL,           -- lunes de la semana pronosticada
    demanda_estimada NUMERIC(10,2) NOT NULL,
    limite_inferior  NUMERIC(10,2),
    limite_superior  NUMERIC(10,2),
    generado_en    TIMESTAMP     NOT NULL DEFAULT now(),
    PRIMARY KEY (id_modelo, id_sucursal, id_producto, semana_inicio)
);

CREATE TABLE ops.alertas_inventario (
    id_alerta      BIGSERIAL PRIMARY KEY,
    id_sucursal    SMALLINT    NOT NULL REFERENCES core.sucursales,
    id_producto    INTEGER     NOT NULL REFERENCES core.productos,
    tipo           VARCHAR(20) NOT NULL CHECK (tipo IN ('RIESGO_DESABASTO', 'EXCESO_INVENTARIO', 'SIN_ROTACION')),
    existencia     INTEGER     NOT NULL,
    demanda_estimada NUMERIC(10,2),
    dias_cobertura NUMERIC(8,1),
    generada_en    TIMESTAMP   NOT NULL DEFAULT now(),
    atendida       BOOLEAN     NOT NULL DEFAULT FALSE
);
CREATE INDEX ix_alertas_pendientes ON ops.alertas_inventario (atendida, tipo);
