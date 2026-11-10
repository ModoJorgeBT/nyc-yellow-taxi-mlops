# T32 — Recomendación real auditada

**PASS técnico, 2026-11-09.** Reglas aprobadas por el usuario antes de
ejecutarlas. Resultado: **RETRAIN_RECOMMENDED**, sin iniciar entrenamiento
desde el evaluador ni modificar el champion LightGBM v4.

| Regla | Evidencia de los reportes T31 congelados |
|---|---|
| PSI >0,20, misma feature y dos meses consecutivos | passenger_count_missing, julio/agosto de 2025 |
| MAE >115 % de validation, dos meses consecutivos | septiembre/octubre, octubre/noviembre y noviembre/diciembre de 2025 |
| Revisión trimestral | REVIEW_REQUIRED en reloj retrospectivo; no activa entrenamiento |

Referencia MAE fija: 6,496404304242834 minutos; umbral estricto 115 %:
7,470864949879259 minutos. Mínimo 1.000 filas y cobertura de etiquetas
elegibles completa; meses ausentes no forman parejas. Los FAIL D-04 y
sus aceptaciones exactas se conservan; calidad no aceptada bloquea.

La fecha virtual de observación es 2026-01-02T05:00:00Z, con corte de train
del champion 2025-01-01. El aviso trimestral se refiere a ese reloj de replay,
no afirma que el modelo estuviera desplegado en 2025 ni sustituye la fecha
real de ajuste de T16. No se acredita publicación histórica de TLC.

Reporte local: reports/retraining/triggers/572f46fc38a84fa7996fce28c0c8653c.json;
SHA-256 e1539ff36b100bc5d694fb44bb82cb44390c3814afe98de2d0913f75d39f3fbe.
Perfil aprobado: configs/retraining.yaml, SHA canónico
560d2108aa754cfc681e41c5febdd52f7b0708d8357e84a1af8be0dc6c5cab71.

Pruebas focalizadas: 100 aprobadas, incluyendo fronteras, consecutividad,
meses faltantes, n mínimo, ausencia de etiquetas, evidencia alterada,
modelo incorrecto, no acción sin fit, gates, descarga y supervisión.
Los resultados reales de T33/T34 se registran por separado; aprobar esta
recomendación no implica aprobar un futuro candidato para serving.
