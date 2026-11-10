# Runbook local — T35–T38

Estado técnico y evidencia: [cierre](../reports/final/completion.md).
Champion real LightGBM **v4**; v5 fue rechazado por T34. Los ejemplos
TEST_ONLY no autorizan una promoción real. Revisión cruzada por otro
integrante y defensa académica: **NO VERIFICADAS**.

## Requisitos y bootstrap

Windows x64, PowerShell, Git y Python **3.14.7**; Docker Desktop/WSL2 en modo
Linux para Compose. Trabajar desde la raíz. No hace falta activar el venv
ni modificar la política de ejecución. Clonar Git aporta código/configuración,
no Parquet, modelos, SQLite, recibos locales ni caché de wheels.

Para pruebas técnicas sin datos reales, el entorno de serving contiene
MLflow, LightGBM, FastAPI y Pytest. En una máquina nueva, obtener los wheels
del lock requiere red y presupuesto propios; la reproducción T37 usa solo
la caché ya aprobada. No regenerar locks para resolver una instalación fallida.

```powershell
py -3.14 --version
py -3.14 -m venv .venv-mlflow
py -3.14 -c "from pathlib import Path; from scripts.reproduce_local import tool_lock; p=Path('.cache/repro-tools.lock'); p.parent.mkdir(exist_ok=True); p.write_text(tool_lock(Path.cwd()), encoding='utf-8')"
.\.venv-mlflow\Scripts\python.exe -m pip --isolated install --require-hashes --only-binary=:all: -r .cache/repro-tools.lock
.\.venv-mlflow\Scripts\python.exe -m pip --isolated install --require-hashes --only-binary=:all: -r requirements-serving.lock
.\.venv-mlflow\Scripts\python.exe -m pip --isolated install --no-index --no-deps --no-build-isolation .
.\.venv-mlflow\Scripts\python.exe -m pip check
.\.venv-mlflow\Scripts\python.exe -m pytest -q
```

El build local necesita setuptools/wheel ya disponibles. El procedimiento
automático siguiente instala esas herramientas desde los cuatro bloques
históricos de requirements-dev.lock, sin cambiar versiones. Separa el entorno
de reportes Evidently/pandas 2.3.3; no mezclarlo con serving/pandas 3.1.1.

```powershell
py -3.14 -m scripts.reproduce_local --output-dir .cache/repro-nueva
```

El destino debe ser nuevo. El export incluye los cambios locales sin commit,
manifiesto SHA-256 y tests; excluye datasets, pesos, bases, secretos, entornos
y PDF nuevo no versionado. No contiene .git: es una fotografía del árbol
de trabajo, **no un clon del main remoto**. Se crea un venv limpio y se usan
wheels exactos de .cache/t29-t31/wheels-windows, .cache/wheels y .cache/t18/wheels
con --no-index/--require-hashes. Si falta uno, falla; no descarga ni cambia pins.
Logs, wheel y resultado quedan bajo el destino. Esta prueba automatizada no
acredita que otro integrante haya ejecutado el proyecto.

## Datos y modelos reales

Mantener raw/YYYY/MM/yellow_tripdata_YYYY-MM.parquet dentro de data/, sin
editar bytes. Los archivos aportados tienen procedencia LOCAL_UNVERIFIED;
los seis de 2026 descargados conservan URL/hash. Antes de features se exige
registro, esquema y D-04. Cada incumplimiento nuevo requiere aprobación
humana exacta por mes/hash/reporte; conserva FAIL y excluye filas inválidas.
No convertir un FAIL global en PASS ni reutilizar una autorización para otro hash.

Consultar [contratos](t32-t34-retraining.md) y [evidencia T14](../reports/quality/t14_completion.md)
antes de ejecutar preparación. No repetir el holdout final para practicar.
Entrenamiento, validación, test y replay tienen cortes y roles diferentes.
Origen/calendario/pasajeros opcionales son features; destino solo segmenta
resultados y nunca entra al predictor. Timestamps históricos NY y etiquetas
UTC siguen la convención aprobada; horarios ambiguos/inexistentes se apartan.

Presupuestos: fit real 8 GiB libres/4 GiB RSS combinado; preparación 4/2;
evaluación 6/2; disco 50 GiB, hasta cuatro hilos y dos horas por modelo.
Demo T35/T36: 4 GiB libres, 2 GiB RSS combinado, 50 GiB disco, un escenario
y 20 minutos. Medición cooperativa, no límite duro del sistema operativo.
Si falla el preflight o se excede un límite, detener y revisar; no reducir
datos ni subir presupuesto automáticamente.

## Arranque y comprobación del servicio real

MLflow nativo: 127.0.0.1:5000; Docker mantiene una copia aislada en 5001 y
API en 8080. El puerto 8000 pertenece a otro proceso. No detenerlo.

Si el Registry nativo aprobado está detenido y el puerto 5000 está libre,
arrancarlo desde otra terminal con
`.\.venv-mlflow\Scripts\python.exe scripts/mlflow_server.py`.
No lanzar una segunda instancia sobre la misma SQLite si ya está en ejecución.

```powershell
.\.venv-mlflow\Scripts\python.exe -m src.training.champion --resolve
docker version
docker compose config --quiet
docker compose up -d --no-build --wait --wait-timeout 180 mlflow api
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/model-info
.\.venv\Scripts\python.exe scripts/smoke_api.py
```

Estos comandos requieren Registry/seed/imagen aprobados existentes; para
otra máquina seguir [bootstrap y backup T23–T25](t23-t25-docker.md).
No reinicializar el volumen actual ni copiar SQLite abierta con Copy-Item.
Health/model-info: 200 con champion válido; 503 si no se puede cargar.
Predict inválido: 422. Modelo cargado al inicio, sin recarga automática.
Cambiar un alias por sí solo no cambia una API ya cargada.

## Promoción y rollback controlados

La aprobación inicial v1 de configs/champion.yaml sigue intacta. Una operación
futura necesita paquete de aprobación v2 independiente: usuario/alcance,
operation_id único, hash de aprobación previa, Registry/versión/run/familia,
pesos y mapa completo de artefactos, fingerprints de parámetros/métricas,
gate/evaluación por hash y smoke esperado. Debe existir gate recalculable
ELIGIBLE_FOR_HUMAN_REVIEW y aprobación humana propia; v5 no cumple el gate.
Para operación real, la identidad del champion evaluado debe coincidir con
el nombre/versión/hash del estado anterior que se pretende reemplazar.
Los archivos locales son recibos auditables, no firmas criptográficas humanas.

Usar una configuración activa separada y una API creada por ManagedAPI.
Su recibo incluye token, PID, directorio, puerto y ruta activa; se cotejan
con identidad y comando del proceso. No se adopta un PID solo por su puerto.
El mecanismo no controla la API Docker existente y no migra su volumen.
Para una promoción real futura habrá que aprobar y provisionar ese controlador.

Consultar la interfaz sin efectuar cambios:

```powershell
.\.venv-mlflow\Scripts\python.exe -m src.retraining.promote --help
.\.venv-mlflow\Scripts\python.exe -m src.retraining.rollback --help
```

El CLI de promoción recibe --approval, --active, --controller y --root;
rollback recibe --operation, --controller y --root. --test-only exige raíz
marcada TEST_ONLY y namespace synthetic-, nunca usa puertos protegidos.
La demo crea todos esos recibos de manera aislada:

```powershell
.\.venv-mlflow\Scripts\python.exe -m scripts.demo_lifecycle --output-dir .cache/demo-lifecycle-nueva --external-rollback
```

Diario encadenado tracking/lifecycle/<operation>/NNNN.json: PREPARED,
ALIAS_APPLIED, APPLIED, VERIFIED; ante fallo, FAILED/ROLLED_BACK. Se guardan
bytes previos y aliases. Rollback verifica el paquete previo, restaura bytes
exactos/alias, reinicia su API y comprueba predicción/versión por HTTP.
No borra modelos. Cambios concurrentes ajenos producen CONFLICT y revisión;
no se promete transacción distribuida ni compare-and-swap del Registry.

Si cae el controlador, recuperar con el recibo original y CLI de rollback.
--recover-stale-lock solo archiva un lock cuyo PID ya no existe; si está vivo
o fue reutilizado, bloquea. No eliminar locks manualmente ni matar procesos
desconocidos. Conservar diarios, logs y recibos para investigar fallos parciales.

## Workflow manual T36

El grafo prepare → train → validation → register → final → compare exige
trigger, autorización acotada y publicación completa de cada etapa. Sin
trigger no entrena; registra candidato sin alias y no incluye promoción.
La CLI pública planifica/verifica evidencia existente; una nueva campaña real
requiere aprobación independiente. No se añadió workflow remoto de retraining.
resume exige las seis etapas completas con hashes válidos; una campaña parcial
o alterada bloquea y requiere revisión, sin reejecución automática de etapas.

```powershell
.\.venv-mlflow\Scripts\python.exe -m src.retraining.evaluate --help
.\.venv-mlflow\Scripts\python.exe -m scripts.demo_workflow --output-dir .cache/demo-workflow-nueva
```

La demo usa 48 filas sintéticas de train, evalúa y registra en MLflow aislado;
NOT_EVALUABLE por segmentos pequeños es el resultado correcto, no un permiso
de promover. La campaña real reutilizada está documentada en
[trazabilidad](../reports/final/traceability.md); no se repitieron fits ni holdout.

## Incidentes, limpieza y revisión humana

Si falta RAM/disco, cerrar aplicaciones propias o pedir revisión del perfil.
Si un puerto está ocupado, elegir uno libre para la demo; no detener terceros.
Si falta wheel/hash coincide mal, parar y revisar caché/lock. Si falta seed,
no iniciar Registry vacío como sustituto. Si el gate rechaza, conservar v4.

En la reproducción final se conservó un timeout de arranque de API sintética
a los 90 segundos. La carga directa posterior y la repetición HTTP pasaron
con los mismos bytes/versión/presupuesto; no se confirmó la causa raíz.
No aumentar el timeout ni convertir el fallo en PASS silenciosamente. Para
una repetición técnica autorizada, usar el venv del export, nuevos temporales,
logs/JUnit distintos y verificar al final que sus servicios propios se detuvieron.
Las fases de esta entrega cubren casos disjuntos: el caso HTTP repetido y
el resto de la suite. No se suman pruebas duplicadas ni se borra el primer FAIL.

docker compose stop detiene servicios conservando el volumen. down también
lo conserva por defecto; **no usar down -v**, prune o borrados recursivos
sin backup verificado y aprobación específica. Las demos detienen solo sus
procesos identificados y conservan directorios para auditoría.

Otro integrante debe clonar la revisión que se publique, registrar SHA,
SO/Python/locks/comandos/resultados y problemas, sin copiar datos/credenciales
al repositorio. Firmar esa revisión y realizar la defensa son acciones humanas
pendientes; no se sustituyen por la suite automatizada.
