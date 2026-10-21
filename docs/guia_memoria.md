# Guía para la memoria de estadía

Qué evidencia del repositorio respalda cada capítulo. Las cifras corresponden a la semilla 42 y pueden reproducirse con los comandos del [manual técnico](manual_tecnico.md).
Ajusta la estructura al formato oficial de la UPQ.

| Capítulo | Contenido sugerido | Evidencia en el repo |
|---|---|---|
| Introducción | Contexto de NexaTech (ficticia), problemática, justificación, objetivos. | Propuesta original; `docs/01_requerimientos.md` §1. |
| Marco teórico | ETL y calidad de datos; modelado relacional; pronóstico de demanda intermitente (Croston/SBA); gradient boosting con pérdida Poisson; validación temporal (origen móvil); métricas WAPE y sesgo; demanda censurada; políticas de inventario (s, S). | `docs/04` (política s, S), `docs/05` (modelo, métricas, censura). |
| Metodología | Fases de 2 semanas del cronograma; trabajo en pareja con Git; agentes de código (Claude, Codex) como herramienta, con revisión humana y pruebas. | Historial de commits en GitHub; `AGENTS.md`; CI. |
| Requerimientos | RF y RNF con prioridad; alcance; riesgos. | `docs/01`. |
| Diseño | Arquitectura por capas; modelo entidad-relación; diccionario de datos; esquemas core, ops y kpi. | `docs/02`, `docs/03`, `db/*.sql`. |
| Datos simulados | Reglas de simulación; volumen; defectos inyectados con bitácora. | `docs/04`; `data/ground_truth/metadata.json`. 181,054 tickets; 640,673 renglones; 16,502 defectos. |
| ETL y calidad | Extracción de formatos heterogéneos; 18 reglas; recuperación de datos (fusión de clientes, reconstrucción de precios, corrección de fechas). | `reports/etl/calidad.md`: 18/18 tipos detectados, 100 % de precisión, 97-100 % de exhaustividad; carga en ≈50 s. |
| Análisis exploratorio | Estacionalidad, Pareto, patrones de calendario, inventario, incidencias. | `reports/eda/README.md` y sus 8 figuras. |
| Indicadores | Vistas KPI y cómo se validaron. | `db/vistas.sql`; `docs/03` (sección Indicadores). |
| Modelo predictivo | Variables, algoritmo, validación, comparación con 4 baselines, hallazgo sobre la censura, intervalos. | `docs/05`; `reports/ml/backtest.md` (WAPE producto-semana ≈26 % contra 29 % de la media móvil). |
| Alertas | Reglas y su evaluación contra faltantes reales. | `docs/05` §Intervalos y alertas: 54 % de exhaustividad con p90. |
| API y dashboard | Rutas, seguridad (roles, clave de acceso), páginas. | `src/datacore/api/app.py` (`/docs`), `manual_usuario.md`, capturas del dashboard. |
| Infraestructura | Respaldos con prueba de recuperación, monitoreo, bitácoras, proceso diario, CI, contenedor. | `docs/06`; `ops.respaldos`, `ops.monitoreo`, `ops.corridas`; ejecución en GitHub Actions. |
| Pruebas | Estrategia: unidad, integración con base, anti-fuga del modelo, extremo a extremo en CI. | `tests/` (≈70 pruebas); insignia de CI. |
| Resultados | Tabla resumen de métricas por componente. | Las de arriba. |
| Competencias TSU | Relación con las 3 competencias de la propuesta. | `docs/01`; propuesta §12. |
| ODS 9 y 12 | Infraestructura digital; menos exceso de inventario y menos desabasto. | Cifras de alertas de exceso y sin rotación (`/alertas`). |
| Conclusiones | Logros, limitaciones (datos simulados, un solo periodo de despliegue), trabajo futuro. | `docs/05` §Limitaciones; ajuste del umbral de alertas; despliegue. |
| Anexos | Manuales, diccionario de datos, reportes. | `docs/manual_*`, `docs/03`, `reports/`. |

## Figuras recomendadas

1. Arquitectura (diagrama de `docs/02`).
2. Diagrama entidad-relación (`docs/03`).
3. Ventas mensuales y estacionalidad (`reports/eda/ventas_mensuales.png`).
4. Mapa de calor por categoría y mes (`reports/eda/categorias_mes.png`).
5. Curva de Pareto (`reports/eda/pareto_productos.png`).
6. Tabla de detección de defectos (`reports/etl/calidad.md`).
7. Comparación del modelo con los baselines (`reports/ml/backtest.md`).
8. Capturas del dashboard: Inicio, Alertas y Pronóstico.
