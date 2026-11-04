# T15 — Baseline real evaluado y excepción acotada de marzo

Fecha: 2026-11-03, America/Costa_Rica. **VERIFICACIÓN TÉCNICA COMPLETA: AJUSTE + VALIDACIÓN.** Resultados disponibles para revisión humana; no cierre de T14 integral ni de gates globales. [Contrato](../../docs/t15-baseline.md), [excepción autorizada](../../docs/t15-march-exception.md).

## Resultados medidos

| Dato | Resultado |
|---|---:|
| Train 2024, etiquetas disponibles al corte | 41.119.495 |
| Mediana global exacta, minutos | 12,983333 |
| Elegibles DQ de validación antes del corte | 11.164.194 |
| Apartadas por llegada igual/posterior al corte de abril | 930 |
| Predicciones de validación | 11.163.264 |
| MAE, minutos | 7,741890 |
| RMSE, minutos | 11,912962 |

Se reutilizó sin reajuste la constante del [ajuste train auditado](t15_train_fit.md). El archivo original conserva sus bytes y su estado histórico; se publica un modelo evaluado nuevo con la misma constante/filas/hash lógico de train. No se usó validación para calcular/elegir la mediana ni test/replay para ajustar, comparar o evaluar. Estas métricas corresponden únicamente a viajes elegibles de validación, no a todos los registros raw ni a un modelo champion.

| Mes 2025 | Raw | Elegibles DQ | Apartadas por corte | Evaluadas | Aceptación excepcional |
|---|---:|---:|---:|---:|---|
| 01 | 3.475.226 | 3.471.776 | 0 | 3.471.776 | No |
| 02 | 3.577.543 | 3.571.047 | 0 | 3.571.047 | No |
| 03 | 4.145.257 | 4.121.371 | 930 | 4.120.441 | Sí, solo este hash/reporte |

El corte de validation es 2025-04-01 00:00 America/New_York (04:00 UTC); llegada igual o posterior se excluye sin mover la fila. Es replay retrospectivo por evento y no acredita publicación histórica de los archivos.

## Excepción de marzo: calidad medida y aceptación humana

Se preservó íntegro el FAIL original 077a819319564b4eb4913a4e389da48a, SHA-256 90586cd9bd750d0e1894e899d6871376bd924af29069f05c2bb5b952e175b261. La regla duración no positiva sigue observando 22.280/4.145.257 (0,537482 %) frente al máximo global 0,50 %. El nuevo escaneo reprodujo todos los conteos/normalizaciones: 23.886 filas inválidas excluidas, 4.121.371 elegibles. No se conservaron duraciones cero/negativas.

Aceptación nueva: VALIDATED_REAL_EXCEPTION, status=WARN, raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true por autorización humana. Checks con FAIL se conservan. El registro está ligado al mes, SHA raw, configuración/política y reporte rechazado; otros meses/hashes/fallos o cambios de conteos bloquean. La ejecución normal sin --quality-exception sigue rechazando ese archivo. Para reproducir, conservar también el reporte FAIL original local cuyo hash exige el registro.

La autorización no certifica procedencia remota: los 15 originales usados conservan SHA/tamaño y LOCAL_UNVERIFIED con fuente/fecha nulas. No se ampliaron límites ni se descargaron datasets.

## Auditoría independiente

Se verificaron el ajuste exacto, sus doce fuentes y hash de modelo original, además de las tres fuentes de validation y su autorización vigente. Una lectura independiente de contextos/etiquetas aplicó el corte UTC, verificó identidades y reprodujo la secuencia completa de etiquetas y contextos publicados. Todas las predicciones tienen índice continuo y el mismo valor positivo/finito; MAE/RMSE se recalcularon sobre todas las etiquetas y coinciden dentro de 1e-12.

- Hash lógico de etiquetas de validation: `202c92b46e70787a83b9465e6a5ef6dfa48981539cbb3161a5e1d3466a60e617`.
- Hash lógico de contexto estructurado: `5ecf3a60e1f4b7216a83d72478e87cd42c2c194425e5bf64d71e311ec1653fae`.
- Hash del modelo train original: `221df1e9ec3bfd737f33aa61df20eb26b4ae65df7ce4755d13d5a6310b31012c`.
- Hash del modelo evaluado: `7d6e3eefd040f04f46e7a8f6ef6068fd65dcf86c56bb0e97cde5ecb8f0c8abf9`.
- Original FAIL intacto; 15 raw intactos; SQLite/staging/locks propios limpios.

## Artefactos, recursos y pruebas

Directorio local `data/processed/baselines/f44a7df0171b484788f059b0b1b10328`; baseline id `f44a7df0171b484788f059b0b1b10328`. Modelo JSON, predicciones, target y contexto de validation, con baseline_manifest.json al final. Estado BASELINE_REAL, evaluation_status=COMPLETE_VALIDATION y t15_complete=true; human_review_complete=false, t14_complete=false, model_registered=false y approved_for_serving=false.

Revalidación/features de marzo: 360.99 s, pico RSS 356.31 MiB. Evaluación: 482.83 s, pico RSS 385.07 MiB. Perfil aprobado 4 GiB RAM libre/2 GiB RSS/50 GiB disco y cuatro hilos; supervisión cooperativa, no límite duro del SO ni certificación Docker. El perfil de candidatos T16 conserva 12/8.

**380 pruebas aprobadas en desarrollo y 380 desde wheel instalado** en checkout sin src/data; 24 imports aislados, CLI y tests de rechazo/revocación/integridad/no refit. Ruff check/format y pip check ambos entornos correctos. Sin nuevas dependencias.

Wheel evaluación SHA-256 `67e22465cfb33755e0d8ec49a0a7ceaf89f2388171d7a4692990f8d3e0a198ef`; lock `372c8949a3c4fbc62c3f334d8ddf565ff213e56a80deca8d00a007cde6673529`. El wheel coincide byte por byte con los módulos actuales. El ajuste original tiene su wheel/evidencia propios en el informe anterior; no se atribuye todo a un commit inexistente.

Evidencia local: .cache/t15-close/march-result.json, evaluation-result.json, audit.json, software.json y logs. Catálogo de tres versiones: configs/validation-feature-batches.local.json. Datos/modelos/catálogos locales excluidos de Git; no hubo nuevo commit/push.

T15 queda técnicamente terminada para revisión del equipo. T14 integral sobre los 24 meses, candidatos T16, métricas segmentadas T17, MLflow, API, Docker, CI y promoción permanecen independientes; no se ejecutaron ni cerraron por este resultado.
