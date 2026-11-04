# T15 — Baseline de mediana global exacta

Fecha: 2026-11-03, America/Costa_Rica. **T15: AJUSTE Y VALIDACIÓN REALES COMPLETOS, CIERRE TÉCNICO AUDITADO.** T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [Reporte completo](../reports/quality/t15_baseline_validation.md). Revisión humana pendiente; no registro, serving, T14 integral ni T16.

## Alcance y prevención de leakage

[baseline.py](../src/training/baseline.py) conserva el flujo completo: consume un lote de particiones T14 explícito. Exige split_manifest.json publicado al final, ámbito coherente, configuración/fingerprint idénticos, conteos y hashes de tablas válidos, y linaje de las fuentes de train/validation sin cambios. REAL exige cobertura de los 24 meses del protocolo; TEST_ONLY conserva aislamiento. El flujo de ajuste independiente aprobado a continuación es distinto y no publica ese marcador completo.

La verificación de T15 abre únicamente artefactos y fuentes de train y validation. No abre archivos de test ni monitoring_replay para ajustar, evaluar o elegir el baseline. Las pruebas vigilan esos accesos, incluyendo cuando Parquet recibe un descriptor de archivo abierto. No se ajusta el preprocesador ni se cambia ninguna feature.

## Cálculo exacto con todos los datos

Cada etiqueta positiva y finita de train se inserta por bloques en una tabla SQLite temporal. El orden numérico se resuelve con un índice en disco: para n impar se toma la observación central; para n par, el punto medio de las dos observaciones centrales. No se promedian medianas de bloques, no se aproximan cuantiles y no se muestrea. El conteo final debe coincidir con todas las filas train publicadas por T14.

SQLite usa cache de 16 MiB, temporales de disco y un hilo. Journal/sincronización se desactivan solo en esta base descartable, nunca en los datos originales o en artefactos persistentes. Un fallo descarta el temporal y no publica un baseline completo. El índice no es un modelo ni una base MLflow.

La predicción de validación es la misma constante aprendida, una por cada fila de validation, con índice posicional que enlaza con su contexto T14. Se comprueba cobertura completa y se calculan MAE y RMSE solo en validation. La evaluación segmentada, MedAE/P90 y selección de candidatos se mantienen en T17, sin anticipar ese framework.

## Perfil de recursos aprobado

| Fase | RAM libre al inicio | Máximo RSS supervisado | Disco libre mínimo |
|---|---:|---:|---:|
| Preparación T14 y mediana T15 | 4 GiB | 2 GiB | 50 GiB |
| Candidatos SGD/MLP de T16 | 12 GiB | 8 GiB | 50 GiB |

Los perfiles están separados en [model.yaml](../configs/model.yaml): preparation_resources y resources. Se conservan cuatro hilos totales, un modelo a la vez y meses secuenciales. El perfil nuevo no autoriza reducir filas ni aumentar límites al fallar. Se aplica también a la preparación real mediante callbacks entre bloques de validación/features y al particionado.

El baseline supervisa recursos durante lectura/inserción y mediante un callback de progreso SQLite durante ordenación/consulta. Aplica el presupuesto de dos horas por candidato; al excederlo interrumpe y conserva reporte de fallo. La supervisión RSS/disco es cooperativa; no se presenta como límite duro del SO/contenedor. Docker todavía no está verificado.

## Artefactos y ejecución

El directorio final contiene model.json, validation_predictions.parquet y baseline_manifest.json, este último publicado al final. El modelo JSON guarda la constante, las filas train y el SHA de sus etiquetas. El reporte registra configuración, hash del split, método exacto, recursos, número de predicciones y métricas de validación. No se carga pickle arbitrario ni se instalan dependencias nuevas.

BASELINE_REAL describe un resultado académico completado. approved_for_serving=false y model_registered=false: no existe promoción, champion ni registro MLflow en T15. La autorización de esta ejecución proviene de la solicitud expresa del usuario y de la política baseline aprobada; el false de approved_for_training en T14 expresa ausencia de aprobación automática del dataset, no una promoción implícita.

```powershell
.\.venv\Scripts\python.exe -m src.training.baseline --help
.\.venv\Scripts\python.exe -m src.training.baseline --split-batch RUTA_LOTE_T14
```

--test-only exige particiones sintéticas y aísla artefactos/reportes. Reejecutar crea un intento nuevo sin reemplazar el anterior. Los JSON generados, SQLite y Parquet reales quedan excluidos de Git. El catálogo real de versiones explícitas se guarda como configs/real-feature-batches.local.json, también excluido por contener rutas locales.

## Verificación y estado de ejecución

Las pruebas cubren mediana global par/impar/repetidos, independencia del orden/tamaño de bloque, rechazo de etiquetas inválidas, liberación de SQLite, interrupción durante ordenación nativa, integridad/ámbito de particiones y CLI. Un caso independiente usa train=10, validation=30 y test=100: aprende 10, obtiene MAE/RMSE=20 en validación y prohíbe abrir test/replay.

La preparación real utiliza los 24 archivos locales autorizados, sin descargas y conservando LOCAL_UNVERIFIED con fuente/fecha nulas. Reutiliza la validación de enero y genera versiones nuevas explícitas para los restantes. Los umbrales D-04 y los periodos D-01 no se modifican. Una calidad FAIL detiene el flujo para revisión.

Estado histórico anterior a separar el ajuste: .cache/t15/preparation-state.json, FAILED_OR_INTERRUPTED por rechazo de calidad. 14 meses completos, marzo sin publicar. No existen split-result.json/baseline-result.json de esta ejecución ni métricas reales de baseline. Todos los procesos terminaron. **333 pruebas en desarrollo y wheel aprobadas**, 21 imports aislados, Ruff y pip check correctos. [Preparación auditada](../reports/quality/t14_t15_preparation.md).

## Ajuste independiente aprobado posteriormente

La aprobación expresa permite ejecutar [baseline_fit.py](../src/training/baseline_fit.py) sin esperar T14 completa. No es una excepción de calidad ni una modificación de periodos. El catálogo REAL debe contener exactamente los doce meses de train, con versiones explícitas de features/validated aprobadas y hashes íntegros. Se rechazan entradas de 2025 antes de abrirlas, meses repetidos, cobertura parcial y salidas que se solapen con fuentes. TEST_ONLY admite un subconjunto sintético limitado; no representa un ajuste real.

El lector causal compartido con T14 verifica alineación, identidad y cobertura de filas, target frente a eventos UTC, mes y calendario. Aparta etiquetas con llegada igual o posterior al corte, sin trasladarlas a otra partición. Todas las restantes se incorporan a la mediana exacta en disco. Verifica de nuevo fuentes y catálogo antes de publicar; cualquier fallo deja reporte y ningún marcador completo.

El directorio data/processed/baseline_fits/id contiene model.json, train_target.parquet y fit_manifest.json publicado al final. Estado REAL: BASELINE_FIT_REAL_PENDING_VALIDATION; fit_complete=true y evaluation_status=PENDING_VALIDATION. T14/T15 completas=false, métricas de validación=null, sin acceso a validation/test/replay, registro ni serving. El Parquet es una copia auditada de etiquetas usadas para el ajuste, no una partición T14 completa. El modelo provisional tampoco es un champion.

El manifiesto conserva fuentes y sus verificaciones, configuración, conteos/exclusiones, ejemplos, rangos, recursos y hashes. El hash lógico de etiquetas usa bytes IEEE754 float64 little-endian concatenados y es independiente de bloques; el hash físico del Parquet puede variar por row groups. Orden: mes ascendente y posición de origen. El índice SQLite temporal se elimina al terminar. RSS/disco se supervisan entre bloques y el plazo de dos horas también durante el ordenamiento SQLite.

```powershell
.\.venv\Scripts\python.exe -m src.training.baseline_fit --help
.\.venv\Scripts\python.exe -m src.training.baseline_fit --inputs configs/train-feature-batches.local.json
```

Actualización de interfaz autorizada: [baseline_evaluate.py](../src/training/baseline_evaluate.py) verifica y evalúa el ajuste congelado sin modificarlo. Exige toda validation aprobada, conserva test/replay sellados y completa técnicamente T15 sin declarar T14 integral completa. [Excepción y contrato](t15-march-exception.md), [resultados](../reports/quality/t15_baseline_validation.md). El flujo original que consume una T14 completa sigue disponible por separado.

## Resultado del ajuste independiente

Ajuste exacto train 2024 completo y auditado: 41.119.495 etiquetas, mediana 12,983333 minutos; 561 filas apartadas por corte de etiqueta entre 41.120.056 elegibles DQ. Evaluación y cierre de T14/T15 pendientes de marzo 2025; D-04 permanece congelada. [Reporte completo](../reports/quality/t15_train_fit.md). 356 pruebas en ambos entornos, 22 imports; orden estadístico y todas las etiquetas contrastados independientemente. Los estados anteriores de ejecución pendiente describen sus etapas históricas. La evaluación no se había ejecutado en esa entrega; la sección siguiente recoge su ejecución posterior.

## Evaluación posterior y cierre técnico

T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [Resultados y auditoría](../reports/quality/t15_baseline_validation.md). Marzo aceptado por excepción humana solo para su hash/reporte; FAIL original y exclusiones conservados, sin cambiar D-04 global. T14 integral sigue pendiente; test/replay sellados, T16 no ejecutada y sin registro/promoción. Las referencias anteriores a evaluación pendiente describen el ajuste original, cuyo artefacto permanece inmutable. 380 pruebas en ambos entornos; revisión humana independiente.
