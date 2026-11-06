# T16/T17 — Contrato y verificación de la primera comparación

Fecha: 2026-11-05, America/Costa_Rica. **Cierre técnico auditado de T14, T16 y T17; revisión humana de resultados independiente.** No cierra MLflow, champion, API, Docker ni CI.

## Evidencia real

- [T14 integral](../reports/quality/t14_completion.md): 24 meses, cuatro particiones y auditoría completa de valores/identidades/cortes; 89.262.149 filas finales.
- [T16](../reports/quality/t16_training.md): SGD Huber y MLP16, cada uno con las 41.119.495 filas train, una pasada y 10.039 bloques; preprocesamiento ajustado únicamente con train.
- [T17](../reports/evaluation/t17_model_comparison.md): baseline congelado y ambos candidatos sobre 11.163.264 filas validation y 12.712.466 test. SGD elegido con validation antes de abrir test; selección inmutable después. Métricas y segmentos recomputados independientemente.

La configuración [candidates.yaml](../configs/candidates.yaml), el [protocolo](t16-t17-execution-proposal.md) y el [perfil 8/4](d02-t16-resource-review.md) identifican esta ejecución. `configs/model.yaml` y `configs/data.yaml` conservan los hashes de la preparación T14; el perfil histórico 12/8 no se reescribe para cambiar su identidad.

## Software verificado antes del ajuste real

**423 pruebas aprobadas en desarrollo y 423 desde wheel instalado**, en un checkout sin `src` ni datos reales; 30 imports aislados, Ruff lint/formato sobre 63 archivos y `pip check` en ambos entornos PASS. No se añadieron dependencias para estos dos candidatos. Dos advertencias de minibatch MLP proceden exclusivamente de fixtures de once filas; las ejecuciones reales no emitieron esas advertencias.

Pruebas relevantes: [candidatos unitarios](../tests/unit/test_candidates.py), [candidatos integrados](../tests/integration/test_candidates.py), [métricas y segmentos](../tests/unit/test_evaluation_metrics.py), [evaluación integrada](../tests/integration/test_candidate_evaluation.py), [excepciones DQ](../tests/integration/test_quality_exception.py).

Los casos cubren varios bloques, vocabulario/scaler exclusivamente train, categorías futuras, serialización equivalente, lectura selectiva sin abrir particiones futuras, destinos con índices saltados, percentiles exactos, límites/timeout y fallos sin publicación completa. Una fixture hace que otro modelo gane en test y verifica que no cambia la elección fijada con validation.

La auditoría real T16 contrasta contadores internos, vocabulario exhaustivo y hash de todas las etiquetas. La auditoría T17 reconstruye predicciones con operaciones sobre los pesos, deriva segmentos por identidad y verifica los cuantiles sobre todos los errores. No sustituye datos completos por una muestra.

## Comandos implementados

```powershell
.\.venv\Scripts\python.exe -m src.training.train --help
.\.venv\Scripts\python.exe -m src.evaluation.run --help
```

El entrenador exige `--split` y, en modo REAL, `--audit` con el recibo completo T14. El evaluador exige además `--training` y `--baseline`; ambos guardan UUID nuevo y rechazan alteraciones de configuración/linaje. `--test-only` usa únicamente fixtures y no concede aprobación a datos reales. No basta ejecutar `--config` sin esas entradas.

Los recibos locales de esta ejecución están en `.cache/t14-approved/audit.json`, `.cache/t16/audit.json` y `.cache/t17/audit.json`; los directorios de artefactos están identificados en los reportes. Otro checkout necesita los archivos locales correspondientes o ejecutar nuevamente la preparación autorizada; Git no contiene Parquet ni modelos.

## Límites y decisiones posteriores

Se respetaron cuatro hilos, un candidato, mínimo 8 GiB libres/50 GiB disco, máximo 4 GiB RSS y dos horas. Los controles son cooperativos para estos estimadores; no acreditan un límite duro del sistema operativo ni Docker. La procedencia LOCAL_UNVERIFIED y las excepciones D-04 se conservan explícitas.

MLP fue peor que el baseline y SGD empeoró ligeramente su P90 en validation; no hay promoción automática por mejorar MAE. D-05, D-07 y la aprobación de champion siguen pendientes. La extensión LightGBM solicitada después de esta comparación usa un protocolo separado, aprobado para evaluación solo con validation; una nueva evaluación final independiente queda pendiente. Ver [propuesta y alcance](t16-lightgbm-extension-proposal.md).

## Extensión LightGBM verificada

LightGBM 4.7.0 fue entrenado con las 41.119.495 filas train y 100 árboles. En las 11.163.264 filas validation: MAE 6.496404, RMSE 9.847425, MedAE 4.631360 y P90 13.478764 minutos. Ajuste y evaluación auditados; 447 pruebas por entorno. Solo validation: una nueva evaluación final independiente sigue pendiente. La selección SGD y el test de la primera comparación permanecen intactos; no hay promoción.

La suite ampliada tiene **447 PASS en desarrollo y 447 PASS desde wheel instalado**, 35 imports aislados y Ruff sobre 70 archivos; pip check correcto en ambos entornos. Las 423 pruebas anteriores documentan el snapshot congelado de la primera comparación. [Recursos, identidades, métricas y segmentos de LightGBM](../reports/evaluation/lightgbm_validation.md).

CLI adicionales: `python -m src.training.lightgbm_train --help` y `python -m src.evaluation.lightgbm_run --help`. El segundo exige `--original-evaluation` y auditorías REAL de T14 y de la primera comparación; solo abre la partición validation. Los archivos de configuración y los manifiestos registran esta restricción.


**Evaluación final independiente completada y auditada — 2026-11-05:**
enero–marzo de 2026, 10.937.087 viajes; MAE LightGBM **7,742891 min**, SGD
**8,352735** y baseline **9,141254**. Se excluyeron 139.305 filas DQ mediante
tres excepciones humanas exactas y 814 por corte de etiqueta; los 27 raw,
modelos y selección de 2025 permanecen intactos. Reinicio de recursos aprobado
6 GiB libres/2 GiB RSS solo para inferencia final; entrenamiento 8/4 y preparación
4/2 sin cambios. 474 pruebas por entorno y auditoría completa. Sin promoción.
[Reporte final y trazabilidad](../reports/evaluation/lightgbm_final_evaluation.md). Las referencias anteriores a evaluación
final pendiente describen la entrega histórica previa a esta aprobación. T18
requiere D-07 y dependencias; no hay Registry ni champion todavía.
