# NYC Yellow Taxi MLOps

Proyecto de maestría de Universidad CENFOTEC para estimar la duración de un viaje en minutos al inicio y demostrar un ciclo MLOps reproducible y auditable.

## Estado actual

Actualización del 2026-11-05: **T14 y la primera comparación T16/T17 tienen cierre técnico auditado; T15 permanece congelada.** Los 24 meses están preparados y las cuatro particiones auditadas: train 41.119.495, validation 11.163.264, test 12.712.466 y replay 24.266.924 filas. Se conservan los 24 raw, D-04 global, diez FAIL originales y todas las exclusiones autorizadas. [Auditoría T14](reports/quality/t14_completion.md).

SGD Huber y MLP16 se ajustaron con todo train. SGD fue elegido usando validation antes de abrir test: MAE 6,876910 min frente a 7,741890 del baseline; en test 7,965068 frente a 9,032999. MLP fue peor que el baseline y SGD empeoró ligeramente su P90 en validation. [Comparación y segmentos T17](reports/evaluation/t17_model_comparison.md).

LightGBM 4.7.0 fue entrenado con las 41.119.495 filas train y 100 árboles. En las 11.163.264 filas validation: MAE 6.496404, RMSE 9.847425, MedAE 4.631360 y P90 13.478764 minutos. Ajuste y evaluación auditados; 447 pruebas por entorno. La entrega inicial fue solo validation; la evaluación independiente posterior ya terminó y está auditada. La selección SGD y el test de la primera comparación permanecen intactos; en aquella fase no hubo promoción. [Reporte LightGBM](reports/evaluation/lightgbm_validation.md). Se añadió solo esa dependencia al lock; las 23 versiones previas no cambiaron. Ver [software y comandos](docs/t16-t17-validation.md).

**Evaluación final independiente completada y auditada — 2026-11-05:**
enero–marzo de 2026, 10.937.087 viajes; MAE LightGBM **7,742891 min**, SGD
**8,352735** y baseline **9,141254**. Se excluyeron 139.305 filas DQ mediante
tres excepciones humanas exactas y 814 por corte de etiqueta; los 27 raw,
modelos y selección de 2025 permanecen intactos. Reinicio de recursos aprobado
6 GiB libres/2 GiB RSS solo para inferencia final; entrenamiento 8/4 y preparación
4/2 sin cambios. 474 pruebas por entorno y auditoría completa. Sin promoción en aquella fase.
[Informe final](reports/evaluation/lightgbm_final_evaluation.md).

T18 tiene cierre técnico auditado: MLflow 3.16.1 registra baseline v1, SGD v2, MLP v3 y LightGBM v4; reinicio sin pérdida ni duplicados. [Runs y evidencia](reports/tracking/t18_completion.md), [guía local](docs/t18-mlflow.md). Servidor activo al cierre: http://127.0.0.1:5000. **T19 completada:** LightGBM **v4 es el champion inicial**, aprobado por el usuario y verificado. El alias `champion` resuelve a `models:/nyc-yellow-taxi-duration/4`. [Decisión y evidencia](reports/model_selection.md). G3 cumple su alcance de Sprint 3. T20–T22 tienen cierre técnico verificado: API con champion LightGBM v4, validación estricta y errores controlados. Docker serving T23–T25 está verificado; CI, monitoreo y retraining siguen pendientes en sus tareas. Revisión humana de resultados independiente del cierre técnico. La tercera entrega reúne código y documentación de T14–T19; el estado operativo de MLflow y los binarios permanecen locales.

Repositorio GitHub: [ModoJorgeBT/nyc-yellow-taxi-mlops](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops), rama `main`. El primer commit `164bf9e` contiene T01–T11; el segundo `27b09d2` incorpora features T12/T13, D-01/D-02/D-04, baseline T15 y el bloqueo histórico de T14. El tercero completa T14–T19, evaluación independiente, tracking MLflow y champion LightGBM v4. El [historial de las tres entregas](docs/commit-history.md) detalla alcance, pruebas y límites; los datos, pesos y la instancia MLflow permanecen locales. Las menciones históricas a «sin nuevo commit/push» corresponden al momento de esas mediciones. GitHub Actions sigue sin implementar.

Documentos rectores: [intent.md](intent.md), [spec.md](spec.md) y [plan.md](plan.md). Consultar [decisiones y riesgos](docs/decisions.md), [arquitectura](docs/architecture.md), [ADR local](docs/adr/0001-arquitectura-local.md) y [verificación T02](docs/t02-verification.md).

Entorno y evidencia actual: [T03](docs/t03-environment.md). Datos aportados: [inventario de metadatos 2024/2025](reports/raw_inventory.md).

Continuación: [evidencia T04/T05](docs/t04-t05-verification.md), [fixtures](tests/fixtures/README.md) e [informe EDA](reports/eda_schema.md).

Ingesta actual: [guía, contrato y evidencia T06/T07](docs/t06-t07-ingestion.md).

Calidad actual: [contrato y evidencia T08/T09](docs/t08-t09-validation.md), [configuración](configs/data.yaml) y [pruebas](tests/unit/test_validation.py).

Pipeline actual: [contrato y evidencia T10/T11](docs/t10-t11-data-pipeline.md) y [pruebas de integración](tests/integration/test_data_pipeline.py).

Features actuales: [contrato y evidencia T12/T13](docs/t12-t13-features.md), [whitelist](src/features/schema.py), [transformaciones](src/features/build.py).

D-04 ratificada/congelada con [excepción puntual de marzo](docs/t15-march-exception.md). Los límites globales permanecen: se conserva FAIL original, se excluyen las 23.886 filas inválidas y se aceptan por decisión humana 4.121.371 elegibles. La excepción exige mes/hash/reporte exactos y no cubre otros fallos. [evaluación real auditada](reports/quality/t15_baseline_validation.md). Suite: 380 pruebas en desarrollo y wheel.

## Estructura preparada

| Ruta | Finalidad |
|---|---|
| `src/` | Paquete raíz para comandos y módulos del proyecto. |
| `src/ingestion` | Descarga mensual, manifiestos, idempotencia y registro local explícito. |
| `src/validation` | Esquema, reglas REAL/TEST_ONLY, autorización y CLI con reportes; calidad separada de entrenamiento. |
| `src/features` | Target UTC, whitelist, transformación compartida, Pipeline y lector de lotes REAL/TEST_ONLY aprobados. |
| `src/training` | Particiones temporales, baseline y candidatos SGD/MLP completos por bloques; LightGBM completo sobre todo train. |
| `src/evaluation` | Comparación auditada baseline/SGD/MLP, métricas exactas y segmentos; elección con validation antes de test. |
| `src/api`, `src/monitoring`, `src/retraining` | Serving, observación y retraining futuros. |
| `tests/unit`, `tests/fixtures` | Pruebas de empaquetado, casos sintéticos y perfilador; no requieren datos reales. |
| `tests/integration`, `tests/api` | Integración offline, persistencia MLflow y contrato REST. |
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

La carpeta raw no certifica procedencia ni calidad. Los 24 archivos están registrados como LOCAL_UNVERIFIED, con fuente/fecha nulas y bytes/hash conservados. Hay 24 versiones con features: catorce lotes pasaron calidad y diez fueron aceptados mediante autorizaciones humanas exactas, conservando FAIL medidos y excluyendo todas las filas inválidas. [Continuación actual de T14](reports/quality/t14_completion.md), [rechazos originales](reports/quality/t14_full_preparation.md) y [evaluación congelada de T15](reports/quality/t15_baseline_validation.md).

Los Parquet reales están excluidos de Git. La excepción `tests/fixtures/*.parquet` contiene diez archivos sintéticos pequeños de T04 (103.906 bytes en total); no copiar datos TLC reales allí.

## Fixtures y perfilado de T04/T05

Las fixtures siguen siendo necesarias aunque existan datos reales: permiten repetir casos de nulos, duplicados, fechas inválidas y cambios de esquema con resultados conocidos, sin subir datasets reales a CI.

```powershell
.\.venv\Scripts\python.exe -m tests.fixtures.factory --seed 42 --output-dir tests/fixtures
.\.venv\Scripts\python.exe -m scripts.profile_sample --rows-per-group 2048
```

La muestra T05 de 90.112 filas de 2024 es sesgada por posición y no representa todo el año. Se observaron 35 duraciones no positivas, 155 recogidas fuera del mes y 4.096 pasajeros nulos; son conteos de esa muestra. D-04 se resolvió posteriormente con otra muestra aleatoria, aprobación explícita y piloto completo. D-02 tiene presupuesto incremental aprobado; sus controles, mediciones de entrenamiento y límites efectivos Docker aún deben implementarse/verificarse en sus tareas.

El perfilador guarda `reports/eda_schema.md` y un JSON detallado local excluido de Git. No modifica raw ni genera datos aprobados. Las pruebas usan fixtures y temporales propios; los reportes de EDA utilizan únicamente los Parquet reales de la muestra autorizada.

## Entorno Python de T03

T13 amplía este entorno aprobado con scikit-learn 1.9.1 y tzdata 2026.6; el snapshot de T13 incluyó 23 paquetes con hashes. La extensión LightGBM lleva el lock vigente a 24 paquetes, sin cambiar las 23 versiones previas. La instalación del lock siguiente incluye el extra de features y sus transitivas. Detalle y límites en [T12/T13](docs/t12-t13-features.md).

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

Hay 15 manifiestos raw creados por registro local explícito autorizado (2024 y enero–marzo de 2025). Solo 14 lotes superaron calidad y tienen features; marzo de 2025 sigue rechazado. Los nueve meses restantes no se incorporaron en este intento. --register-local conserva bytes y no concede calidad ni entrenamiento. La autorización cubre los 24 hashes/meses actuales, no archivos nuevos/modificados. [decisión y contraste oficial](docs/t14-t15-quality-blocker.md).

## Esquema y calidad de T08/T09

`configs/data.yaml` contiene el esquema aprobado y la política provisional APPROVED_REAL. Su sintaxis es JSON compatible con YAML; no se instaló PyYAML. El motor recibe bloques Arrow y devuelve reportes con reglas, conteos/tasas, umbrales y evidencia. Distingue exclusiones de filas del rechazo completo del lote, mide duplicados exactos entre bloques y permite viajes cuya llegada cruza de mes. Históricos localizados en Nueva York, duración UTC y cuarentena DST; pasajeros fuera de 0–6 pasan a null con auditoría.

Las entregas iniciales T08/T09 y T10/T11 alcanzaron 129 y 162 pruebas con fixtures. D-04 añade el perfil real aprobado y probado, con 255 pruebas totales. Un fallo crítico bloquea publicación; exclusiones toleradas y controles informativos permanecen visibles como WARN. T10 comprueba autorización, manifiestos, exhaustividad y escritura segura, manteniendo `approved_for_training=false` incluso al aprobar calidad REAL.

Contrato y evidencia históricos: [T08/T09](docs/t08-t09-validation.md). Política, semántica temporal y recursos actuales: [D-04](docs/d04-activation.md).

## Pipeline de T10/T11

```powershell
.\.venv\Scripts\python.exe -m src.validation.run --help
.\.venv\Scripts\python.exe -m pytest -q tests/integration/test_data_pipeline.py --basetemp=.cache/pytest-t10-integration -o cache_dir=.cache/pytest-cache-t10-integration
```

El modo normal exige manifiesto, integridad, política APPROVED_REAL y procedencia permitida; publica bajo `data/validated/YYYY/MM/id/` solo tras superar calidad. `--test-only` exige configuración y fixture sintéticas y usa `data/validated/_test_only/`. Ambos conservan reportes y marcador final `validation.json`. No se registran automáticamente los Parquet aportados. Repetir crea un intento nuevo y conserva los anteriores; el CLI devuelve código 1 ante rechazo/error. Detalle inicial en [T10/T11](docs/t10-t11-data-pipeline.md) y actualización en [D-04](docs/d04-activation.md).

La calidad aprobada no habilita entrenamiento. El lector T12/T13 comprueba ámbito/aprobación y exige un lote explícito, sin glob de todos los Parquet. D-04 provisional resuelta; G2 conserva revisión humana. Catálogo operativo aprobado; contrato REST completo pendiente en D-06. D-01/D-02 aprobadas para el [protocolo local](docs/d01-d02-protocol.md); instrumentación y pruebas de recursos pendientes antes de modelado real.

## Target y features de T12/T13

El lector de features comprueba un lote validado explícito y sus hashes/estado REAL o TEST_ONLY antes de leer filas. REAL exige calidad aprobada, política temporal/autorización coherentes y ninguna exclusión adicional; rechaza raw, resultados incompletos, datos modificados y mezcla de modos. Extrae origen, calendario de Nueva York y pasajeros opcionales; destino y variables post-viaje quedan fuera de X. El target se calcula en UTC después de localizar timestamps históricos; horarios ambiguos/inexistentes se apartan con motivo. Esta es una convención aprobada del proyecto, no una garantía del diccionario TLC.

El preprocesador compartido admite offset en inferencia, representa pasajeros ausentes con indicador y aprende categorías de origen únicamente durante fit. La construcción de archivos de features no hace fit: las particiones de T14 todavía no existen. El evento final de etiqueta se conserva como contexto separado y no acredita publicación del lote.

```powershell
.\.venv\Scripts\python.exe -m src.features.build --help
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_features.py tests/integration/test_feature_pipeline.py --basetemp=.cache/pytest-feature-check -o cache_dir=.cache/pytest-cache-feature-check
```

La entrega T12/T13 tenía 227 pruebas, 65 nuevas; la suite actual tiene 255 tras D-04. El CLI requiere `--validated-batch`; `--test-only` selecciona el modo sintético. Produce features.parquet, target.parquet, context.parquet y marcador final bajo processed/YYYY/MM/id o processed/_test_only. Este soporte REAL se probó con fixtures; no se ejecutó sobre enero real. No concede aprobación para entrenamiento. Ver [contrato, serialización y límites](docs/t12-t13-features.md).

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

Python, MLflow, FastAPI y Docker Compose para ejecución local están confirmados. T03 fija las herramientas de entorno y PyArrow; T13 añade scikit-learn/tzdata y transitivas con aprobación. MLflow/FastAPI/Pydantic y pandas están instalados en el entorno separado del SDK; T20–T22 reutilizan ese entorno con HTTPX/httpcore aprobados. Evidently y GitHub Actions siguen pendientes. D-04 aprueba calidad provisional y catálogo operativo; D-06 resuelve whitelist/tiempo, con destino deshabilitado. D-01/D-02 fijan periodos y ejecución incremental con todos los elegibles: SGDRegressor/MLPRegressor pequeño, 4 hilos, 8 GiB, 2 h/candidato, preflight 12 GiB RAM/50 GiB disco libres. El contrato REST D-06 está aprobado y probado; los presupuestos vigentes y resultados de entrenamiento/persistencia constan en el plan. Docker, reglas automáticas de drift/promoción y criterio general de PR mantienen sus pendientes. No introducir llegada, target, importes finales ni distancia real de taxímetro en inferencia.

Los CLI de ingesta/validación/features están implementados con las restricciones indicadas; modelos, Registry y API tienen verificación técnica; Docker serving está verificado en T23–T25. No subir `.env`, Parquet reales, modelos ni bases locales de MLflow a Git. Ver [.gitignore](.gitignore).

## Particiones temporales T14

[Contrato y evidencia](docs/t14-temporal-splits.md), [configuración aprobada](configs/model.yaml). El CLI `python -m src.training.split --inputs CATALOGO_JSON` exige las 24 versiones explícitas de features y su validación; sin glob, submuestreo ni fit. Conserva features/target/context separados, aparta etiquetas no disponibles al corte y verifica cobertura. `--test-only` requiere fixtures y aísla salidas. Suite inicial T14: 287 pruebas; [demostración de 24 meses sintéticos](reports/quality/t14_temporal_splits.md).

T14 integral sobre 24 meses permanece pendiente. T15 completó ajuste y evaluación usando el lector causal y todas las fuentes train/validation, con la separación autorizada. [evaluación real auditada](reports/quality/t15_baseline_validation.md). Los snapshots de validation de T15 no son una T14 integral completa.

## Baseline T15

[Contrato T15](docs/t15-baseline.md). El usuario aprobó mediana global exacta de todo train 2024, en disco, y predicción solo de validación ene–mar 2025. El CLI es `python -m src.training.baseline --split-batch RUTA_LOTE_T14`; no abre test/replay. Modelo JSON y predicciones alineadas, sin MLflow/serving/promoción. Suite actual: 356 pruebas en desarrollo y wheel.

Preparación/evaluación usaron el perfil 4 GiB libres/2 GiB RSS/50 GiB disco; T16 conserva 12/8. Ajuste y evaluación T15 terminaron y fueron auditados, sin test/replay ni candidatos. [evaluación real auditada](reports/quality/t15_baseline_validation.md).

Ajuste: `python -m src.training.baseline_fit --inputs configs/train-feature-batches.local.json`. Evaluación del ajuste congelado: `python -m src.training.baseline_evaluate --fit-batch RUTA_AJUSTE --inputs configs/validation-feature-batches.local.json`. [evaluación real auditada](reports/quality/t15_baseline_validation.md). No se modifica el ajuste original ni se reutiliza un dataset rechazado sin autorización.

## Modelos y evaluación auditados

SGD Huber y MLP16 se ajustaron con las 41.119.495 filas train, una pasada por candidato. SGD fue elegido con validation antes de abrir test: MAE 6,876910 frente a 7,741890 del baseline. En test obtuvo MAE 7,965068 frente a 9,032999. MLP fue peor que el baseline; SGD empeoró ligeramente P90 en validation. Sin reajustes después de test ni promoción.

[Entrenamiento T16](reports/quality/t16_training.md), [comparación T17 y segmentos](reports/evaluation/t17_model_comparison.md) y [software/CLI verificados](docs/t16-t17-validation.md). 423 pruebas en desarrollo y 423 desde wheel instalado; límites reales 8 GiB libres/4 GiB RSS respetados.

El usuario aprobó [añadir LightGBM](docs/t16-lightgbm-extension-proposal.md) con todos los elegibles, presupuesto vigente y evaluación solo con validation. El test de la primera comparación permanece congelado; una nueva evaluación final independiente de LightGBM queda pendiente. Ya está instalado, entrenado y auditado en el alcance de validation; [resultado](reports/evaluation/lightgbm_validation.md). Esta continuación sigue local, sin nuevo commit/push.


## Serving T20–T22 — 2026-11-09

LightGBM v4 se carga desde el Registry con aprobación y hashes verificados.
`POST /predict`, `GET /health` y `GET /model-info` probados: 200 válido,
422 inválido y 503 sin modelo. Contrato D-06 aprobado: origen del catálogo,
timestamp con offset y pasajeros opcionales 0–6; destino deshabilitado.

[Contrato, instalación y arranque local](docs/t20-t22-serving.md).
553 casos serving verificados (incluye reintento de un reinicio bloqueado por
el sandbox), 501 nativos y 51 del wheel instalado fuera de src. Auditoría con
champion real, sin cambios de modelos/evaluaciones/Registry. Locks históricos
intactos; nuevo `requirements-serving.lock` con 97 paquetes.
Aquella entrega no dejó la API iniciada; la entrega Docker posterior sí deja API/MLflow saludables.


## Docker T23–T25 — 2026-11-09

Build, arranque Linux, predicción LightGBM v4, errores 422/503 y persistencia
tras down/up verificados. **G4 PASS técnico.** Servicios activos:

- API y documentación: http://127.0.0.1:8080/docs
- MLflow Docker: http://127.0.0.1:5001

El puerto 8000 y MLflow nativo 5000 se conservaron. El Registry Docker usa una
copia aislada en volumen Linux; cuatro runs/versiones y champion v4 intactos.
No se reentrenó ni cambió ninguna aprobación de modelo o umbral de calidad.

[Operación y comandos](docs/t23-t25-docker.md),
[cierre y evidencia](reports/smoke/t23-t25.md).
Usar `docker compose up -d --no-build --wait mlflow api` para arrancar y
`docker compose down` para detener conservando el volumen. No usar `down -v`.
Clonar Git no incluye los datos/modelos/Registry; se necesita el bootstrap
aprobado. Próxima tarea: T26 (CI). Sin nuevo commit/push en esta entrega.

## CI y observación T26–T28 — 2026-11-09

T27/T28 tienen verificación técnica: métricas operativas reales Docker y
comparación de calidad de julio–diciembre 2025 contra los mismos meses de
2024. Los FAIL y excepciones D-04 siguen visibles; no se cambian modelos,
umbrales ni aprobaciones. [Métricas](reports/monitoring/t27_service_metrics.md),
[calidad](reports/monitoring/t28_quality_replay.md) y
[comandos y límites](docs/t26-t28.md).

T26 prepara Ruff, Pytest, smoke HTTP y build Docker en GitHub Actions con
fixtures, 2 CPU/4 GiB, 10 GiB de disco y 20 minutos. La verificación Linux
local y remota pasó: 601 pruebas, Ruff, dependencias, smoke HTTP e imagen de
producción. **T26 PASS técnico:** [PR #1 verde](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/pull/1)
y demostración roja/verde separada; [evidencia](reports/monitoring/t26_github_ci.md).
La [publicación](docs/t26-publication-proposal.md) fue aprobada por el usuario;
queda en PR borrador para revisión, sin merge a main. G5 y T29–T31 continúan pendientes.

## Monitoreo T29–T31 — 2026-11-09

**G5 PASS técnico.** Referencia de train 2024 completo y seis meses de replay
julio–diciembre 2025: 24.266.924 predicciones/etiquetas maduras auditadas.
PSI, calidad, métricas y reportes Evidently versionados; no se cambia el champion.
CI verifica 625 pruebas principales y 17 del renderer aislado. La omisión de
Evidently en el runtime original se cubre explícitamente en ese segundo entorno.

```powershell
.\.venv-mlflow\Scripts\python.exe -m src.monitoring.run --year 2025 --month 7
```

El renderer usa `.venv-monitoring`, Evidently 0.7.23 y pandas 2.3.3; el modelo
conserva su runtime pandas 3.1.1. Sin etiquetas, desempeño NOT_AVAILABLE.
Las observaciones actuales de servicio no se atribuyen a meses de 2025.
[Operación y límites](docs/t29-t31-monitoring.md),
[resultados y CI](reports/monitoring/t29-t31_monthly_replay.md).
El [historial](docs/commit-history.md) distingue código, correcciones y evidencia
de la cuarta entrega ampliada. PR #1 en borrador; T32–T38 pendientes.
