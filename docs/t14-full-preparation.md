# T14: preparación integral y auditoría de los 24 meses

Fecha: 2026-11-03, America/Costa_Rica. El usuario autorizó preparar abril–diciembre de 2025 —registro, validación y features—, particionar los 24 meses y auditar cortes temporales, cobertura e integridad. **Cualquier excepción nueva requiere aprobación. Registro y validación completos; T14 pendiente por nueve rechazos.**

Resultado: 24 archivos registrados y 15 versiones previas con features aceptadas. Los nueve meses abril–diciembre de 2025 incumplen D-04 y conservan su FAIL; no se publicaron sus features ni el particionado integral. El [reporte por mes](../reports/quality/t14_full_preparation.md) identifica reglas, conteos y hashes. No se aplicó ninguna excepción nueva. El catálogo final, el particionado y su auditoría exhaustiva quedan pendientes de resolver esos rechazos con aprobación humana o fuentes distintas aceptables.

## Ejecución autorizada

Se reutilizan doce versiones train de 2024 y tres de validation 2025 ya identificadas y verificadas, incluida la aceptación excepcional exacta de marzo. Los nueve archivos restantes se registran explícitamente contra sus hashes autorizados, conservando LOCAL_UNVERIFIED y fuente/fecha de descarga nulas. No hay descarga ni reemplazo de originales.

Cada mes se valida completo por bloques con D-04 congelada, sin pasar ninguna excepción nueva. Un rechazo conserva su reporte y bloquea su consumo: no genera features ni entra al catálogo completo. Los demás meses independientes pueden seguir preparándose. Solo se generará el catálogo final cuando estén aceptados los 24 meses. No se eligen versiones por glob ni por fecha de modificación.

Las ejecuciones guardan checkpoints y versiones para evitar repetir trabajo; el historial anterior de rechazos no se reescribe. Control local: .cache/t14-full/state.json y execution.log. El catálogo final será configs/real-feature-batches.local.json, excluido de Git.

## Criterios de aceptación

- Integridad de los 24 raw: tamaño, SHA-256, manifiesto y autorización de año/mes consistentes; procedencia desconocida conservada.
- Calidad/aceptación y features verificables para cada una de las 24 versiones. Cualquier excepción debe estar aprobada para ese mes/hash/reporte y conservar sus exclusiones y FAIL medido.
- Cuatro particiones según D-01, con features, target y contexto separados/alineados. Eventos de llegada estrictamente anteriores a cada corte; exclusiones con conteos y motivos. No split aleatorio, submuestreo ni concatenación del histórico completo en RAM.
- Auditoría independiente de todas las identidades y valores publicados frente a las fuentes filtradas por corte, hashes, conteos exhaustivos y ausencia de solapamiento temporal. Contraste de train/validation con los artefactos congelados de T15.
- Marcador split_manifest.json publicado al final, sin alterar intentos anteriores; recursos supervisados y temporales/locks propios limpios. Resultados y límites documentados antes de afirmar cierre técnico.

## Recursos y alcance

Perfil aprobado de preparación: preflight 4 GiB de RAM libre y 50 GiB de disco, RSS supervisado ≤2 GiB, cuatro hilos y meses secuenciales. Se usan [ingesta](../src/ingestion/download.py), [validación](../src/validation/run.py), [features](../src/features/artifacts.py) y [particionado](../src/training/split.py) existentes. El código se contrastó con el wheel que pasó 380 pruebas en ambos entornos; no se cambia ni se instalan dependencias para esta ejecución.

Leer test/replay para calidad, preparación y auditoría está autorizado en esta tarea; no se utilizan para calcular métricas predictivas, seleccionar parámetros o reajustar el baseline. T15 permanece congelada y T16 no se inicia. El replay sigue siendo retrospectivo por evento, no prueba de disponibilidad histórica de publicación TLC. No hay promoción. La publicación posterior autorizada se documenta en el [historial de commits](commit-history.md).
