# NYC Yellow Taxi MLOps

Proyecto de maestría de Universidad CENFOTEC para estimar la duración de un viaje en minutos al inicio y demostrar un ciclo MLOps reproducible y auditable.

## Estado actual

T01/T02 fueron cerradas por el usuario y las continuaciones hasta T10/T11 se autorizaron progresivamente. Hay esquema, motor de calidad y CLI de validación con integración offline. T10/T11 están verificadas técnicamente con fixtures para revisión humana; el flujo real permanece bloqueado por D-04/D-06. T12 y siguientes, periodos y umbrales reales requieren autorización.

Hay CLI de ingesta/validación, manifiestos, esquema raw, reportes de calidad y pruebas de empaquetado, fixtures y perfilado. La integración raw → validated solo publica fixtures TEST_ONLY aisladas, sin aprobación para entrenamiento. Políticas reales, features, modelos, API, Dockerfile, Compose y workflows siguen pendientes. Se usan herramientas T03 y PyArrow, sin dependencias nuevas.

Repositorio GitHub: [ModoJorgeBT/nyc-yellow-taxi-mlops](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops), rama `main`. El usuario autorizó el primer commit y la publicación del estado hasta T10/T11. Las evidencias anteriores que indican «sin commits/remotos/publicación» describen las verificaciones previas a esta autorización. La publicación no resuelve decisiones pendientes ni habilita datos reales para entrenamiento; GitHub Actions sigue sin implementar.

Documentos rectores: [intent.md](intent.md), [spec.md](spec.md) y [plan.md](plan.md). Consultar [decisiones y riesgos](docs/decisions.md), [arquitectura](docs/architecture.md), [ADR local](docs/adr/0001-arquitectura-local.md) y [verificación T02](docs/t02-verification.md).

Entorno y evidencia actual: [T03](docs/t03-environment.md). Datos aportados: [inventario de metadatos 2024/2025](reports/raw_inventory.md).

Continuación: [evidencia T04/T05](docs/t04-t05-verification.md), [fixtures](tests/fixtures/README.md) e [informe EDA](reports/eda_schema.md).

Ingesta actual: [guía, contrato y evidencia T06/T07](docs/t06-t07-ingestion.md).

Calidad actual: [contrato y evidencia T08/T09](docs/t08-t09-validation.md), [configuración](configs/data.yaml) y [pruebas](tests/unit/test_validation.py).

Pipeline actual: [contrato y evidencia T10/T11](docs/t10-t11-data-pipeline.md) y [pruebas de integración](tests/integration/test_data_pipeline.py).

## Estructura preparada

| Ruta | Finalidad |
|---|---|
| `src/` | Paquete raíz para comandos y módulos del proyecto. |
| `src/ingestion` | Descarga mensual, manifiestos, idempotencia y registro local explícito. |
| `src/validation` | Esquema, reglas y CLI con reportes; solo publicación sintética aislada mientras la configuración real siga PENDIENTE. |
| `src/features` | Transformaciones futuras. |
| `src/training`, `src/evaluation` | Entrenamiento y evaluación futuros. |
| `src/api`, `src/monitoring`, `src/retraining` | Serving, observación y retraining futuros. |
| `tests/unit`, `tests/fixtures` | Pruebas de empaquetado, casos sintéticos y perfilador; no requieren datos reales. |
| `tests/integration`, `tests/api` | Integración de datos offline; API pendiente. |
| `scripts` | Perfilador acotado de T05; no es el pipeline productivo. |
| `configs`, `notebooks` | Contrato data.yaml versionado; otras configuraciones y exploración futuras. |
| `data/raw`, `data/validated`, `data/processed` | Datos locales excluidos de Git; solo se versionan marcadores. |
| `reports` | Salidas locales; se permite versionar documentación Markdown pequeña. |
| `.github/workflows` | Carpeta reservada; no contiene automatizaciones ejecutables. |

## Colocar los Parquet existentes

Colocar cada archivo original en `data/raw/YYYY/MM/yellow_tripdata_YYYY-MM.parquet`, creando los subdirectorios de año y mes que correspondan. Por ejemplo, un archivo de enero de 2025 se ubica en:

```text
data/raw/2025/01/yellow_tripdata_2025-01.parquet
```

El ejemplo no aprueba los periodos de entrenamiento. Conservar los archivos originales sin transformarlos ni sobrescribir otros lotes. No es necesario volver a descargarlos para preparar T02.

Los 24 archivos aportados ya están organizados así, de enero a diciembre de 2024 y 2025. Suman 1.418 GiB y 89,892,322 filas declaradas en footers. Se verificó que sus hashes no cambiaron durante el movimiento. Los esquemas tienen 19 columnas en 2024 y 20 en 2025 por `cbd_congestion_fee`; no se escanearon todas las filas ni se aprobaron Quality Gates.

La carpeta raw no certifica procedencia ni calidad. T05 perfila solo 2024 mediante la muestra posicional aprobada de 2.048 filas por row group; 2025 permanece sin perfilado de filas. Manifiestos/gates siguen pendientes y los metadatos de procedencia ausentes no se inventan. No colocar archivos manualmente en validated o processed como si hubieran sido aprobados.

Los Parquet reales están excluidos de Git. La excepción `tests/fixtures/*.parquet` contiene diez archivos sintéticos pequeños de T04 (103.906 bytes en total); no copiar datos TLC reales allí.

## Fixtures y perfilado de T04/T05

Las fixtures siguen siendo necesarias aunque existan datos reales: permiten repetir casos de nulos, duplicados, fechas inválidas y cambios de esquema con resultados conocidos, sin subir datasets reales a CI.

```powershell
.\.venv\Scripts\python.exe -m tests.fixtures.factory --seed 42 --output-dir tests/fixtures
.\.venv\Scripts\python.exe -m scripts.profile_sample --rows-per-group 2048
```

La muestra de 90.112 filas de 2024 es sesgada por posición y no representa todo el año. Se observaron 35 duraciones no positivas, 155 recogidas fuera del mes y 4.096 pasajeros nulos; son conteos de muestra. D-02 dispone de mediciones del host y del perfilado, pero límites Docker y presupuesto de entrenamiento siguen pendientes. D-04 contiene propuestas sin umbrales de lote aprobados.

El perfilador guarda `reports/eda_schema.md` y un JSON detallado local excluido de Git. No modifica raw ni genera datos aprobados. Las pruebas usan fixtures y temporales propios; los reportes de EDA utilizan únicamente los Parquet reales de la muestra autorizada.

## Entorno Python de T03

Versión aprobada: Python 3.14.7 de 64 bits, registrada en [.python-version](.python-version). El lock se generó y probó en Windows con CPython 3.14; la compatibilidad de Docker/Linux y del stack MLOps completo aún no está probada.

En PowerShell, seleccionar primero el intérprete aprobado; `py -3.14 --version` debe mostrar 3.14.7. Crear un entorno nuevo solo si `.venv` no existe:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip --isolated install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple --cache-dir .cache/pip -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip --isolated install --no-index --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

No se necesita activar el entorno ni modificar la política de ejecución de PowerShell. `.venv` es local y está excluido de Git. La instalación del proyecto es separada y sin resolución de dependencias: las herramientas y dependencias transitivas se instalan primero con hashes desde [requirements-dev.lock](requirements-dev.lock). La guía [T03](docs/t03-environment.md) detalla la prueba adicional con wheel y un segundo entorno limpio, además de límites e incidentes del sandbox.

## Ingesta de T06/T07

```powershell
.\.venv\Scripts\python.exe -m src.ingestion.download --help
```

El CLI admite año/mes, timeout, reintentos, directorio raw y hash esperado. Para un lote ausente descarga desde la URL canónica TLC; para un lote con manifiesto verifica hash/esquema/volumen y devuelve SKIPPED sin red. Los conflictos bloquean, sin reemplazar datos.

Los 24 archivos aportados todavía no tienen manifiestos de ingesta. El comando normal los bloquea hasta una acción explícita: `--register-local` conserva bytes y crea un registro LOCAL_UNVERIFIED con fuente/fecha de descarga desconocidas. Esa política se aprobó y probó con fixtures, sin aplicarla a los archivos reales. No convierte un archivo raw en datos aprobados para entrenamiento. Consultar la guía T06/T07 antes de usar los comandos sobre raw.

## Esquema y calidad de T08/T09

`configs/data.yaml` contiene el esquema aprobado y una política real PENDIENTE. Su sintaxis es JSON compatible con YAML; no se instaló PyYAML. El motor recibe bloques Arrow y devuelve reportes con reglas, conteos/tasas, umbrales y evidencia. Distingue exclusiones de filas del rechazo completo del lote, mide duplicados entre bloques y permite viajes cuya llegada cruza de mes.

La entrega T08/T09 alcanzó 129 pruebas; T10/T11 amplían la suite a 162. Solo perfiles completos TEST_ONLY y fixtures marcadas pueden superar calidad en estas pruebas. Un gate crítico o cualquier decisión pendiente bloquea. La integración T10 comprueba manifiestos, exhaustividad y escritura segura de fixtures, manteniendo `approved_for_training=false`; no se validaron filas reales de 2025 ni se adoptaron límites del EDA como definitivos.

Detalles de API, semántica de tasas/exclusiones, costes temporales, DST pendiente y evidencia: [T08/T09](docs/t08-t09-validation.md).

## Pipeline de T10/T11

```powershell
.\.venv\Scripts\python.exe -m src.validation.run --help
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_data_pipeline.py --basetemp=.cache/pytest-t10-integration -o cache_dir=.cache/pytest-cache-t10-integration
```

El modo normal exige manifiesto e integridad y guarda rechazo por política real pendiente, sin leer filas. `--test-only` exige configuración y fixture sintéticas y publica bajo `data/validated/_test_only/`, con reportes y marcador final `validation.json`. No registra automáticamente los Parquet aportados. Repetir crea un intento nuevo y conserva los anteriores; el CLI devuelve código 1 ante rechazo/error. Los detalles de linaje, publicación incompleta, rutas y límites están en [T10/T11](docs/t10-t11-data-pipeline.md).

Estos resultados de prueba no habilitan entrenamiento. T12 deberá comprobar ámbito/aprobación y no consumir todos los Parquet de validated mediante un glob sin controles. D-04/D-06 siguen pendientes y G2 operativo permanece abierto.

## Comprobaciones de estructura de T02

Desde la raíz, usando un intérprete Python existente y funcional, se puede comprobar que los paquetes vacíos importan sin dependencias externas:

```powershell
python -B -c "import src.ingestion, src.validation, src.features, src.training, src.evaluation, src.api, src.monitoring, src.retraining; print('Importaciones OK')"
git symbolic-ref --short HEAD
git status --short --untracked-files=all
git check-ignore -v --no-index data/raw/2025/01/yellow_tripdata_2025-01.parquet .env
```

La rama esperada es `main`. Antes de la publicación inicial los archivos aparecían como no rastreados; tras versionarlos, los datos reales y secretos deben seguir excluidos. `git check-ignore --no-index` también permite comprobar una ruta representativa sin crear el archivo.

La consulta `python -m pytest --version` de T02 solo acreditaba disponibilidad. T03 añadió una prueba real de empaquetado y T04/T05 amplían la suite a casos sintéticos y perfilado; no son todavía pruebas de modelos/API ni Quality Gates productivos. Si el alias `python` de Windows no funciona, usar el intérprete aprobado de VS Code o los ejecutables del entorno.

## Configuración y decisiones pendientes

[.env.example](.env.example) es una plantilla pública con rutas relativas y una URI de MLflow propuesta para el host. No contiene credenciales ni se carga automáticamente. No hay todavía servicio MLflow al que conectarse; la configuración entre contenedores se resolverá en su tarea.

Python, MLflow, FastAPI y Docker Compose para ejecución local están confirmados. T03 fija Python, setuptools, pip/wheel, Ruff, Pytest, pip-tools y PyArrow. MLflow/FastAPI no se instalaron aún; Pandas, sklearn, Pydantic, Evidently y GitHub Actions mantienen su aprobación pendiente. Destino conocido, meses, recursos, umbrales, persistencia y criterio general de PR mantienen los estados de D-01…D-08. No introducir en inferencia llegada, duración/target, importes finales ni distancia real de taxímetro.

Los CLI de ingesta/validación y los módulos de esquema/calidad están implementados; los comandos de features/modelos/Docker incluidos en spec/plan siguen siendo contratos futuros. No subir `.env`, Parquet reales, modelos ni bases locales de MLflow a Git. Ver [.gitignore](.gitignore).
