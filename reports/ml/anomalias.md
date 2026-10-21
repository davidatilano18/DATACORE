# Detección de anomalías

Selección exploratoria por mayor F1 en el historial completo; empate: umbral mayor. No es una estimación fuera de muestra.

| grupo | verdaderos_positivos | falsos_positivos | fallas | precision | exhaustividad | f1 | umbral |
|---|---|---|---|---|---|---|---|
| total | 96 | 153 | 325 | 0.3855 | 0.2954 | 0.3345 | 2.3300 |
| 2-3 h | 10 | 153 | 79 | 0.0613 | 0.1266 | 0.0826 | 2.3300 |
| 4-5 h | 16 | 153 | 105 | 0.0947 | 0.1524 | 0.1168 | 2.3300 |
| 6-8 h | 70 | 153 | 141 | 0.3139 | 0.4965 | 0.3846 | 2.3300 |
| total | 73 | 96 | 325 | 0.4320 | 0.2246 | 0.2955 | 2.5800 |
| 2-3 h | 5 | 96 | 79 | 0.0495 | 0.0633 | 0.0556 | 2.5800 |
| 4-5 h | 12 | 96 | 105 | 0.1111 | 0.1143 | 0.1127 | 2.5800 |
| 6-8 h | 56 | 96 | 141 | 0.3684 | 0.3972 | 0.3823 | 2.5800 |
| total | 39 | 22 | 325 | 0.6393 | 0.1200 | 0.2021 | 3.0900 |
| 2-3 h | 4 | 22 | 79 | 0.1538 | 0.0506 | 0.0762 | 3.0900 |
| 4-5 h | 6 | 22 | 105 | 0.2143 | 0.0571 | 0.0902 | 3.0900 |
| 6-8 h | 29 | 22 | 141 | 0.5686 | 0.2057 | 0.3021 | 3.0900 |

Umbral elegido: 2.33. Anomalías publicadas: 1154.

Se excluyen eventos festivos del calendario y de la referencia; pueden ocultar fallas reales. Evaluación por sucursal-día, unión de métricas. Por horas se reutilizan las falsas alarmas globales; las precisiones de estratos no son aditivas. El denominador incluye fallas en festivos y calentamiento.
