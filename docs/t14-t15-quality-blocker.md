# T14/T15: decisión requerida por calidad de marzo de 2025

Fecha: 2026-11-03, America/Costa_Rica. **Historial del rechazo original, conservado íntegro.** El usuario autorizó después una excepción exacta para marzo; la revalidación acepta el lote conservando FAIL medido y excluyendo filas inválidas. T15 terminó técnicamente; T14 integral sigue pendiente. [Excepción](t15-march-exception.md), [resultado auditado](../reports/quality/t15_baseline_validation.md). Las secciones siguientes describen la secuencia histórica.

## Evidencia del rechazo

El escaneo completo de marzo de 2025 revisó **4.145.257 filas**. La regla `rows.duration_nonpositive` detectó **22.280 filas**, **0,537482 %**, frente al máximo aprobado de **0,50 %**. Es el único control con FAIL. El exceso es de 0,037482 puntos porcentuales; la comparación usa la tasa completa sin redondearla.

El reporte local es `reports/quality/2025/03/077a819319564b4eb4913a4e389da48a.json`. El intento terminó REJECTED, con `data_quality_approved=false` y sin publicar un dataset validated. Los registros potencialmente elegibles no constituyen un lote aprobado.

Una segunda lectura acotada en memoria de las columnas temporales y VendorID, sobre ese mismo archivo ya inspeccionado, reprodujo exactamente el conteo: **22.199 duraciones cero y 81 negativas**. De las 22.280, **21.481** tienen VendorID=7. No se excluyó a ese proveedor ni se usó como predictor. Esta concentración es un indicio para investigar el archivo; no demuestra su causa ni justifica aceptar el lote automáticamente. La regla DST no detectó horarios ambiguos/inexistentes en este lote.

Las exclusiones por la unión de reglas serían **23.886 filas (0,576225 %)**; **4.121.371** superarían las reglas por fila. Que la unión quede por debajo del 1 % no anula el fallo del límite específico de duración no positiva. Las filas de duración cero o negativa seguirán excluidas bajo cualquiera de las opciones.

## Estado conservado

- Los doce meses de 2024 y enero–febrero de 2025 completaron calidad y features REAL: **14 meses**. Sus versiones se conservan.
- Marzo de 2025 tiene manifiesto local y reporte FAIL, sin validated/features publicados por este intento. Abril–diciembre de 2025 no se incorporaron durante esta ejecución.
- No hay particiones reales T14 ni baseline real T15 de esta ejecución. No se redujo la validación a dos meses, no se cambió el split y no se entrenaron candidatos T16.
- El código pasó **333 pruebas** en desarrollo y **333 desde el wheel instalado**, Ruff y comprobación de dependencias en ambos entornos. Estas pruebas no sustituyen la aceptación de datos reales.
- Los procesos de preparación y sus esperas terminaron. Se liberó mediante su propietario la reserva temporal de abril destinada a mantenimiento; no queda un trabajo avanzando en segundo plano.

## Opciones para decidir

1. **Mantener D-04 congelada y revisar la procedencia o una nueva versión de marzo (recomendado).** Conservar el rechazo y contrastar el archivo con la fuente. No reemplazar el original: cualquier versión nueva tendrá hash, autorización y validación propios. T14/T15 quedan pendientes mientras el mes no sea aceptable.
2. **Autorizar una excepción académica únicamente para este mes/hash y este reporte.** Aceptar expresamente el exceso observado de duración no positiva, conservar el FAIL original y todas las exclusiones por fila, y registrar un override separado y auditable. No cambia tolerancias globales ni autoriza excepciones en otros meses. Requiere definir y probar ese mecanismo antes de incorporarlo; el sistema actual no permite saltarse el gate.
3. **Solicitar una nueva propuesta D-04 v2.** Revisar su fundamento y efectos antes de aprobar límites nuevos. No modificar retrospectivamente la política v1 ni presentar los nuevos límites como independientes de los datos de validación ya vistos. Una aprobación posterior exigiría revisar fingerprints y revalidar los lotes afectados.

No se recomienda elevar automáticamente el umbral para conseguir un PASS, borrar viajes antes de medir su tasa o cambiar los periodos de validación. No se aplicó ninguna de esas acciones. La autorización previa de uso académico LOCAL_UNVERIFIED acredita permiso de uso, no una excepción de calidad.

## Alcance de la consulta inicial

Al presentar esta propuesta se solicitó una elección explícita; la respuesta posterior y su resultado se registran a continuación. El baseline de mediana global y el perfil de preparación de 4 GiB libres/2 GiB RSS ya están aprobados y no requieren volver a autorizarse. El presupuesto de candidatos T16 permanece en 12 GiB libres/8 GiB RSS. [Contrato T14](t14-temporal-splits.md), [contrato T15](t15-baseline.md) y [política congelada D-04](d04-quality-proposal.md).

## Decisión del usuario y contraste de la fuente

El usuario eligió **mantener D-04 y revisar la fuente o una nueva versión de marzo**. Las opciones de excepción y nueva política no están aprobadas. Se mantiene el rechazo y no se reanuda el flujo con este lote.

La [página oficial TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) enlaza el [Parquet de marzo de 2025](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2025-03.parquet). Se consultaron exclusivamente sus cabeceras HTTP, sin descargar el dataset:

| Comprobación | Resultado |
|---|---|
| HTTP | 200 |
| Tamaño remoto y local | 69.964.745 bytes, iguales |
| Last-Modified remoto | 21 de mayo de 2025, 15:29:16 GMT |
| ETag remoto | `5a7b279b75549fe3c5270e995a5b8c02-14` |
| ETag multipart calculado localmente | Coincide, 14 partes de 5 MiB salvo la última |
| SHA-256 local conservado | `20c4b77cce457b7cfdae77c5069ca7dc91c167f876a41467f4502ab69487a186` |

El cálculo sigue la composición de MD5 de partes descrita por [Amazon S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html). El ETag multipart no es el MD5 del archivo completo ni un SHA-256 remoto. La coincidencia de tamaño y ETag respalda que el local corresponde al objeto actualmente publicado; **no se encontró indicio de una versión corregida distinta en esa URL**. No se acreditó la descarga histórica ni se modificó el manifiesto LOCAL_UNVERIFIED: fuente y fecha originales siguen nulas. Evidencia local: `.cache/t15/march-source-comparison.json` y `march-source-headers.txt`.

El [diccionario oficial](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf) identifica VendorID=7 como Helix: es un código documentado y ya admitido por la configuración. La concentración de duraciones no positivas no se explica por un identificador desconocido. La [TLC advierte que no garantiza la exactitud de estos datos](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). No se ha establecido la causa de las duraciones cero/negativas.

Con la política y los periodos conservados, no hay una vía aprobada para cerrar T14/T15 usando este archivo rechazado. Para reanudar la evaluación completa se necesita una versión de marzo con trazabilidad/autorización propias que supere D-04; si no existe, cualquier excepción o revisión de política exige una nueva decisión explícita. No se descargó un duplicado ni se esperó indefinidamente una actualización de la fuente.

## Continuación autorizada: ajuste separado de train

Después el usuario aprobó separar el ajuste exacto de train 2024 de la evaluación, respetando corte de etiquetas y calidad. [Contrato actualizado T15](t15-baseline.md). Esa fase puede avanzar con sus doce meses ya aprobados, sin consumir marzo ni ningún archivo de 2025. No elimina el rechazo, no concede excepción y no cierra T14/T15. Las afirmaciones anteriores de bloqueo del ajuste describen el contrato previo a esta nueva aprobación; el bloqueo de evaluación/cierre permanece vigente.

## Resultado posterior autorizado

Ajuste exacto train 2024 completo y auditado: 41.119.495 etiquetas, mediana 12,983333 minutos; 561 filas apartadas por corte de etiqueta entre 41.120.056 elegibles DQ. Evaluación y cierre de T14/T15 pendientes de marzo 2025; D-04 permanece congelada. [Ajuste provisional auditado](../reports/quality/t15_train_fit.md). La ausencia de una versión aceptable de marzo sigue bloqueando evaluación y cierre; no impide conservar este ajuste independiente aprobado. No hay excepción de calidad.

## Excepción posterior autorizada y resultado

El usuario solicitó hacer una excepción únicamente para este mes y cerrar T15. La [autorización](../configs/quality-exception-2025-03.json) no altera el FAIL original ni D-04 global. T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [Reporte](../reports/quality/t15_baseline_validation.md). Sustituye el estado previo sin excepción; no autoriza otros meses/hashes/fallos.
