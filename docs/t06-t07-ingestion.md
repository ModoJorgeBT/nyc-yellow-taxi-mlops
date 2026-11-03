# T06/T07 — Descarga, manifiestos e idempotencia

Fecha: 2026-11-03, America/Costa_Rica. Estado técnico: VERIFICADO; revisión humana pendiente. Alcance autorizado: T06/T07 con pruebas de red simulada. El usuario aprobó registro local explícito con procedencia pendiente, sin aplicarlo todavía a los 24 Parquet reales. T08/posteriores y descargas masivas no se ejecutan.

## Uso y estados

Desde la raíz, con el entorno T03 instalado:

```powershell
.\.venv\Scripts\python.exe -m src.ingestion.download --help
```

Ejemplo operativo de descarga para un lote ausente (no ejecutado contra TLC durante esta tarea):

```powershell
.\.venv\Scripts\python.exe -m src.ingestion.download --year 2025 --month 01 --timeout 30 --retries 2
```

Ejemplo de registro explícito de un archivo ya ubicado en raw/YYYY/MM (implementado y probado con fixtures; no aplicado a los archivos reales):

```powershell
.\.venv\Scripts\python.exe -m src.ingestion.download --year 2025 --month 01 --register-local
```

`--raw-dir` cambia la raíz local; `--expected-sha256` permite exigir un hash de referencia de 64 dígitos hexadecimales. Parámetros validados antes de efectos sobre disco: año entero 2009…9999, mes 1…12, timeout positivo/finito y reintentos 0…5. El timeout aplica a operaciones de red bloqueantes, no es una duración máxima global para todo el archivo.

| Situación | Resultado |
|---|---|
| No existen datos ni manifiesto | Descarga en streaming, inspección Parquet y publicación del par de archivos. |
| Datos y manifiesto consistentes | SKIPPED, sin conexión remota; manifiesto original conservado. |
| Archivo sin manifiesto, comando normal | Conflicto explícito; no descarga ni reemplaza. |
| Archivo sin manifiesto, registro explícito | REGISTERED_LOCAL_UNVERIFIED; se conservan bytes y se registra procedencia pendiente. |
| Manifiesto sin datos, corrupto o contenido divergente | Conflicto, sin reparación ni sobrescritura automática. |
| Lote bloqueado por otra operación | Conflicto; no se elimina el bloqueo ajeno. |

La salida estándar es JSON con estado de ejecución, estado persistente, procedencia, periodo, hash y rutas locales. Los errores del CLI salen por stderr con código distinto de cero. `SKIPPED` es una verificación local, no confirma que el proveedor remoto conserve la misma publicación.

## Archivos y procedencia

Por cada lote se usan:

```text
data/raw/YYYY/MM/
    yellow_tripdata_YYYY-MM.parquet
    manifest.json
    ingestion-events.jsonl
```

Se crea `.ingestion.lock` durante la operación y temporales `.part` propios. El manifiesto versión 1 contiene URL de origen/esperada, año, mes, nombre, fecha de descarga/registro UTC, SHA-256, bytes, filas del footer, esquema y huella, versión de pipeline, origen, procedencia y estado.

Para descarga por pipeline: `origin=download`, `status=DOWNLOADED`, `provenance_status=RECORDED_DOWNLOAD`, URL y fecha de descarga registradas. Esto no acredita Quality Gates, exactitud de los datos ni comparación con un checksum oficial independiente. La opción de hash esperado se aplica antes de publicación y también al verificar un lote existente.

Para registro local: `origin=local`, `status=LOCAL_UNVERIFIED`, `provenance_status=UNVERIFIED_LOCAL`; `source_url` y `downloaded_at_utc` son nulos. `expected_source_url` identifica solo dónde se esperaría el archivo; `recorded_at_utc` registra la acción actual. La reejecución puede ser SKIPPED, pero conserva LOCAL_UNVERIFIED y no inventa el historial. La decisión sobre procedencia suficiente para T08/T09 sigue pendiente.

La huella de esquema se calcula sobre nombres, tipos y nulabilidad con JSON canónico, sin metadata personalizada. Los eventos JSONL guardan fecha UTC y estado: DOWNLOADED, REGISTERED_LOCAL_UNVERIFIED, SKIPPED o FAILED. Las carpetas raw y estos artefactos locales están excluidos de Git; no se escriben muestras ni datos aprobados en validated/processed.

## Descarga y publicación

Implementación: [download.py](../src/ingestion/download.py), [manifest.py](../src/ingestion/manifest.py). Usa `urllib` de biblioteca estándar y PyArrow ya aprobado; no hay nuevas dependencias ni cambios en el lock.

La URL canónica sigue los archivos públicos enlazados por [TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Se exige HTTP 200, se lee por bloques de 1 MiB y se comprueba Content-Length si existe. Los errores de red/transporte y HTTP 408/429/500/502/503/504 tienen reintentos limitados con espera; un 404 falla sin reintentar porque el mes puede no estar publicado. Se consulta el footer para legibilidad, esquema y volumen; no se decodifican todas las páginas ni se validan esquema de negocio o calidad de filas.

La publicación usa hard links locales en el mismo volumen para fallar si el destino ya existe. Requiere un sistema de archivos que los soporte; no se degrada a una sobrescritura cuando falla esa operación. Fuentes técnicas: [urllib.request](https://docs.python.org/3.14/library/urllib.request.html) y [os.link](https://docs.python.org/3.14/library/os.html#os.link).

Cada archivo se publica de forma individual, no como una transacción atómica de datos más JSON. Si falla la publicación del manifiesto después de publicar datos, se conserva el Parquet completo huérfano y se falla explícitamente; la siguiente ejecución normal bloquea ese estado. Esta recuperación no exige ni autoriza borrar datos. Ante cierre abrupto del proceso puede quedar un lock/temporal: inspeccionarlo antes de cualquier limpieza manual. No hay opción `--replace` ni borrado automático de archivos divergentes.

## Pruebas y evidencia

[Pruebas de ingesta](../tests/unit/test_ingestion.py): red simulada y Parquet sintético, sin leer raw real ni necesitar Internet. Casos: descarga y metadata, segunda ejecución sin red, 404, timeout y error de servidor con reintentos, interrupción de lectura, Content-Length inválido/truncado/ausente, Parquet ilegible, hash esperado, registro local, datos modificados, JSON inválido, campos manipulados, manifiesto sin datos, lock ajeno, carrera de publicación, fallo del segundo archivo, parámetros inválidos, CLI --help y registro/skip desde subprocess aislado.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-t06-t07-expanded -o cache_dir=.cache/pytest-cache-t06-t07-expanded
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Resultado observado inicial: **69 pruebas aprobadas** en la suite total (32 previas y 37 de ingesta), lint sin errores. La prueba de Parquet ilegible encontró un handle abierto al fallar el constructor de PyArrow en Windows; se corrigió abriendo el stream Python en un contexto externo para garantizar el cierre antes de limpiar el temporal. La repetición pasó; no se presenta ese primer intento fallido como exitoso.

Verificación final: wheel construido localmente sin resolver dependencias ni usar red, e instalado en `.venv-verify`. Se copiaron tests/scripts/pyproject a un checkout temporal sin `src` ni `data`; las **69 pruebas también pasaron** desde el paquete instalado, incluidos los subprocess CLI aislados. No es una ejecución GitHub ni una descarga real.

Ruff: `All checks passed!` y `21 files already formatted`; `pip check`: sin dependencias rotas. Auditoría de 15 Markdown y 85 enlaces locales, PDF original intacto, 24 hashes raw iguales a los registrados antes de su organización y cero manifiestos/eventos/temporales/locks creados en raw real. Git sigue en main, sin commits/remotos/índice; los 63 archivos públicos no rastreados no incluyen datos reales ni cachés.

No se descargó un dataset real, no se registraron automáticamente los archivos aportados y no se certifica la conectividad real a TLC con estas pruebas. Revisión humana T06/T07 pendiente; no se cierra G2 ni se habilita entrenamiento.
