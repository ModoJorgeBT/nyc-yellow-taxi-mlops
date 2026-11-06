# D-07 — Propuesta local para T18

**Estado: APROBADA, IMPLEMENTADA Y VERIFICADA; cierre técnico T18 PASS. Fecha: 2026-11-05.**

Registro: «Sí, aprobar D-07 y ese alcance de T18». Incluye consultar metadata,
resolver hashes e instalar exclusivamente en el entorno separado. No concede
promoción ni ampliación a otros sprints.

T18 registrará los resultados ya auditados y los modelos congelados de baseline,
SGD, MLP y LightGBM. El registro no ajustará modelos ni asignará un champion.
T19 conserva la decisión explícita de promoción.

## Entorno y dependencias

Se propone un entorno **`.venv-mlflow` separado**, con Python 3.14.7 y MLflow
**3.16.1 como versión candidata a verificar**. Se resolverán versiones y hashes
en `requirements-mlflow.lock` antes de instalar exclusivamente wheels.
La compatibilidad completa con Windows/Python 3.14 todavía no está verificada.
Una resolución imposible o un aviso de seguridad aplicable detendrá el paso para
revisión; no se cambiará silenciosamente Python ni la versión de MLflow.

Motivo del aislamiento: la metadata revisada de MLflow 3.16.1 exige
`pyarrow<26`, mientras el entorno de preparación/modelado usa PyArrow 26.0.1.
Se propone PyArrow **25.0.0 solo dentro del nuevo entorno**, condicionado a que
exista wheel compatible. No se alterarán `.venv`, `.venv-verify` ni el lock de
24 paquetes que reprodujo el entrenamiento y las evaluaciones.

Se conservarán en el entorno nuevo las versiones de inferencia existentes:
NumPy 2.5.4, SciPy 1.18.1, scikit-learn 1.9.1, joblib 1.6.0,
threadpoolctl 3.7.0, LightGBM 4.7.0 y tzdata 2026.6.
La resolución fijará además las transitivas de MLflow, incluidas pandas,
Pydantic, SQLAlchemy, Alembic y sus componentes HTTP. Su instalación quedaría
limitada a T18; no implementa la API del proyecto.

Historial anterior a la aprobación de D-07: la consulta adicional de metadata de PyPI no fue
autorizada. No se ejecutó una instalación ni se afirma haber resuelto el lock.
La aprobación posterior del usuario incluyó esa verificación de metadata y
descarga de paquetes; después se resolvieron hashes e instalaron los 95 paquetes en el entorno aislado.

Referencias primarias: [metadata de MLflow 3.16.1](https://pypi.org/pypi/mlflow/3.16.1/json)
y [metadata de PyArrow 25.0.0](https://pypi.org/pypi/pyarrow/25.0.0/json).

## Servicio y persistencia

- Servidor local accesible únicamente en `http://127.0.0.1:5000`.
- Backend de tracking y Registry SQLite explícito: `tracking/mlflow.db`.
- Artefactos servidos por MLflow desde `tracking/artifacts/`, fuera de Git.
- Un proceso servidor y un cliente a la vez; registro secuencial de los modelos.
- Sin FileStore de metadatos, servicios cloud ni exposición en interfaces públicas.
- El reinicio conservará la misma base y artefactos; no se borrará un almacén
  existente ni se migrará una base ajena automáticamente.
- Compose completo permanece en T24. T18 prueba primero el servicio local.

Este diseño sigue el [servidor de tracking documentado por MLflow](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/).
El presupuesto de preparación 4 GiB libres/2 GiB RSS se mantendrá para el
cliente; cualquier ampliación de recursos requerirá consulta. La verificación
incluirá consumo del servidor, sin declarar un límite duro del sistema operativo.

## Registro y contrato de predicción

Experimento propuesto: `nyc-yellow-taxi-duration`. Nombre estable de Registry:
`nyc-yellow-taxi-duration`. Se crearán cuatro versiones candidatas con tags
`family=baseline|sgd|mlp|lightgbm`, SHA-256 del modelo y del linaje, sin alias
`champion` ni `challenger` operativos.

Se registrarán configuración, semillas, rango train, hashes de datos y splits,
locks, versión del software evaluado, commit y estado sucio del árbol. El registro
es posterior al entrenamiento: no se atribuirán estas ejecuciones de MLflow a
la fecha histórica del fit. Métricas separadas por ventana: validation 2025,
test original 2025 y final independiente 2026, según su existencia real. MLP no
tiene evaluación final 2026 autorizada; se marcará esa ausencia.

Los Pipelines existentes reciben registros Python, por lo que el modelo MLflow
necesita un adaptador `pyfunc` que convierta la tabla de entrada a ese mismo
contrato. Se propone conservar origen, timestamp con offset y pasajeros
opcionales; normalizar la representación tabular de ausentes a `None` y enteros
opcionales a `int`. No se habilitarán destino ni variables posteriores al viaje.
El adaptador llamará al Pipeline congelado sin hacer `fit`, y el baseline usará
su constante ya congelada. El artefacto joblib/JSON original conservará su hash.

La firma y el ejemplo de entrada usarán únicamente payloads sintéticos. Se
compararán sus predicciones con el entorno original para detectar diferencias
introducidas por la envoltura o el entorno. No se recalcularán ni elegirán
modelos a partir del holdout ya consumido.

## Archivos previstos y aceptación

Archivos: `src/training/tracking.py`, adaptador de inferencia MLflow separado,
`configs/tracking.yaml`, `requirements-mlflow.in`, `requirements-mlflow.lock`,
scripts de arranque/verificación, tests de tracking e integración, y
`docs/t18-mlflow.md`. Se actualizarán `.gitignore`, `.env.example`, README y
el estado documental; sin cambiar los contratos congelados de modelado.

Pruebas necesarias:

1. Resolución con hashes y wheels de Windows/Python 3.14; `pip check` del nuevo
   entorno; los dos entornos anteriores y su lock quedan intactos.
2. Runs con parámetros, métricas, artefactos y linaje comprobables; las cuatro
   familias tienen una versión candidata enlazada al run correcto.
3. Carga desde el Registry por nombre y versión exacta; payloads sintéticos
   predicen igual que los modelos originales, sin entrenar ni habilitar destino.
4. Rechazo de modelo, reporte o linaje alterados; reintentos sin duplicación
   silenciosa de registros completados.
5. Detener y reiniciar únicamente el servidor creado por la prueba: mismos run
   IDs/versiones, artefactos descargables con hashes originales y mismas
   predicciones. No se elimina la base para simular un reinicio.
6. Ningún alias de champion asignado ni cambiado. Sin modelo promovido, API,
   Docker Compose ni CI declarados operativos.

La aprobación requerida comprende el entorno aislado, dependencias fijadas,
servicio loopback con persistencia y registro de los cuatro candidatos. Los
fallos de compatibilidad o decisiones fuera de ese perfil se consultarán.


## Resultado de la ejecución aprobada

Cuatro candidatos registrados y auditados; persistencia real después de reiniciar
verificada sin duplicados ni alias. [Informe](../reports/tracking/t18_completion.md)
y [guía](t18-mlflow.md). Las formulaciones anteriores conservan la propuesta
aprobada; su estado de ejecución actual es el indicado aquí.
