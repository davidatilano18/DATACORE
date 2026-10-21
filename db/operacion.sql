-- DATACORE · Tablas de operación (respaldos y monitoreo).
-- Idempotente: db_setup lo aplica en cada ejecución sin tocar datos existentes.

CREATE TABLE IF NOT EXISTS ops.respaldos (
    id_respaldo     BIGSERIAL PRIMARY KEY,
    inicio          TIMESTAMP    NOT NULL DEFAULT now(),
    fin             TIMESTAMP,
    archivo         VARCHAR(255) NOT NULL,
    tamano_bytes    BIGINT,
    estatus         VARCHAR(10)  NOT NULL CHECK (estatus IN ('exitoso', 'fallido')),
    verificado      BOOLEAN      NOT NULL DEFAULT FALSE,  -- se restauró en una base de prueba y cuadró
    detalle         TEXT
);

CREATE TABLE IF NOT EXISTS ops.monitoreo (
    id_chequeo   BIGSERIAL PRIMARY KEY,
    revisado_en  TIMESTAMP   NOT NULL DEFAULT now(),
    componente   VARCHAR(30) NOT NULL,      -- base_de_datos, api, dashboard, disco, etl, respaldo, modelo
    estado       VARCHAR(10) NOT NULL CHECK (estado IN ('ok', 'alerta', 'falla')),
    latencia_ms  NUMERIC(10,1),
    detalle      TEXT
);
CREATE INDEX IF NOT EXISTS ix_monitoreo_componente ON ops.monitoreo (componente, revisado_en DESC);

CREATE TABLE IF NOT EXISTS ops.corridas (
    id_corrida  BIGSERIAL PRIMARY KEY,
    proceso     VARCHAR(30) NOT NULL,       -- diario
    inicio      TIMESTAMP   NOT NULL DEFAULT now(),
    fin         TIMESTAMP,
    estatus     VARCHAR(10) NOT NULL CHECK (estatus IN ('en_curso', 'exitosa', 'fallida')),
    pasos       JSONB       NOT NULL DEFAULT '[]'::jsonb,  -- [{paso, estatus, segundos, detalle}]
    mensaje_error TEXT
);


-- Detección diaria de ventas (RF-13); publicación reemplazada en una transacción.
CREATE TABLE IF NOT EXISTS ops.anomalias (
    id BIGSERIAL PRIMARY KEY,
    fecha DATE NOT NULL,
    id_sucursal INTEGER NOT NULL,
    metrica VARCHAR(10) NOT NULL CHECK (metrica IN ('ingreso', 'tickets')),
    tipo VARCHAR(5) NOT NULL CHECK (tipo IN ('caida', 'pico')),
    valor NUMERIC(18,2) NOT NULL,
    esperado NUMERIC(18,2) NOT NULL,
    z DOUBLE PRECISION NOT NULL,
    detectada_en TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (fecha, id_sucursal, metrica)
);

-- Migración: quita las llaves foráneas de ops hacia core en bases creadas antes de este cambio
-- (el TRUNCATE ... CASCADE del ETL vaciaba pronósticos, alertas atendidas y anomalías).
-- Sin el carácter de porcentaje: psycopg lo interpretaría como marcador de parámetro.
DO $$
DECLARE r record;
BEGIN
    FOR r IN SELECT conrelid::regclass::text AS tabla, conname
             FROM pg_constraint
             WHERE contype = 'f' AND connamespace = 'ops'::regnamespace
               AND starts_with(confrelid::regclass::text, 'core.')
    LOOP
        EXECUTE 'ALTER TABLE ' || r.tabla || ' DROP CONSTRAINT ' || quote_ident(r.conname);
    END LOOP;
END $$;
