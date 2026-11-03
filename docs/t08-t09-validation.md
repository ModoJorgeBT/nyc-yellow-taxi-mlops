# T08/T09 — Esquema y motor de calidad

Fecha: 2026-11-03. El usuario aprobó expresamente el contrato T08, el motor T09 con políticas sintéticas y el bloqueo de aprobación de lotes reales. T08 está verificada técnicamente para revisión humana. T09 está verificada en su alcance de motor; su cierre operativo depende de D-04. Esta entrega no incluyó T10/T11; su continuación posterior se documenta en [pipeline T10/T11](t10-t11-data-pipeline.md). G2 operativo permanece abierto.

## Contrato T08 aprobado

[Configuración versionada](../configs/data.yaml) y [validador de esquema](../src/validation/schema.py):

- Cuatro campos obligatorios: `tpep_pickup_datetime`, `tpep_dropoff_datetime`, `PULocationID`, `DOLocationID`.
- Los otros campos históricos son opcionales; si están presentes se comprueba su tipo. Enteros con signo de 32/64 bits y `string`/`large_string` son compatibles. Timestamps exclusivamente `timestamp[us]` sin zona; importes y distancia conservan `double`. No hay casts implícitos.
- `Airport_fee` conserva su nombre. `cbd_congestion_fee` es conocido y opcional. Otras columnas producen WARN; no se eliminan ni se incorporan automáticamente a features. Nombres duplicados, esenciales ausentes o tipos incompatibles producen FAIL antes de leer filas.
- La nulabilidad declarada no exige ausencia de nulos: los valores se evalúan por separado en T09. Orden de columnas y metadatos de fixtures no alteran el conjunto exigido; el fingerprint conserva el orden y la nulabilidad observados, igual que T07.

`data.yaml` usa **sintaxis JSON, subconjunto de YAML**, para leerlo con biblioteca estándar. No admite comentarios YAML, anclas ni sintaxis YAML general. `load_config(Path(...))` recibe la ruta explícitamente; no depende de una ruta absoluta ni busca archivos silenciosamente desde el paquete instalado. No se añade PyYAML ni se modifica el lock. La configuración se versiona en el repositorio y se entrega explícitamente al motor; no viene incluida dentro del wheel.

## Reglas T09 y alcance del reporte

[Motor](../src/validation/rules.py): `evaluate_batches(schema, batches, year=..., month=..., config=..., scratch_dir=...)` recibe un iterable completo de `RecordBatch` y devuelve un diccionario serializable a JSON. No accede a la red, abre raw, escribe datos validados ni implementa un CLI. Cada regla incluye estado PASS/WARN/FAIL, observación, umbral, severidad y evidencia. Se incluyen hashes de configuración/esquema, versiones de política/catálogo y hasta cinco índices globales por anomalía, desde cero.

| Control | Semántica implementada |
|---|---|
| Timestamps | Cuenta filas con pickup o dropoff nulo; no produce una duración ficticia. |
| Duración | Diferencia exacta de microsegundos almacenados; cero/negativa inválida. Máximo configurable o deshabilitación explícita, exclusivamente en pruebas por ahora. |
| Mes | Pickup dentro de `[inicio_mes, inicio_mes_siguiente)`; dropoff puede cruzar mes/año. Febrero bisiesto probado. |
| Zonas | Nulos por fila; pertenencia a catálogo explícito versionado. Sin catálogo se informa no evaluado, no cero anomalías. No hay rango/códigos especiales implícitos. |
| Pasajeros | Ausencia de columna o nulo se mide aparte; negativos y valores fuera de rango se cuentan por separado. La exclusión requiere una acción explícita. |
| Categorías | Conjuntos explícitos por columna opcional presente; medir o excluir según política. Sin conjuntos, no evaluado. |
| Repeticiones | Todas las columnas suministradas, incluidas adicionales; cuenta repeticiones más allá de la primera, también entre bloques. Mide sin eliminar. No equivale a identidad de viaje. |
| Volumen | Mínimo total y mínimo elegible por separado; lote vacío no supera el perfil de prueba. |
| Tasas | Denominador: todas las filas escaneadas; se rechaza al superar el máximo, igualdad tolerada. Anomalía dentro del máximo produce WARN. |
| Exclusiones | Unión de razones invalidantes: una fila con varias anomalías se cuenta una sola vez. La tasa de inválidos también tiene gate propio. |

`eligible_rows` y `excluded_rows` son conteos propuestos, sin selección/escritura de datos. `eligibility_complete=false` advierte controles de fila pendientes; esos conteos no acreditan una población final válida. Un fallo estructural o un cambio de esquema durante la lectura deja los conteos elegibles/excluidos en null. El esquema debe ser consistente entre bloques, incluyendo metadata. Si el iterable falla se propaga la excepción sin retornar aprobación y se cierra el temporal.

La suma de conteos por anomalía puede superar el número de filas. Duplicados y pasajeros/categorías en modo `measure_only` pueden rechazar el lote por tasa, pero no se excluyen automáticamente del conteo elegible. Los pasajeros ausentes se permiten a nivel de fila; su tasa sigue siendo observable y configurable. Validar un campo histórico no autoriza su uso al inicio del viaje.

## Bloqueo de datos reales y pendientes

La configuración real queda `PENDIENTE`, con límites y catálogo en null. `policy.ready=FAIL` impide superar calidad. Un campo no evaluado o una tasa sin definir no se presenta como PASS. Valores mal formados (tasas negativas, NaN, bool como entero, rangos invertidos) fallan explícitamente.

Solo existe adicionalmente el estado `TEST_ONLY`: requiere todos los parámetros y metadata `fixture_origin=synthetic`. Sirve para comprobar PASS/WARN/FAIL sobre fixtures; no es una credencial de seguridad ni una aprobación de procedencia. No se admite `status=APPROVED` en esta versión.

`quality_passed` solo puede ser true para ese perfil sintético completo sin FAIL. **`approved_for_training` siempre es false**; `lineage_status=NOT_CHECKED_T10` informa que el motor directo no ha verificado manifiesto, hash del contenido ni exhaustividad del archivo. `scan.complete` solo acredita que terminó el iterable entregado, no que este contuviera todas las filas del Parquet. La integración posterior [T10](t10-t11-data-pipeline.md) añade esas comprobaciones y selección/escritura segura únicamente de fixtures aisladas, conservando el bloqueo de datos reales.

Pendientes para operar con datos reales: D-04 (mínimos de volumen, tolerancias por regla y global, máximo de duración, catálogo y política de códigos especiales, rango/acción de pasajeros, categorías y acción sobre duplicados); D-06 (semántica histórica/DST). La resta actual es de reloj local sin zona y no afirma tiempo transcurrido UTC. No se calibraron límites con 2025 ni con la muestra sesgada de T05. Las cifras de las [pruebas](../tests/unit/test_validation.py) se escogieron únicamente para fixtures de doce filas.

## Recursos y compatibilidad local

El motor retiene un bloque Python a la vez y ejemplos acotados. El tamaño de bloque lo controla el llamador. El índice de repeticiones exactas usa SQLite temporal de biblioteca estándar, con claves completas sin riesgo de colisión de hash y caché configurada a aproximadamente 2 MiB. Esta estructura es auxiliar de pruebas/calidad; no decide la persistencia MLflow de D-07. Crece en disco con las filas distintas; no constituye un presupuesto de disco aprobado. Con cierre normal/excepción se elimina solo el subdirectorio propio; un cierre abrupto puede dejar temporales para inspección.

No se midieron rendimiento ni espacio temporal sobre un mes completo. Antes de ejecutar lotes reales se debe medir ese coste y aprobar recursos con D-02. No se concatenaron los 24 meses en RAM.

La primera prueba encontró un bloqueo de Windows Application Control al importar PyArrow Compute; persistió al ejecutar fuera del sandbox. Se retiró esa dependencia de módulo y se utilizaron vistas de enteros de Arrow básico y límites de mes de biblioteca estándar. No se cambió la política del sistema ni se añadieron paquetes. La suite actual pasa dentro del entorno normal; esa prueba no certifica Docker/Linux.

## Evidencia ejecutada

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-t08-t09-complete1 -o cache_dir=.cache/pytest-cache-t08-t09-complete1
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Resultado de desarrollo: **129 pruebas aprobadas** (69 anteriores y 60 nuevas), lint sin errores y dependencias consistentes. Los casos nuevos cubren esquemas 2024/2025 compatibles, esenciales ausentes/tipos incompatibles, opcionales, columnas nuevas, límites de mes/año/bisiesto, máximos y timestamps extremos sin overflow, duplicados entre bloques, nulos/NaN, políticas/catálogos explícitos, unión de exclusiones, gates críticos, volumen vacío/insuficiente, interrupción, limpieza y bloqueo de configuración pendiente/perfil de prueba sobre datos sin marcar.

Verificación final adicional, ejecutada sin red ni resolución de dependencias:

- Wheel construido con `pip --isolated wheel --no-deps --no-build-isolation --no-index --wheel-dir .cache/t08-t09-dist .` e instalado con `--no-index --no-deps --force-reinstall` en el segundo entorno existente `.venv-verify`. No se instalaron paquetes adicionales. El wheel contiene schema/rules; la prueba aislada comprueba once módulos importables.
- Se copiaron tests/scripts/configs/pyproject a `.cache/t08-t09-checkout`, sin `src` ni `data`; desde allí `.venv-verify` ejecutó **129 pruebas aprobadas**, usando el paquete instalado. El mismo resultado se repitió en desarrollo con `--basetemp=.cache/pytest-t08-t09-final -o cache_dir=.cache/pytest-cache-t08-t09-final`. Es una verificación local, no otro equipo ni Docker.
- Ruff: `All checks passed!` y `24 files already formatted`. `pip check`: sin dependencias rotas.
- Trece [reportes de demostración](../reports/quality/fixtures_t08_t09.md) ejecutados con fixtures: PASS, WARN tolerado, FAIL estructural/crítico, configuración pendiente y datos sin marcador sintético. JSON completo en `.cache/t08-t09-examples.json`, excluido de Git. Ninguno concede aprobación para entrenamiento.
- Los 24 esquemas reales pasan T08 leyendo solo footers; SHA-256 de todos los archivos coincide con el inventario anterior a su organización. Cero manifiestos/eventos/locks/temporales nuevos en raw, cero datasets en validated; PDF intacto. No se ejecutaron reglas de filas sobre los Parquet reales.
- Auditoría documental inicial: 17 Markdown, 100 enlaces locales válidos; revisión final de referencias tras añadir estas evidencias. Git sigue en main, sin commits, remotos ni archivos en índice; datos reales/cachés excluidos.

La revisión humana final de T08 y del alcance técnico T09 sigue pendiente. No se cierran D-04, D-06 ni G2 por pasar esta suite.
