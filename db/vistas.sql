-- Indicadores sobre ventas completadas; importes en MXN.
CREATE SCHEMA IF NOT EXISTS kpi;

-- Tickets e ingreso de cabecera sin multiplicarlos por sus renglones.
CREATE OR REPLACE VIEW kpi.ventas_diarias_sucursal AS
WITH unidades AS (
    SELECT id_venta, sum(cantidad) AS unidades FROM core.detalle_venta GROUP BY id_venta
)
SELECT v.fecha_hora::date AS fecha, v.id_sucursal, s.codigo,
       count(*) AS tickets, sum(coalesce(u.unidades, 0)) AS unidades,
       sum(v.total) AS ingreso, round(avg(v.total), 2) AS ticket_promedio
FROM core.ventas v JOIN core.sucursales s USING (id_sucursal)
LEFT JOIN unidades u USING (id_venta)
WHERE v.estatus = 'completada'
GROUP BY 1, 2, 3;

-- Mezcla mensual de categorías, medida por ingreso del detalle.
CREATE OR REPLACE VIEW kpi.ventas_mensuales_categoria AS
SELECT date_trunc('month', v.fecha_hora)::date AS mes, p.id_categoria,
       c.nombre AS categoria, sum(d.cantidad) AS unidades, sum(d.subtotal) AS ingreso,
       100 * sum(d.subtotal) / nullif(sum(sum(d.subtotal)) OVER
           (PARTITION BY date_trunc('month', v.fecha_hora)::date), 0) AS participacion_pct
FROM core.ventas v JOIN core.detalle_venta d USING (id_venta)
JOIN core.productos p USING (id_producto) JOIN core.categorias c USING (id_categoria)
WHERE v.estatus = 'completada'
GROUP BY 1, 2, 3;

-- Agregado reutilizable para pronóstico; materializado para evitar reagrupar todo el detalle.
CREATE MATERIALIZED VIEW IF NOT EXISTS kpi.ventas_semanales_producto AS
SELECT date_trunc('week', v.fecha_hora)::date AS semana_inicio,
       v.id_sucursal, d.id_producto, sum(d.cantidad) AS unidades,
       sum(d.subtotal) AS ingreso, count(DISTINCT v.id_venta) AS tickets
FROM core.ventas v JOIN core.detalle_venta d USING (id_venta)
WHERE v.estatus = 'completada'
GROUP BY 1, 2, 3;
CREATE UNIQUE INDEX IF NOT EXISTS ix_kpi_ventas_semanales
    ON kpi.ventas_semanales_producto (semana_inicio, id_sucursal, id_producto);

-- Pareto por ingreso: el producto que supera 80/95 pasa a la clase inferior.
-- Se usa el acumulado incluido el producto, a diferencia del acumulado previo del EDA.
CREATE OR REPLACE VIEW kpi.abc_productos AS
WITH ingresos AS (
    SELECT p.id_producto, p.sku, p.nombre, c.nombre AS categoria,
           coalesce(sum(s.ingreso), 0) AS ingreso
    FROM core.productos p JOIN core.categorias c USING (id_categoria)
    LEFT JOIN kpi.ventas_semanales_producto s USING (id_producto)
    GROUP BY p.id_producto, p.sku, p.nombre, c.nombre
), acumulados AS (
    SELECT *, coalesce(100 * sum(ingreso) OVER (ORDER BY ingreso DESC, id_producto
        ROWS UNBOUNDED PRECEDING) / nullif(sum(ingreso) OVER (), 0), 0) AS pct_acumulado
    FROM ingresos
)
SELECT *, CASE WHEN ingreso = 0 THEN 'C' WHEN pct_acumulado <= 80 THEN 'A'
               WHEN pct_acumulado <= 95 THEN 'B' ELSE 'C' END AS clase
FROM acumulados;

-- Cobertura de la foto actual usando 90 fechas inclusivas hasta la última venta.
-- Precedencia: cero, sin rotación, exceso (>180 días), bajo mínimo, normal.
CREATE OR REPLACE VIEW kpi.cobertura_inventario AS
WITH corte AS (SELECT max(fecha_hora::date) AS fecha FROM core.ventas), demanda AS (
    SELECT v.id_sucursal, d.id_producto, sum(d.cantidad) AS unidades
    FROM core.ventas v JOIN core.detalle_venta d USING (id_venta) CROSS JOIN corte c
    WHERE v.estatus = 'completada' AND v.fecha_hora::date BETWEEN c.fecha - 89 AND c.fecha
    GROUP BY 1, 2
), cobertura AS (
    SELECT i.*, coalesce(d.unidades, 0) AS unidades_90d,
           coalesce(d.unidades, 0) / 90.0 AS venta_diaria_90d,
           i.existencia * 90.0 / nullif(d.unidades, 0) AS cobertura_dias
    FROM core.inventario i LEFT JOIN demanda d USING (id_sucursal, id_producto)
)
SELECT id_sucursal, id_producto, existencia, stock_minimo, stock_maximo,
       unidades_90d, venta_diaria_90d, cobertura_dias,
       CASE WHEN existencia = 0 THEN 'sin_existencia'
            WHEN unidades_90d = 0 THEN 'sin_rotacion'
            WHEN cobertura_dias > 180 THEN 'exceso'
            WHEN existencia < stock_minimo THEN 'bajo_minimo'
            ELSE 'normal' END AS estado
FROM cobertura;

-- Reconstrucción diaria costosa: último movimiento por id del día y arrastre
-- mediante intervalos hasta el siguiente cierre. Solo pares con inventario inicial.
-- El denominador son días-par activos, incluso en meses parciales.
CREATE MATERIALIZED VIEW IF NOT EXISTS kpi.desabasto_mensual AS
WITH corte AS (
    SELECT greatest((SELECT max(fecha) FROM core.movimientos_inventario),
                    (SELECT max(fecha_hora::date) FROM core.ventas),
                    (SELECT max(fecha_actualizacion) FROM core.inventario)) AS fecha
), activos AS (
    SELECT id_sucursal, id_producto, min(fecha) AS inicio
    FROM core.movimientos_inventario WHERE tipo = 'INVENTARIO_INICIAL' GROUP BY 1, 2
), cierres AS (
    SELECT DISTINCT ON (m.id_sucursal, m.id_producto, m.fecha)
           m.id_sucursal, m.id_producto, m.fecha, m.existencia_resultante
    FROM core.movimientos_inventario m JOIN activos a USING (id_sucursal, id_producto)
    WHERE m.fecha >= a.inicio
    ORDER BY m.id_sucursal, m.id_producto, m.fecha, m.id_movimiento DESC
), intervalos AS (
    SELECT *, lead(fecha) OVER (PARTITION BY id_sucursal, id_producto ORDER BY fecha) AS siguiente
    FROM cierres
), dias AS (
    SELECT i.id_sucursal, i.id_producto, i.existencia_resultante, g.fecha::date AS fecha
    FROM intervalos i CROSS JOIN corte c
    CROSS JOIN LATERAL generate_series(i.fecha::timestamp,
        least(coalesce(i.siguiente - 1, c.fecha), c.fecha)::timestamp, interval '1 day') g(fecha)
)
SELECT date_trunc('month', fecha)::date AS mes, id_sucursal,
       count(DISTINCT id_producto) AS pares_activos,
       count(*) FILTER (WHERE existencia_resultante = 0) AS dias_par_sin_existencia,
       count(*) FILTER (WHERE existencia_resultante = 0)::numeric / count(*) AS tasa_desabasto
FROM dias GROUP BY 1, 2;
CREATE UNIQUE INDEX IF NOT EXISTS ix_kpi_desabasto_mensual
    ON kpi.desabasto_mensual (mes, id_sucursal);

-- Incidencias por mes de reporte; abiertas incluye las que están en proceso.
CREATE OR REPLACE VIEW kpi.incidencias_mensuales AS
SELECT date_trunc('month', fecha_reporte)::date AS mes, id_sucursal, tipo, severidad,
       count(*) AS total, count(*) FILTER (WHERE estatus <> 'resuelta') AS abiertas,
       avg(fecha_resolucion - fecha_reporte) AS dias_promedio_resolucion
FROM core.incidencias GROUP BY 1, 2, 3, 4;

-- Hallazgos de todos los procesos de la última corrida (mismo inicio).
CREATE OR REPLACE VIEW kpi.calidad_ultima_carga AS
SELECT h.regla, h.accion, count(*) AS conteo
FROM ops.calidad_hallazgos h JOIN ops.etl_ejecuciones e USING (id_ejecucion)
WHERE e.inicio = (SELECT max(inicio) FROM ops.etl_ejecuciones)
GROUP BY 1, 2;

-- Resumen de una fila; ventanas móviles ancladas al día posterior a la última
-- venta: [corte - 12 meses, corte) y los 12 meses anteriores, sin solapamiento.
CREATE OR REPLACE VIEW kpi.resumen_ejecutivo AS
WITH corte AS (SELECT max(fecha_hora::date) + 1 AS fecha FROM core.ventas), ventas AS (
    SELECT coalesce(sum(total), 0) AS ingreso_total, count(*) AS tickets,
           round(avg(total), 2) AS ticket_promedio,
           coalesce(sum(total) FILTER (WHERE fecha_hora >= c.fecha - interval '12 months'), 0) AS ingreso_ultimos_12_meses,
           coalesce(sum(total) FILTER (WHERE fecha_hora >= c.fecha - interval '24 months'
               AND fecha_hora < c.fecha - interval '12 months'), 0) AS ingreso_previos,
           count(DISTINCT id_cliente) FILTER (WHERE fecha_hora >= c.fecha - interval '12 months') AS clientes_activos_12_meses
    FROM core.ventas CROSS JOIN corte c WHERE estatus = 'completada'
), inventario AS (
    SELECT count(*) FILTER (WHERE estado = 'sin_existencia') AS pares_sin_existencia,
           count(*) FILTER (WHERE estado = 'exceso') AS pares_exceso,
           count(*) FILTER (WHERE estado = 'sin_rotacion') AS pares_sin_rotacion
    FROM kpi.cobertura_inventario
)
SELECT v.ingreso_total, v.ingreso_ultimos_12_meses,
       100 * (v.ingreso_ultimos_12_meses - v.ingreso_previos) / nullif(v.ingreso_previos, 0) AS crecimiento_pct,
       v.tickets, v.ticket_promedio, v.clientes_activos_12_meses, i.*,
       (SELECT count(*) FROM core.incidencias WHERE estatus <> 'resuelta') AS incidencias_abiertas
FROM ventas v CROSS JOIN inventario i;
