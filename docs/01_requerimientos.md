# 01 · Requerimientos y alcance

**Proyecto:** DATACORE: Plataforma Inteligente de Gestión, Monitoreo y Análisis de Datos Empresariales
**Empresa (ficticia):** NexaTech Solutions S.A. de C.V.
**Equipo:** David Israel Atilano Quiroz · Ricardo Leonel Ordaz Aguilar
**Versión:** 0.1 (borrador del 20 de octubre de 2026)

## 1. Problema

NexaTech Solutions comercializa productos de consumo en 12 sucursales de 9 estados. Cada área genera su información por separado:

| Área | Sistema de origen | Formato de exportación |
|---|---|---|
| Ventas | Punto de venta (POS) | CSV por año (`ventas_AAAA.csv`, `detalle_venta_AAAA.csv`) |
| Compras | Hojas de cálculo | Excel (`productos.xlsx`, `proveedores.xlsx`) |
| Mercadotecnia | CRM | CSV en Windows-1252 separado por `;` (`clientes.csv`) |
| Almacén | Sistema de inventarios | CSV (`movimientos_inventario_AAAA.csv`, `inventario_actual.csv`) |
| Operaciones | Mesa de ayuda | CSV (`incidencias.csv`) |

No existe un repositorio central. Los datos llegan con duplicados, formatos inconsistentes, valores faltantes y errores de captura. Las decisiones de resurtido se toman con estimaciones manuales, y eso provoca desabastos (alrededor de 4.7 % de la demanda queda sin surtir) y, en otros productos, exceso de inventario.

## 2. Requerimientos funcionales

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | Generar un dataset simulado reproducible (semilla fija) de unos 3 años de operación, con defectos controlados y su bitácora. | Alta |
| RF-02 | Ingerir automáticamente los archivos de todas las áreas (CSV, Excel, distintas codificaciones). | Alta |
| RF-03 | Limpiar, estandarizar y validar los datos con reglas de calidad configurables. | Alta |
| RF-04 | Registrar cada hallazgo de calidad (regla, registro, acción tomada) y cada ejecución del ETL. | Alta |
| RF-05 | Cargar los datos validados en una base relacional con integridad referencial. | Alta |
| RF-06 | Calcular indicadores: ventas por periodo, sucursal, categoría y producto; ticket promedio; rotación; cobertura de inventario; tasa de desabasto. | Alta |
| RF-07 | Pronosticar la demanda semanal por producto y sucursal. | Alta |
| RF-08 | Generar alertas de riesgo de desabasto, exceso de inventario y productos sin rotación. | Alta |
| RF-09 | Exponer datos, indicadores, predicciones y alertas mediante una API. | Media |
| RF-10 | Ofrecer un dashboard interactivo con filtros por fecha, sucursal y categoría. | Alta |
| RF-11 | Respaldar la base de datos automáticamente y poder restaurarla. | Media |
| RF-12 | Monitorear la disponibilidad de los servicios (BD, API, dashboard) y registrar eventos. | Media |
| RF-13 | Detectar anomalías en ventas o inventario (complementario). | Baja |

## 3. Requerimientos no funcionales

| ID | Requerimiento |
|---|---|
| RNF-01 | **Reproducibilidad:** el mismo código con la misma semilla produce exactamente los mismos datos. |
| RNF-02 | **Rendimiento:** el ETL completo (unas 180 mil ventas y 640 mil renglones) termina en menos de 10 minutos en el servidor. |
| RNF-03 | **Trazabilidad:** todo registro rechazado o corregido puede rastrearse hasta su archivo y fila de origen. |
| RNF-04 | **Idempotencia:** volver a correr el ETL sobre los mismos archivos no duplica datos. |
| RNF-05 | **Calidad medible:** se reportan la precisión y la exhaustividad (recall) de las reglas de calidad contra la bitácora de defectos inyectados. |
| RNF-06 | **Seguridad básica:** credenciales fuera del código (`.env`) y un usuario de BD de solo lectura para el dashboard. |
| RNF-07 | **Mantenibilidad:** código en Python con pruebas automatizadas; documentación al día en `docs/`. |
| RNF-08 | **Portabilidad:** se puede ejecutar en Windows (desarrollo) y en Linux (servidor). |

## 4. Alcance

**Incluye:** generador de datos, ETL con reglas de calidad, base de datos PostgreSQL, análisis exploratorio, modelo de pronóstico de demanda, alertas de inventario, API, dashboard, respaldos, bitácoras, monitoreo básico, despliegue en un servidor y manuales técnico y de usuario.

**No incluye:** integración con sistemas reales, facturación, autenticación de usuarios finales con roles complejos, aplicación móvil ni procesamiento en tiempo real (la carga es por lotes).

## 5. Supuestos

- Todos los datos son simulados; no se usa información de personas ni empresas reales. Las marcas de productos son inventadas.
- El periodo simulado va del 1 de enero de 2023 al 31 de diciembre de 2025.
- La carga es por lotes, una vez al día. Para la demostración se procesa el histórico completo de una vez.

## 6. Riesgos

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Datos simulados poco realistas que hagan trivial el modelo | Media | Alto | Reglas de simulación documentadas: estacionalidad, tendencias, demanda censurada por faltantes, productos nuevos y descontinuados. |
| Python 3.15 sin ruedas (wheels) para alguna librería | Media | Medio | Ya se verificaron numpy, pandas, scikit-learn, FastAPI, Streamlit, psycopg y SQLAlchemy. Si algo falla, se usa Python 3.13. |
| No contar con un servidor o VPS a tiempo | Media | Medio | Desplegar en una VM Linux local o en una capa gratuita en la nube; los scripts no dependen del proveedor. |
| Carga de trabajo desigual entre integrantes | Baja | Medio | Frentes divididos con revisión cruzada (ver `AGENTS.md`). |
| Alcance demasiado amplio para 16 semanas | Media | Alto | Priorizar los RF de prioridad alta; RF-13 queda como opcional. |
