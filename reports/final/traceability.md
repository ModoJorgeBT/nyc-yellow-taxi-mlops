# Matriz de trazabilidad final

| Afirmación | Evidencia | Alcance/límite |
|---|---|---|
| Arquitectura y contratos | [Arquitectura](../../docs/architecture.md), [spec](../../spec.md), [decisiones](../../docs/decisions.md) | Convenciones explícitas; PDF no garantiza disponibilidad al abordar |
| Ingesta y D-04 | [Ingesta](../../docs/t06-t07-ingestion.md), [calidad](../../docs/t08-t09-validation.md) | Procedencia desconocida de archivos aportados conservada |
| Particiones y cobertura | [T14](../quality/t14_completion.md), [T33](../retraining/t33_challenger.md) | Cortes/filas elegibles, excepciones sin cambiar umbrales |
| Champion real v4 | [Selección](../model_selection.md), [final Q1 2026](../evaluation/lightgbm_final_evaluation.md) | Aprobación T19; sin tuning |
| Serving y persistencia | [Docker](../../docs/t23-t25-docker.md) | Smoke real histórico; T35 no reconstruyó ni actualizó el volumen |
| CI rojo/verde | [GitHub T26](../monitoring/t26_github_ci.md), [historial](../../docs/commit-history.md) | Merge 21a6abf; no ejecución remota nueva para cambios locales |
| Drift/desempeño/trigger | [Replay](../monitoring/t29-t31_monthly_replay.md), [T32](../retraining/t32_trigger.md) | Retrospectivo; no prueba servicio histórico |
| V5 rechazado y v4 conservado | [T34](../retraining/t34_comparison.md) | Ganancia 0,737317 % <2 %, demás controles cumplen |
| Promoción/rollback/compensación HTTP | .cache/t35-t38/demo-external/demo-result.json y tracking/lifecycle dentro de esa raíz | TEST_ONLY; rollback ejecutado por CLI en otro proceso; servicios propios detenidos |
| Workflow completo | .cache/t35-t38/workflow-first/workflow-result.json | 48 filas sintéticas; candidato sin alias, gate NOT_EVALUABLE correcto |
| Reanudación real sin repetir ciencia | reports/retraining/workflows/a0ffd7a4748b40679364cfa59a07f328.json | 0 fits, 0 evaluaciones, 0 descargas; candidato v5 rechazado |
| Reproducción limpia automatizada | .cache/repro38/reproduction-result.json, EXPORT_MANIFEST.json en source, retry-http/rest-junit.xml bajo source/.cache | 681 PASS/una omisión; timeout original conservado; export sin .git, no revisión humana |
| Preparación académica | [Guion](demo-script.md), [presentación](presentation.md), [runbook](../../docs/runbook.md) | Defensa oral y revisión humana NO VERIFICADAS |

Los JSON, SQLite, pesos y logs de ejecución son locales e ignorados por Git.
Los Markdown públicos resumen resultados trazables; un clon no contiene esa
evidencia binaria. Conservar los directorios originales para revisión autorizada.
El [cierre](completion.md) contiene hashes y resultados de la verificación final.
