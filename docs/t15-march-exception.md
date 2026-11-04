# T15: excepción académica de marzo y evaluación del baseline congelado

Fecha: 2026-11-03, America/Costa_Rica. El usuario autorizó expresamente: «Hagamos una excepción y no rechacemos el lote solo sobre este mes y asi podemos cerrar T15». La implementación y la ejecución se verifican antes de declarar resultados.

## Alcance de la excepción

[Registro versionado](../configs/quality-exception-2025-03.json): solo marzo de 2025, SHA-256 raw `20c4b77cce457b7cfdae77c5069ca7dc91c167f876a41467f4502ab69487a186`, y reporte FAIL `077a819319564b4eb4913a4e389da48a`. Se conserva su SHA-256 `90586cd9bd750d0e1894e899d6871376bd924af29069f05c2bb5b952e175b261`. No se reescriben esos originales ni se cambia ningún umbral global de D-04.

La única regla dispensada a nivel de lote es rows.duration_nonpositive: 22.280/4.145.257 (0,537482 %) frente a 0,50 %. Las duraciones cero/negativas y todas las demás filas inválidas siguen excluidas. La unión original es 23.886 filas; 4.121.371 potencialmente elegibles. La revalidación debe reproducir esos conteos y normalizaciones, verificar integridad/exhaustividad y no tener otro FAIL.

[Motor de autorización](../src/validation/exceptions.py): exige documento aprobado, coincidencia exacta de mes/hash/configuración/política, hash del reporte original y fallo autorizado. El CLI requiere --quality-exception explícito: la existencia del registro no cambia la ejecución normal. Otro mes/hash, reglas nuevas, conteos diferentes, configuración alterada, registro revocado o reporte original modificado bloquean el consumo.

El nuevo marcador conserva checks con FAIL y quality_passed=false; raw_quality_status=FAIL. La aceptación efectiva tiene status=WARN, execution_status=VALIDATED_REAL_EXCEPTION y data_quality_approved=true por decisión humana. No se presenta como calidad medida PASS. El lector de features verifica esa evidencia y la propaga a su manifiesto; quitar el registro o revocarlo impide el consumo posterior. approved_for_training=false permanece como ausencia de autorización automática de nuevos entrenamientos.

## Evaluación y cierre de T15

[baseline_evaluate.py](../src/training/baseline_evaluate.py) evalúa el ajuste congelado previamente auditado, sin modificarlo ni recalcular la mediana con validación. Verifica sus doce fuentes train, configuración, modelo, hashes/conteos, secuencia de etiquetas y posición exacta de la mediana. Exige catálogo explícito de los tres meses de validación aprobados; aparta etiquetas que alcanzan/cruzan el corte de abril y conserva trazabilidad de fila.

Esta continuación completa la separación de ajuste/evaluación aprobada previamente: T15 usa el lector causal de T14 y todas las fuentes aprobadas train/validation; no exige preparar test/replay para calcular MAE/RMSE. La preparación integral de T14 sobre 24 meses queda independiente y pendiente. No se declara una T14 incompleta como completa ni se amplía la excepción a los nueve meses restantes.

Se publican modelo evaluado nuevo, validation_predictions.parquet, validation_target.parquet y validation_context.parquet alineados; baseline_manifest.json al final. El nuevo manifiesto enlaza el hash del ajuste y del modelo original, fuentes, excepción, cortes, conteos, MAE/RMSE y recursos. El modelo original de ajuste conserva su estado histórico pendiente; no se sobrescribe. El nuevo resultado puede completar técnicamente T15, con revisión humana independiente, sin cerrar T14, registrar/promover un champion ni ejecutar T16/T17.

Perfil de preparación/evaluación: preflight de 4 GiB libres y 50 GiB de disco, límite RSS supervisado de 2 GiB, cuatro hilos, bloques ≤65.536 y plazo de dos horas. Es supervisión cooperativa, no un límite duro del SO. No hay submuestreo ni nuevas dependencias. Procedencia LOCAL_UNVERIFIED con URL/fecha originales nulas; la excepción no verifica origen remoto.

```powershell
.\.venv\Scripts\python.exe -m src.validation.run --year 2025 --month 3 --quality-exception configs/quality-exception-2025-03.json
.\.venv\Scripts\python.exe -m src.training.baseline_evaluate --fit-batch RUTA_AJUSTE_CONGELADO --inputs configs/validation-feature-batches.local.json
```

Estado de ejecución: COMPLETA Y AUDITADA; cierre técnico T15 PASS, resultados disponibles para revisión humana. Los artefactos/datos/catálogos locales no se incorporan a Git.

## Resultados reales y verificación final

T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [Reporte completo](../reports/quality/t15_baseline_validation.md). Marzo revalidado con 4.121.371 elegibles y 23.886 exclusiones, FAIL original intacto. 380 pruebas en desarrollo y wheel, auditoría de todas las etiquetas/contextos/predicciones y métricas verificada. Estado de ejecución anterior EN CURSO superado; cierre técnico T15 PASS y revisión humana pendiente.
