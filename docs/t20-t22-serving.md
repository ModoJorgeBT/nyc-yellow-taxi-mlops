# T20–T22 — Serving local

El 2026-11-09 el usuario autorizó las tres tareas y aprobó explícitamente el
contrato D-06 y HTTPX para TestClient. Alcance: esquemas, carga del champion y
endpoints; Docker corresponde a T23–T25.

## Contrato aprobado D-06 v1

`POST /predict` recibe un objeto con `pickup_datetime` ISO 8601 con `T` y
offset obligatorio, `pickup_location_id` entero del catálogo D-04 y
`passenger_count` opcional/null o entero entre 0 y 6. Incluye zonas 264/265.
Rechaza booleanos, strings/decimales como enteros, timestamps numéricos,
fechas sin offset, campos extra, destino y variables posteriores al viaje.
El calendario se obtiene en Nueva York mediante el pipeline congelado.
Offsets distintos que identifican el mismo instante producen las mismas features.
No se restringe la fecha al periodo histórico ni se consulta una etiqueta.

```json
{"pickup_datetime":"2026-03-12T08:30:00-04:00","pickup_location_id":161,"passenger_count":1}
```

La respuesta contiene `predicted_duration_minutes`, `unit="minutes"`,
`model_version` y `predicted_at_utc`. Las cotas de 1 segundo–180 minutos
pertenecen al modelo ya aprobado; la API comprueba su salida.

`GET /health` devuelve `200 {"status":"ok","model_loaded":true}` cuando el
modelo está listo. `GET /model-info` informa nombre, versión cargada, estado,
periodo train y fecha UTC de carga; no inventa fecha de entrenamiento.
Los tres endpoints dan 503 si no se pudo cargar el modelo. Entrada inválida:
422; fallo inesperado al predecir: 500. Los errores no reflejan payloads,
excepciones internas, rutas ni secretos.

## Carga y operación

El operador conserva `configs/champion.yaml`, `configs/data.yaml` y el recibo
aplicado de `tracking/approvals/`. El loader reutiliza el resolver T19:
comprueba aprobación, alias, versión, run, tags, parámetros y métricas;
descarga **la versión fija 4**, verifica los 50 archivos antes de deserializar,
rechaza enlaces/bytecode ajeno y ejecuta los seis casos sintéticos aprobados.
Una segunda resolución bloquea cambios de identidad durante la descarga.
Se conserva la copia privada durante el lifespan y se elimina al cerrar.
La solicitud HTTP nunca elige un modelo ni una ruta de artefactos.

Se carga una vez al arrancar, sin fallback, promoción, recarga automática ni
consulta al Registry por predicción. Un cambio posterior de alias requiere
reinicio controlado; las respuestas exponen la versión efectivamente cargada.
La salud indica readiness local, no disponibilidad continua del Registry.
Las llamadas al predictor están serializadas; el modelo conserva cuatro hilos.

Requiere el servidor MLflow T18 en `127.0.0.1:5000`. Desde la raíz, usando el
entorno separado existente y el lock completo de serving:

```powershell
.\.venv-mlflow\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-serving.lock
.\.venv-mlflow\Scripts\python.exe -m pip install --no-deps --no-build-isolation .
.\.venv-mlflow\Scripts\python.exe -m uvicorn src.api.main:app --host 127.0.0.1 --port 8000 --workers 1 --no-access-log --log-config configs/serving-logging.json
```

Sin `--reload`. El log de la aplicación registra ruta normalizada, código y
duración; omite query, headers y cuerpo. `--no-access-log` evita que Uvicorn
registre URLs completas. Documentación interactiva local: `/docs`.
Los archivos de configuración/aprobación y almacenamiento local son de confianza
del operador; no se aceptan paquetes de terceros ni rutas desde HTTP.

## Dependencias y verificación

Los locks históricos no cambian: entrenamiento 24 paquetes, SDK 95.
`requirements-serving.in/.lock` conserva las 95 versiones y añade únicamente
HTTPX 0.28.1 y httpcore 1.0.9: 97 paquetes fijados con hashes. Se instalaron solo
en `.venv-mlflow`. FastAPI 0.162.0, Pydantic 2.14.3, Starlette 1.10.0 y Uvicorn
0.54.0 ya estaban instalados. La compatibilidad se prueba ejecutando el código.
Starlette admite HTTPX con aviso de deprecación; no se ocultó el aviso ni se
introdujo HTTPX2 sin aprobación.

50 pruebas específicas PASS: entradas válidas/límites, campos prohibidos,
offsets, 422/503/500, logs sin secretos, readiness, cierre del contexto,
integridad previa a pickle y cambio de alias durante descarga.
Suite serving: 552 PASS y un fallo de permisos del sandbox al cerrar el
servidor sintético de T18; la prueba fallida se repitió fuera del sandbox y
pasó (1 PASS): **553 casos verificados**. Se limpió el proceso sintético propio
comprobando PID, padre y token. Suite nativa: **501 PASS, 10 omisiones** por
dependencias de serving/MLflow ausentes. Wheel instalado fuera de `src`, sin
datos reales: **51 PASS**, incluidas 43 importaciones aisladas. Ruff/formato
(88 archivos) y `pip check` de ambos entornos PASS. Los otros avisos son dos
de MLP en fixtures pequeñas, una deprecación SQLAlchemy y un aviso de caché
en el reintento entre usuarios de Windows; no se ocultaron.

Wheel probado: SHA-256
`afa70a2f4c59ea1401dd6e653181605815657c12838220eae2b3fe9b9b829a7e`.
**T20, T21 y T22: CIERRE TÉCNICO PASS.** Revisión humana de resultados
independiente; T23–T25 y G4 pendientes. Esta entrega no crea commit ni push.

Auditoría real `reports/serving/t20-t22/audit.json` (local, ignorada): seis
predicciones internas de smoke y cinco predicciones REST coinciden exactamente;
el sexto caso, origen 999999, recibe 422 conforme al nuevo contrato REST.
Registry SQLite sin cambios lógicos: cuatro runs, cuatro versiones y champion 4.
Hashes de linaje, modelos, evaluaciones, locks y recibos anteriores intactos.
Transporte REST probado con TestClient; MLflow por HTTP loopback. No acredita
Docker, reinicio de Compose, carga/latencia sostenida ni G4.

Comandos de verificación:

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv-mlflow\Scripts\python.exe -m pytest -q tests/api tests/unit/test_model_loader.py
.\.venv-mlflow\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q
```

Referencias de implementación: [Pydantic estricto](https://pydantic.dev/docs/validation/latest/concepts/strict_mode/),
[TestClient de Starlette](https://www.starlette.io/testclient/),
[descarga de artefactos MLflow](https://mlflow.org/docs/latest/api_reference/python_api/mlflow.artifacts.html).
La implementación fijada 3.16.1 requirió configurar también los URI globales
del SDK para resolver su logged model anidado en Windows; se verificó con el
Registry real sin modificar su configuración ni sus artefactos.
