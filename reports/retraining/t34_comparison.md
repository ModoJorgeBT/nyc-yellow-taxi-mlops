# T34 — Comparación final independiente y gate

**PASS técnico de la tarea, 2026-11-09. Resultado del gate: CHALLENGER_REJECTED.**
La versión 5 permanece registrada como candidato rechazado; champion=4 se conserva.

La comparación utilizó las mismas **11,603,243 filas** de abril–junio 2026 para ambos modelos, congelados antes de abrir las métricas. Reglas aprobadas previamente; no se ajustaron parámetros ni se promovió un modelo.

| Modelo | MAE min | RMSE min | MedAE min | P90 min |
|---|---:|---:|---:|---:|
| Champion v4 | 8.096751 | 12.634822 | 5.314210 | 17.904528 |
| Challenger v5 | 8.037052 | 12.515600 | 5.279114 | 17.752281 |

El MAE mejora **0.737317 %**, inferior al **2 % mínimo**. Ese es el único gate incumplido. RMSE/P90 globales mejoran; MAE/P90 de los 27 segmentos requeridos (tres meses, cuatro franjas y 20 rutas) cumplen el margen máximo de aumento del 5 %, con al menos 1.000 filas por segmento.

Calidad aceptada con tres excepciones exactas, identidad/cobertura, cortes, ausencia de leakage, serialización, smoke y misma población verificados. Se conservaron 155.207 exclusiones D-04 y 874 temporales; los tres FAIL originales y D-04 global permanecen intactos.

La auditoría independiente volvió a calcular todas las predicciones de ambos modelos y verificó MAE/RMSE y cuantiles mediante CDF completa, incluyendo los 28 grupos por modelo. Sin submuestreo, reajustes, otra selección ni una nueva comparación con parámetros distintos. Es verificación de la misma evaluación congelada.

Primero se predijo usando solo features iniciales; las etiquetas se unieron después por identidad de feature/fila y posición. Destino únicamente para segmentación. La reserva es de un solo uso por perfil/periodo, incluso si cambia el identificador de cohorte o candidato. No se reutilizó el test original 2025 ni se presentó Q1 2026 como independiente.

Recursos de la evaluación: cuatro hilos, un modelo a la vez y preflight 6 GiB RAM/50 GiB disco. Cada modelo tardó menos de 72 segundos y el máximo RSS observado fue 624,90 MiB, inferior al límite de 2 GiB. Auditoría con el mismo presupuesto; los límites de entrenamiento no se elevaron.

El resultado, métricas y artefactos se registraron también en el run de v5; final_evaluation=COMPLETED_FROZEN_ONCE y t34_decision=CHALLENGER_REJECTED. Se verificó que el alias champion sigue en v4 y que no cambian pesos ni la aprobación T19.

Evidencia local, excluida de Git:
- Evaluación: `reports/retraining/evaluations/final/48c35a43383045059d4e6c26628ba99f/evaluation.json`, SHA-256 `15340ec8198a051a1f9f66d7e21da568152d929adb72540b54dfbbb0d8b29fab`.
- Gate: `reports/retraining/comparisons/5836e503c812480d9f8ae7276453638b.json`, SHA-256 `17149de9f8c9e26c8e6e9129f09272c07400d4ecc64b8bc84e671c34cf9f687f`.
- Auditoría completa: `.cache/t32-t34/paired-final-audit.json`.
- Recibo MLflow: `.cache/t32-t34/mlflow-final-gate.json`.

Auditor reproducible: `python -m scripts.audit_retraining --evaluation <evaluation.json> --output <nuevo-audit.json>`. Registro de evidencia, sin aliases: `python -m scripts.log_retraining_gate --comparison <gate.json> --output <nuevo-recibo.json>`.

T34 exige una decisión justificada; no exige forzar que gane el challenger. T32–T34 tienen cierre técnico real. T35–T38 y cualquier promoción/rollback siguen pendientes. No se realizó commit/push de estos cambios locales.

[Contrato y comandos](../../docs/t32-t34-retraining.md), [trigger T32](t32_trigger.md) y [ajuste/registro T33](t33_challenger.md).
