# T10/T11 — Resultados ejecutados del pipeline sintético

Cada caso ejecutó ingesta HTTP simulada, manifiesto y API de validación sobre fixtures. El CLI se comprueba aparte en la suite de integración. Ningún dato es TLC real ni queda aprobado para entrenamiento. Política synthetic-tests-v1, salvo normal_pending (configuración real PENDIENTE); critical_null_zone cambia la tolerancia de zonas nulas a 0.

| Caso | Calidad | Ejecución | Lectura | Filas leídas | Filas publicadas | Aprobado para entrenamiento |
|---|---|---|---|---:|---:|---|
| valid | PASS | VALIDATED_TEST_ONLY | FULL_PARQUET | 12 | 12 | False |
| tolerated_null_zone | WARN | VALIDATED_TEST_ONLY | FULL_PARQUET | 12 | 11 | False |
| critical_null_zone | FAIL | REJECTED | FULL_PARQUET | 12 | 0 | False |
| missing_column | FAIL | REJECTED | PREFLIGHT_ONLY | no evaluado | 0 | False |
| normal_pending | FAIL | REJECTED | PREFLIGHT_ONLY | no evaluado | 0 | False |
| unmarked_data | FAIL | REJECTED | NOT_STARTED | no evaluado | 0 | False |

Los artefactos completos y JSON por intento están exclusivamente en .cache/t10-t11-demo; resumen JSON en .cache/t10-t11-examples.json. Los dos casos publicados tienen validation.json y metadata TEST_ONLY. Ningún rechazo publicó datasets. No se modificó data/raw real ni se publicaron datos en data/validated real.

[Contrato y pruebas T10/T11](../../docs/t10-t11-data-pipeline.md).
