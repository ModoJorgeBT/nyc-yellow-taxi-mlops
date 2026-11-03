# T10/T11 — Pipeline de datos e integración offline

Fecha: 2026-11-03. El usuario solicitó continuar con T10 y T11 tras la entrega T08/T09. Se conserva el alcance aprobado: políticas numéricas exclusivamente sintéticas, configuración real PENDIENTE y ningún lote aprobado para entrenamiento. T10/T11 se verifican técnicamente con fixtures; el cierre operativo del flujo real depende de D-04/D-06 y revisión humana. No se implementa T12 ni se cierra G2 operativo.

## Implementación y dependencias

- [CLI y pipeline](../src/validation/run.py): lectura de Parquet por bloques, verificación del manifiesto de T07, staging, publicación sin reemplazo y reportes por intento.
- [Motor T09](../src/validation/rules.py): se añade un callback por bloque con elegibilidad provisional de cada fila. El pipeline utiliza exactamente esas decisiones; no replica reglas de calidad.
- [Política sintética compartida](../tests/fixtures/policies.py): mantiene los valores de las pruebas T08/T09, sin convertirlos en política de TLC.
- [Integración T11](../tests/integration/test_data_pipeline.py): descarga HTTP simulada → manifiesto → escaneo → resultado/rechazo, sin Internet ni datos reales.

Solo se utilizan biblioteca estándar y PyArrow ya instalado. No se modifica el lock ni se instalan dependencias nuevas. Se usa Arrow básico y slices para escribir tramos elegibles, sin importar PyArrow Compute, cuyo bloqueo de Windows quedó documentado en T08/T09.

## CLI y comportamiento actual

```powershell
.\.venv\Scripts\python.exe -m src.validation.run --help
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_data_pipeline.py --basetemp=.cache/pytest-t10-integration -o cache_dir=.cache/pytest-cache-t10-integration
```

El comando admite `--year`, `--month`, `--raw-dir`, `--validated-dir`, `--report-dir`, `--config`, `--scratch-dir`, `--batch-size` y `--test-only`. Rutas predeterminadas: data/raw, data/validated, reports/quality, configs/data.yaml y .cache/validation. Bloques de hasta 65.536 filas; ese límite de lectura no aprueba un presupuesto de entrenamiento ni de Docker. Se rechazan raíces superpuestas y enlaces/junctions dentro de las rutas de lote.

Modo normal: exige Parquet y manifiesto existentes, sin descargar ni registrar archivos. Verifica contenido/esquema/volumen y conserva un reporte de rechazo por política real pendiente, sin leer filas ni crear datasets. Los 24 archivos aportados siguen sin manifiestos: se rechazan sin incorporarlos automáticamente. No se ejecutó este CLI sobre esos archivos durante T10/T11.

Modo `--test-only`: exige configuración TEST_ONLY y metadata `fixture_origin=synthetic`. Un marcador sintético es una declaración para pruebas, no una prueba de procedencia. La integridad se verifica contra el manifiesto, pero no se certifica el origen remoto de los bytes. Se escanean todos los bloques y se publican exclusivamente resultados sintéticos aislados. Una configuración pendiente, un dato sin marcador, un gate crítico o un error bloquean.

Salida estándar: reporte JSON. Código 0 solamente cuando el flujo de prueba termina con PASS/WARN y publicación completa; código 1 para rechazo/error operativo, con mensaje en stderr; argparse usa código 2 para sintaxis inválida. Año/mes/tamaño de bloque o raíces inválidos se rechazan antes de escribir evidencia en rutas potencialmente inseguras. Si no se puede guardar el reporte, el error se propaga y el CLI devuelve fallo.

## Linaje y exhaustividad

Se comparte el bloqueo mensual de ingesta para evitar cambios de escritores cooperativos. Antes de leer filas se verifica el manifiesto completo con T07 y se calcula su SHA-256. El reporte conserva su contenido original, incluido LOCAL_UNVERIFIED, URL/fecha nulas y provenance_status; no se mejora esa procedencia por validar.

Después del escaneo se exige igualdad entre filas leídas y row_count del manifiesto, se vuelve a verificar raw y se compara el contenido/hash del manifiesto. El número escrito debe coincidir con el conteo elegible del mismo motor. Cada reporte registra versión del pipeline, configuración completa y su hash, esquema, identidad del intento, timestamps UTC e input/output. La configuración se carga una vez y se mantiene para toda la ejecución.

`lineage_status=VERIFIED_CONTENT` acredita consistencia de bytes y metadatos durante la validación; no acredita la fuente histórica ni disponibilidad temporal de etiquetas. `scan_scope` distingue NOT_STARTED, PREFLIGHT_ONLY, FULL_PARQUET_ATTEMPT y FULL_PARQUET. Un escaneo fallido conserva la indicación de intento y no se presenta como lectura completa. Si hay un error de ejecución, el linaje se marca FAILED_OR_INCOMPLETE de forma conservadora.

Los lotes históricos continúan pendientes de política DST; la evaluación sintética conserva la semántica naive_wall_clock de T09. No se crean features ni etiquetas persistidas, ni se decide disponibilidad de destino o cortes train/val/test.

## Publicación y recuperación

```text
data/validated/_test_only/YYYY/MM/<validation_id>/
    data.parquet
    validation.json

reports/quality/_test_only/YYYY/MM/<validation_id>.json
reports/quality/YYYY/MM/<validation_id>.json  # intentos normales rechazados
```

Cada intento usa un identificador nuevo; repetir validación conserva resultados previos. La ingesta sigue siendo idempotente y puede devolver SKIPPED sin red. El reporte y el Parquet usan el mismo validation_id y hashes para relacionar sus artefactos. Los resultados sintéticos llevan `execution_status=VALIDATED_TEST_ONLY`, `output.status=VALIDATED_TEST_ONLY`, metadata Parquet de ámbito de prueba y **approved_for_training=false**. Esta versión no publica datasets reales ni ofrece un estado de aprobación para entrenamiento.

Se escribe un Parquet provisional en un subdirectorio propio del mismo volumen de salida. Solo después de superar calidad, exhaustividad e integridad se publica mediante hard link sin reemplazo. `validation.json` se publica al final como marcador de resultado completo. Un Parquet sin ese marcador es una salida incompleta y nunca debe consumirse como validada. No basta encontrar un archivo mediante glob; consumidores futuros deberán verificar estado/ámbito, marcador, hashes y aprobación explícita.

No hay transacción atómica conjunta de todos los archivos. Si falla el marcador después del Parquet, se conserva ese archivo completo huérfano y el reporte indica FAIL/INCOMPLETE. Si falla únicamente la copia externa del reporte después de publicar ambos artefactos, el marcador interno conserva el resultado TEST_ONLY y el CLI falla porque no pudo completar su evidencia externa. Esos resultados siguen sin aprobación para entrenamiento. No se borran automáticamente resultados publicados para simular rollback.

Los temporales propios se cierran antes de limpiarlos en Windows, también ante fallos de lectura/escritura. Un cierre abrupto puede dejar temporales o lock para inspección; no se ofrece limpieza global ni reemplazo de lotes. No se protege contra modificaciones hostiles que ignoren bloqueos y manipulen rutas después de las verificaciones; la operación local presupone escritores cooperativos.

## Pruebas y límites

Suite observada: **162 pruebas aprobadas**, incluidas **33 de integración nuevas**. Casos T11: éxito y linaje de descarga simulada, exclusiones toleradas, duplicados conservados, gates críticos, esquema incompatible sin leer filas, política pendiente/modo normal, uso indebido de TEST_ONLY, falta de archivo/manifiesto, procedencia local desconocida, cambios previos/durante escaneo, lectura incompleta, interrupción de lectura, disco lleno simulado, fallo de marcador, carrera de publicación sin reemplazo, fallo del almacén de reportes, configuración ilegible, reejecución y SKIPPED, lock ajeno, argumentos/rutas inválidos y CLI aislado con éxito/fallo.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-t10-t11-full1 -o cache_dir=.cache/pytest-cache-t10-t11-full1
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

No se ejecutó descarga real, registro de los 24 Parquet, validación de sus filas ni entrenamiento. No se calibraron umbrales con 2025. Rendimiento, espacio temporal, fragmentación por grupos escritos y consumo sobre un mes completo siguen sin medir; requieren D-02 antes de ejecuciones reales. D-04/D-06 permanecen abiertas y la configuración real no cambia.

## Verificación final adicional

- Wheel construido sin red con `pip --isolated wheel --no-deps --no-build-isolation --no-index --wheel-dir .cache/t10-t11-dist .`, e instalado sin dependencias en el segundo entorno existente `.venv-verify`. Se verifica la importación aislada de doce módulos, incluido `src.validation.run`.
- Se copiaron tests/scripts/configs/pyproject a `.cache/t10-t11-checkout`, sin src ni data. Desde ese checkout, `.venv-verify` ejecutó **162 pruebas aprobadas**, incluidos CLI en subprocess aislados; `pip check` sin conflictos. No es una prueba de otro equipo ni de Docker.
- Ruff: `All checks passed!`, `27 files already formatted`. El lock y la configuración real data.yaml permanecen sin cambios.
- Se ejecutaron seis [casos de demostración](../reports/quality/pipeline_t10_t11.md), con artefactos únicamente bajo `.cache/t10-t11-demo`: dos publicaciones TEST_ONLY completas y cuatro rechazos sin dataset. Reportes completos en `.cache/t10-t11-examples.json`.
- Los 24 hashes raw coinciden con el inventario original. Cero manifiestos/eventos/temporales/locks nuevos en raw real y cero datasets en data/validated real; PDF intacto.
- Auditoría documental inicial: 19 Markdown, 116 enlaces locales válidos; se revisan nuevamente después de añadir esta evidencia. Se corrigieron acentos de los resúmenes generados, afectados por la codificación del pipe PowerShell, sin cambiar los resultados observados.
- Git continúa en main, sin commits, remotos ni índice; Parquet reales, salidas TEST_ONLY, reportes JSON y cachés siguen excluidos.

T10/T11 quedan para revisión humana en su alcance técnico offline. El cierre operativo y cualquier futura aprobación de datos reales requieren resolver D-04/D-06; G2 sigue abierto y T12 no se implementó.
