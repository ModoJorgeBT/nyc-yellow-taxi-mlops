# T18 — Tracking y Registry locales

**Actualización posterior T19:** LightGBM v4 es ahora el champion inicial
aprobado. [Decisión y resolución](../reports/model_selection.md). Las pruebas
de T18 descritas aquí conservaron los cuatro candidatos sin alias en aquella
fase. Después de T19, consultar con `python -m src.training.champion --resolve`
en el entorno MLflow; no volver a registrar candidatos para consultar el estado.
El verificador histórico T18 rechaza cambios de alias frente a su snapshot;
el contrato T19 es el que valida la aprobación actual.

**Estado: CIERRE TÉCNICO PASS; registro real, persistencia y auditoría verificados.**
[Resultados, versiones y runs](../reports/tracking/t18_completion.md). Revisión humana independiente.
El usuario aprobó [D-07](d07-mlflow-proposal.md), incluido entorno aislado,
dependencias fijadas, servidor loopback, SQLite/artefactos persistentes y registro
de cuatro candidatos. La evaluación final independiente ya está
[completada y auditada](../reports/evaluation/lightgbm_final_evaluation.md).

## Entorno y límites

Python 3.14.7; MLflow 3.16.1, PyArrow 25.0.0 y 95 paquetes fijados con hashes en
[requirements-mlflow.lock](../requirements-mlflow.lock), a partir de
[requirements-mlflow.in](../requirements-mlflow.in). Se verificaron wheels
compatibles antes de instalar en `.venv-mlflow`, sin instalar desde fuentes.
El lock histórico de entrenamiento y sus 24 versiones no se modifican.
NumPy, SciPy, scikit-learn, joblib, threadpoolctl, LightGBM y tzdata conservan
las versiones usadas para entrenar; PyArrow 25 pertenece solo al entorno T18.
Compatibilidad local de tracking/Registry probada con fixtures y cuatro modelos reales; Docker/Linux sigue sin verificar.

Tracking y Registry comparten `tracking/mlflow.db`; artefactos en
`tracking/artifacts/`, servidos por HTTP. Todo `tracking/` y `.venv-mlflow/`
está fuera de Git. El servidor usa un worker, `127.0.0.1:5000` y backend SQLite
explícito. El cliente respeta preparación 4 GiB libres/2 GiB RSS/50 GiB disco y
supervisión cooperativa; no cambia el presupuesto de entrenamiento ni Docker.

## Revisión de avisos para el perfil aprobado

La [metadata oficial de MLflow 3.16.1](https://pypi.org/pypi/mlflow/3.16.1/json)
reporta tres avisos. CVE-2026-53995 requiere el backend FileStore, excluido aquí
mediante SQLite explícito. Los otros dos requieren integraciones adicionales:
[TruLens para el SSRF](https://github.com/mlflow/mlflow/security/advisories/GHSA-2wqp-q3c6-ccj5)
y [autologging CrewAI para la filtración de credenciales](https://github.com/mlflow/mlflow/security/advisories/GHSA-j7qq-vr8c-xvw3).
El lock no incluye esas dependencias; el cliente y el arranque rechazan un
entorno que las tenga instaladas, y este código no activa autologging.
Por esas condiciones, los avisos revisados no son aplicables al perfil concreto
aprobado. Esto no declara MLflow 3.16.1 libre de vulnerabilidades ni permite
exponerlo públicamente o añadir integraciones sin revisar la decisión.

## Implementación

- [tracking.py](../src/training/tracking.py): verifica aprobación, hashes,
  marcadores REAL/TEST_ONLY, enlaces entre ajuste y evaluación, y linaje antes
  de deserializar; registra parámetros, métricas por ventana/segmento y artefactos.
- [tracking_model.py](../src/training/tracking_model.py): adaptador tabular a la
  misma entrada de los Pipelines. Offset obligatorio, origen entero y pasajeros
  opcionales; no habilita destino. Verifica el SHA-256 antes de cargar joblib.
- [tracking.yaml](../configs/tracking.yaml): cuatro modelos y referencias
  congeladas, recursos y decisión D-07 explícita.
- [mlflow_server.py](../scripts/mlflow_server.py): arranque local con SQLite y
  artefactos persistentes; no crea un champion.
- [smoke_mlflow.py](../scripts/smoke_mlflow.py): registra, detiene únicamente su
  árbol de procesos identificado, reinicia conservando SQLite y verifica runs,
  versiones, artefactos, predicciones e idempotencia.

Registro posterior al entrenamiento: se conserva el commit disponible, estado
sucio, hash del código al registrar, lock T18 y versiones/hashes históricos en
los manifiestos originales. No se atribuye al fit el timestamp de este registro.
Las cuatro familias serán versiones candidatas del nombre
`nyc-yellow-taxi-duration`, con tag `family`, sin asignar alias champion.

Las métricas se separan en `validation_2025`, `test_2025` y `final_2026` según
su existencia real. LightGBM no tiene test original 2025; MLP no tiene evaluación
2026 autorizada. Sus ausencias no se completan con métricas inventadas.
Las métricas incluyen los 29 grupos de cada ventana; los manifiestos conservan
exclusiones, excepciones de calidad y procedencia LOCAL_UNVERIFIED de train.

Un registro completo verificado se reutiliza por huella de configuración. Un
intento remoto parcial bloquea nuevos runs automáticos hasta revisar su estado.
El Registry guarda versiones candidatas; resolver un champion sigue en T19.

## Comandos implementados y verificados

El perfil exige los modelos y manifiestos locales congelados; clonar el
repositorio no los crea. Con el entorno original T03 disponible para construir
el paquete, la instalación aislada usa:

```powershell
python -m venv .venv-mlflow
.\.venv\Scripts\python.exe -m pip download --require-hashes --only-binary=:all: --dest .cache/t18/wheels -r requirements-mlflow.lock
.\.venv-mlflow\Scripts\python.exe -m pip install --no-index --find-links=.cache/t18/wheels --require-hashes --only-binary=:all: -r requirements-mlflow.lock
.\.venv\Scripts\python.exe -m pip wheel --no-deps --no-build-isolation --wheel-dir .cache/t18/dist .
.\.venv-mlflow\Scripts\python.exe -m pip install --no-deps --no-index .cache/t18/dist/nyc_yellow_taxi_mlops-0.1.0-py3-none-any.whl
```

Desde la raíz del proyecto, con el lock instalado en `.venv-mlflow` y el paquete
del proyecto instalado sin dependencias adicionales:

```powershell
# Variables para cada terminal; .env.example no se carga automaticamente
$env:MLFLOW_DISABLE_TELEMETRY='true'
$env:PYTHONUTF8='1'
# Servidor local, en una terminal propia
.\.venv-mlflow\Scripts\python.exe scripts/mlflow_server.py
# Cliente, en otra terminal; no entrena ni promueve
.\.venv-mlflow\Scripts\python.exe -m src.training.tracking
# Smoke de registro/reinicio: exige puerto libre y detiene solo su servidor
.\.venv-mlflow\Scripts\python.exe scripts/smoke_mlflow.py
```

No ejecutar simultáneamente servidor manual y smoke sobre el mismo puerto.
El smoke no borra la base ni los artefactos; al terminar detiene su servidor.
Compose, REST, CI, drift y promoción permanecen en sus tareas posteriores.

## Evidencia verificada

488 pruebas PASS en el entorno histórico y una integración omitida porque allí
no se instaló MLflow. 489 pruebas PASS sobre el wheel en el entorno separado,
incluida la integración HTTP/reinicio; 39 imports aislados. Cuatro modelos reales
registrados, descargados y cargados; parámetros/métricas/artefactos contrastados
con SQLite por una auditoría independiente. Reinicio real sin perder runs,
versiones ni artefactos; reintento completo idempotente y ningún alias asignado.
[Evidencia completa](../reports/tracking/t18_completion.md).

Al cierre el servidor real permanece activo en `http://127.0.0.1:5000`.
Su identidad propia y logs están en `.cache/t18/real-server-state.json`.
No iniciar otro proceso sobre ese puerto. Los servidores manuales se detienen
desde su terminal; para un proceso administrado debe verificarse su identidad
antes de detener exclusivamente su árbol. El sandbox de Windows requiere
permiso para esa operación; no cambiar ACL ni detener procesos ajenos.

El SDK puede descartar columnas adicionales antes de llamar a un modelo con
firma. El adaptador rechaza extras que le lleguen; el contrato REST estricto,
incluido el rechazo de campos no permitidos, corresponde a T20.

El backend opcional de jobs de MLflow no funciona en Windows y no se usa aquí.
La prueba no acredita Docker/Linux ni implementación de API/CI/monitoreo. T19
requiere una decisión humana de champion; los cuatro registros siguen candidatos.
