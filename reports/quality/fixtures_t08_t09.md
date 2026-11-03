# T08/T09 — Reportes ejecutados con fixtures

Datos exclusivamente sintéticos. No son resultados de TLC ni aprobación para entrenamiento.

Perfil synthetic-tests-v1 de tests/unit/test_validation.py (compartido desde tests/fixtures/policies.py en T11): máximo 120 minutos, mínimos de una fila, tasas 0.5 excepto pasajeros nulos 1.0 y catálogo synthetic-v1 [161, 236, 264, 265]. Son valores para ejercitar pruebas de doce filas; no están calibrados para datos reales. La prueba crítica cambia solamente la tolerancia de zonas nulas a 0.

| Caso | Estado | Filas leídas | Exclusiones propuestas | Elegibles propuestas | Supera calidad de prueba | Aprobado para entrenamiento |
|---|---|---:|---:|---:|---|---|
| valid | PASS | 12 | 0 | 12 | True | False |
| null_zone | WARN | 12 | 1 | 11 | True | False |
| null_timestamp | WARN | 12 | 1 | 11 | True | False |
| nonpositive_duration | WARN | 12 | 2 | 10 | True | False |
| pickup_outside_month | WARN | 12 | 1 | 11 | True | False |
| duplicate | WARN | 12 | 0 | 12 | True | False |
| invalid_passengers | WARN | 12 | 0 | 12 | True | False |
| missing_column | FAIL | 0 | None | None | False | False |
| incompatible_type | FAIL | 0 | None | None | False | False |
| extra_column | PASS | 12 | 0 | 12 | True | False |
| pending_policy | FAIL | 12 | 0 | 12 | False | False |
| critical_zone_failure | FAIL | 12 | 1 | 11 | False | False |
| unmarked_data | FAIL | 12 | 0 | 12 | False | False |

None indica que un fallo estructural impidió evaluar filas. pending_policy usa la configuración real PENDIENTE; sus conteos de elegibilidad son parciales (eligibility_complete=false). unmarked_data bloquea el perfil TEST_ONLY fuera de fixtures marcadas. quality_passed no comprueba linaje ni publica datos. Los reportes JSON completos quedan en .cache/t08-t09-examples.json, sin versionar.

[Contrato y evidencia](../../docs/t08-t09-validation.md).
