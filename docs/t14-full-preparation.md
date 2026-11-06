# T14: preparación integral y auditoría de los 24 meses

Fecha inicial: 2026-11-03; cierre técnico: 2026-11-05, America/Costa_Rica. **T14 CIERRE TÉCNICO PASS: 24 meses registrados, validados/aceptados y con features; 89.892.322 raw, 627.221 exclusiones de calidad y 2.952 por disponibilidad de etiqueta. Particiones auditadas: train 41.119.495; validation 11.163.264; test 12.712.466; replay 24.266.924. Todas las identidades y valores publicados coinciden con las fuentes; train/validation coinciden con T15 congelada. D-04, 24 raw y diez FAIL originales intactos. Revisión humana de resultados independiente del cierre técnico. T16/T17 aprobadas para continuar; todavía sin entrenamiento ni métricas nuevas.** [Evidencia integral](../reports/quality/t14_completion.md).

Resultado inicial del 2026-11-03: 24 archivos registrados y 15 versiones previas con features aceptadas. Los nueve meses abril–diciembre de 2025 incumplieron D-04 y conservaron su FAIL, sin publicar features ni particionado integral. El [reporte histórico por mes](../reports/quality/t14_full_preparation.md) identifica reglas, conteos y hashes. El 2026-11-05 se aprobaron nueve aceptaciones excepcionales individuales; la ejecución actual verifica nuevamente las fuentes y aplica únicamente esos permisos. No se declara cierre antes de completar y auditar las cuatro particiones.

## Ejecución autorizada

Continuación solicitada el 2026-11-05: el usuario aprobó las nueve excepciones individuales, ya aplicadas con todas las exclusiones y FAIL originales conservados. La ejecución real y auditoría de T14 terminaron. Cualquier incumplimiento nuevo requiere otra aprobación. La orden de continuar con T16/T17 y sus parámetros/segmentos ya está aprobada; sus resultados técnicos aún no se han producido.

Se reutilizan doce versiones train de 2024 y tres de validation 2025 ya identificadas y verificadas, incluida la aceptación excepcional exacta de marzo. Los nueve archivos restantes se registran explícitamente contra sus hashes autorizados, conservando LOCAL_UNVERIFIED y fuente/fecha de descarga nulas. No hay descarga ni reemplazo de originales.

Cada mes se valida completo por bloques con D-04 congelada. La primera ejecución no pasó excepciones nuevas y produjo los nueve rechazos originales. La continuación pasa solo la autorización individual ya aprobada: exige igualdad de mes/hash/configuración, reporte original, conjunto de fallos, conteos y normalizaciones; conserva los FAIL medidos y todas las exclusiones. Un rechazo adicional se presenta al usuario y no genera features ni entra al catálogo completo mientras no se autorice. Solo se generará el catálogo final cuando estén aceptados los 24 meses. No se eligen versiones por glob ni por fecha de modificación.

Las ejecuciones guardan checkpoints y versiones para evitar repetir trabajo; el historial anterior de rechazos no se reescribe. Control histórico: .cache/t14-full/state.json. Continuación aprobada: .cache/t14-approved/state.json y execution.log. El catálogo final será configs/real-feature-batches.local.json, excluido de Git.

## Criterios de aceptación

- Integridad de los 24 raw: tamaño, SHA-256, manifiesto y autorización de año/mes consistentes; procedencia desconocida conservada.
- Calidad/aceptación y features verificables para cada una de las 24 versiones. Cualquier excepción debe estar aprobada para ese mes/hash/reporte y conservar sus exclusiones y FAIL medido.
- Cuatro particiones según D-01, con features, target y contexto separados/alineados. Eventos de llegada estrictamente anteriores a cada corte; exclusiones con conteos y motivos. No split aleatorio, submuestreo ni concatenación del histórico completo en RAM.
- Auditoría independiente de todas las identidades y valores publicados frente a las fuentes filtradas por corte, hashes, conteos exhaustivos y ausencia de solapamiento temporal. Contraste de train/validation con los artefactos congelados de T15.
- Marcador split_manifest.json publicado al final, sin alterar intentos anteriores; recursos supervisados y temporales/locks propios limpios. Resultados y límites documentados antes de afirmar cierre técnico.

## Recursos y alcance

Perfil aprobado de preparación: preflight 4 GiB de RAM libre y 50 GiB de disco, RSS supervisado ≤2 GiB, cuatro hilos y meses secuenciales. Se usan [ingesta](../src/ingestion/download.py), [validación](../src/validation/run.py), [features](../src/features/artifacts.py) y [particionado](../src/training/split.py). La continuación amplía únicamente el [lector de excepciones](../src/validation/exceptions.py) y sus pruebas. El código actual se contrastó con un nuevo wheel: 391 pruebas aprobadas en ambos entornos, Ruff y pip check correctos. Sin dependencias nuevas. Las 380 pruebas corresponden a la ejecución anterior.

Leer test/replay para calidad, preparación y auditoría está autorizado en esta tarea; no se utilizan para calcular métricas predictivas, seleccionar parámetros o reajustar el baseline. T15 permanece congelada y T16 no se inicia. El replay sigue siendo retrospectivo por evento, no prueba de disponibilidad histórica de publicación TLC. No hay promoción. La publicación posterior autorizada se documenta en el [historial de commits](commit-history.md).
