# Guion de demostración — T38

Duración sugerida: 12–15 minutos de presentación. Estado y límites en
[cierre](completion.md); preparación y recuperación en [runbook](../../docs/runbook.md).
No ejecutar fits reales ni reevaluar holdouts durante la defensa.

| Paso | Mostrar/ejecutar | Evidencia y alcance |
|---|---|---|
| 1. Problema y arquitectura | Entrada al inicio del viaje y predicción en minutos; diagrama de la presentación | [Presentación](presentation.md), origen/calendario/pasajeros; sin destino predictor |
| 2. Ingesta y calidad | Registro idempotente, hash y ejemplo de gate fallido | [T06/T07](../../docs/t06-t07-ingestion.md), [D-04 y excepciones](../../docs/t08-t09-validation.md); FAIL reales conservados |
| 3. Cortes y entrenamiento | Tablas de cohortes, target UTC, train-only, límites | [T14](../quality/t14_completion.md), [T33](../retraining/t33_challenger.md); resultados ya congelados |
| 4. Registry | Consultar champion y mostrar v4/v5 en MLflow nativo | .venv-mlflow/Scripts/python.exe -m src.training.champion --resolve; v5 sin alias |
| 5. Serving Docker | Consultar /health, /model-info y smoke de API 8080 | [T25](../../docs/t23-t25-docker.md); requiere seed e imagen locales existentes |
| 6. CI | Mostrar rojo/verde y merge verde | [T26](../monitoring/t26_github_ci.md); historial remoto, no un job nuevo T35–T38 |
| 7. Drift y trigger | Reporte mensual, PSI y recomendación | [Replay](../monitoring/t29-t31_monthly_replay.md), [trigger](../retraining/t32_trigger.md); replay retrospectivo, sin servicio histórico inventado |
| 8. Challenger real | MAE v4/v5 y gate | [T34](../retraining/t34_comparison.md); mejora 0,737317 % <2 %, rechazo |
| 9. Workflow aislado | Ejecutar comando siguiente | 48 filas TEST_ONLY, registro real en namespace sintético; sin alias |
| 10. Promoción/rollback aislados | Ejecutar demo siguiente | Dos constantes TEST_ONLY; rollback en otro proceso y recuperación de fallo HTTP |
| 11. Reproducibilidad y límites | Mostrar manifiesto/export, JUnit y pendientes humanos | [Trazabilidad](traceability.md); export del trabajo local, no clon remoto ni revisión de otra persona |

Desde la raíz, con el entorno aprobado, destinos nuevos y recursos del runbook:

```powershell
.\.venv-mlflow\Scripts\python.exe -m scripts.demo_workflow --output-dir .cache/defensa-workflow
.\.venv-mlflow\Scripts\python.exe -m scripts.demo_lifecycle --output-dir .cache/defensa-lifecycle --external-rollback
```

Cada demo guarda logs/SQLite/artefactos/diario/resultado y detiene sus servicios.
Si un comando falla, mostrar el fallo y el último recibo; no cambiar reglas,
promover v5 ni detener procesos ajenos para que la demostración parezca verde.
Las mejoras de las constantes sintéticas no describen la calidad de LightGBM.

Preparación de la defensa completada técnicamente; presentación oral y
revisión por otro integrante **NO VERIFICADAS**.
