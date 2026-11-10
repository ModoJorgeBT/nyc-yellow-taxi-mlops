# T23–T25 — Preparación y verificación Docker

Perfil aprobado explícitamente el 2026-11-09: [decisión](t23-t25-execution-proposal.md).
**T23, T24 y T25: CIERRE TÉCNICO PASS; G4 verificado técnicamente.** Docker
Desktop/WSL2 quedó operativo durante la tarea: motor 29.9.3 Linux amd64.
Imagen construida y servicios saludables. API: http://127.0.0.1:8080/docs;
MLflow Docker: http://127.0.0.1:5001. Revisión humana de resultados independiente.

## Entregables y pruebas realizadas

| Tarea | Preparado/verificado | Falta para cerrar |
|---|---|---|
| T23 | Build real, imports Linux, usuario 10001, dependencias fijadas y contexto por whitelist | Ningún requisito técnico de T23 pendiente |
| T24 | Compose válido; volumen inicializado, API/MLflow saludables, down/up sin pérdida; bootstrap posterior SKIPPED | Revisión humana |
| T25 | HTTP real 200/422, diez predicciones exactas, tres 503 aislados y auditoría del volumen tras reiniciar | Revisión humana |

Regresión final: **578 PASS** en `.venv-mlflow`; **525 PASS y 11 omisiones**
en `.venv` (dependencias opcionales ausentes). Incluye 23 casos nuevos de
preparación y dos del loader (transporte y metadatos generados). Se verificó
backup con WAL activo, valores IEEE-754 exactos y conservación de evidencia.
Ruff/formato (93 archivos) y pip check de ambos entornos PASS. Los avisos existentes
de Starlette/HTTPX, MLP con fixtures pequeñas y SQLAlchemy se conservan;
MLflow Linux también emite un aviso de deprecación WSGI, sin impedir el servicio.
El entorno Windows no instaló Gunicorn ni bibliotecas Linux.

HTTP nativo real: dos arranques de Uvicorn en loopback con el modelo aprobado,
diez predicciones exactas, dos rechazos de origen desconocido y dos de feature
prohibida. Otra instancia sin champion recibió tres 503; no se quitó el alias
real. Evidencia local ignorada: `reports/smoke/t23-t25/native-http.json`.
La SQLite original conserva el mismo contenido lógico.

## Imagen y dependencias

Linux amd64, Python 3.14.7 slim Bookworm, digest
`sha256:998acd06f485adfd6890e3e15a4b542543e0cf22ff904310095da328a5e3e561`.
`requirements-serving-linux.in/.lock` y
`configs/container-wheels-linux.json` fijan 99 ruedas compatibles por tags.
Se conservan las 95 versiones compartidas con el lock Windows; se excluyen
pywin32/colorama y se incluyen Gunicorn 26.2.0 y los tres paquetes de build ya
aprobados (pip, setuptools, wheel). Esto acredita disponibilidad de ruedas,
además de los smoke reales ya completados en Linux.

`configs/container-system-packages.json` fija gcc-12-base, libgcc-s1,
libgomp1 y libstdc++6 en 12.2.0-14+deb12u1, con hashes de Debian. No se instala
un compilador. Las entradas binarias base/ruedas/DEB suman **244.775.451 bytes**
(233,4 MiB) por obtención completa, bajo el presupuesto de 2 GiB. Los fetch
verifican tamaño/hash, rechazan divergencias y reutilizan archivos idénticos.
Los locks históricos permanecen intactos; no hay nuevas descargas de datasets.
El build comprueba 50 GiB libres; no se cambia automáticamente un pin si falla.

`.dockerignore` usa whitelist: envs, Git, cachés, datos, modelos, SQLite,
PDF y secretos del proyecto no entran al contexto. El modelo se obtiene del
Registry al arrancar y se verifica antes de deserializar.

## Persistencia y red

La preparación hace backup SQLite consistente y copia artefactos/recibos a
`.cache/compose-state/tracking`, verificando hashes y el contenido lógico.
Esa copia **ya está preparada en esta máquina**; no volver a sobrescribirla.
El perfil `bootstrap` la importa a un volumen Linux de Docker, con marcador
final; rechaza semillas alteradas y volúmenes incompletos. Si el volumen ya
tiene esa procedencia, no lo reinicializa. El MLflow del contenedor usa el
volumen Linux; nunca escribe la SQLite original de Windows.

La API monta solo los recibos de la copia como lectura y descarga por
`http://mlflow:5000`. El transporte explícito del operador no cambia los hashes
de elección/aprobación T19 ni permite una URL arbitraria desde HTTP.
El servidor exige seed verificado antes de iniciar; no crea un Registry vacío
silenciosamente. Puertos host: MLflow Docker 5001, API 8080, fixture 503 8001,
todos enlazados a `127.0.0.1`; MLflow nativo conserva 5000. El cambio de 8000
a 8080 fue aprobado para conservar el proceso Python ajeno que ocupa 8000.

API/MLflow: un worker, máximo 2 GiB/2 CPU por servicio, usuario 10001,
filesystem de imagen de lectura, temporales separados y sin capabilities.
API espera MLflow saludable mediante
[`service_healthy`](https://docs.docker.com/compose/how-tos/startup-order).
Inspección real PASS: 2.147.483.648 bytes y dos CPU por servicio, usuario
10001:10001, imagen de lectura y capabilities eliminadas. Jobs automáticos de
MLflow deshabilitados: esta entrega habilita tracking/Registry, no schedulers.
El job `pipeline` es manual y por defecto solo muestra ayuda de ingesta; no se
ha autorizado ni probado un entrenamiento Linux en estas tareas.

## Operación local verificada

Desde PowerShell en la raíz. Precondición: Docker Desktop en modo Linux y
`docker version` mostrando también **Server**. La copia preparada necesita
Registry T18 y champion T19 existentes: clonar Git no descarga modelos/SQLite.

```powershell
docker version
.\.venv\Scripts\python.exe scripts/container_build.py --preflight
docker compose --profile bootstrap --profile pipeline --profile smoke config --quiet
docker build --platform linux/amd64 -t nyc-taxi-api:local .
```

En otra copia del proyecto, preparar el seed una sola vez después de tener
el Registry aprobado. En esta máquina ese paso ya pasó:

```powershell
.\.venv-mlflow\Scripts\python.exe scripts/prepare_compose.py
```

Inicializar volumen y arrancar:

```powershell
docker compose --profile bootstrap run --rm --no-deps bootstrap
docker compose up -d --no-build --wait --wait-timeout 180 mlflow api
docker compose ps
.\.venv\Scripts\python.exe scripts/smoke_api.py
docker compose exec -T api python -m pip check
docker compose --profile pipeline run --rm --no-deps pipeline
```

MLflow Docker: http://127.0.0.1:5001; documentación API: http://127.0.0.1:8080/docs.
El smoke guarda un JSON nuevo por ejecución en `reports/smoke/api/`; no expone
credenciales ni modifica el Registry.

Reinicio y persistencia; `down` conserva los volúmenes por defecto, como
describe la [guía de Compose](https://docs.docker.com/compose/gettingstarted/).
**No usar `down -v`.**

```powershell
docker compose down
docker compose up -d --no-build --wait --wait-timeout 180 mlflow api
.\.venv\Scripts\python.exe scripts/smoke_api.py
```

Probar 503 sin alterar aliases. Primero detener la API normal para mantener
el presupuesto simultáneo de API/MLflow; la instancia de prueba no recibe
recibos ni volumen del Registry:

```powershell
docker compose stop api
docker compose --profile smoke up -d --no-build --wait --wait-timeout 90 api-unavailable
.\.venv\Scripts\python.exe scripts/smoke_api.py --url http://127.0.0.1:8001 --expect-unavailable
docker compose stop api-unavailable
```

Auditoría del volumen sin servidor activo, seguida de arranque normal:

```powershell
docker compose stop api mlflow
docker compose run --rm --no-deps mlflow python scripts/prepare_compose.py --audit-volume /app/tracking
docker compose up -d --no-build --wait --wait-timeout 180 mlflow api
```

La auditoría exige artefactos/recibos idénticos y el mismo contenido lógico
de SQLite: cuatro runs, cuatro versiones, champion 4. Toda divergencia detiene
el cierre para revisión; no se resuelve borrando el volumen ni cambiando la
aprobación. Este protocolo Docker se ejecutó y pasó. No hay commit/push nuevo
en esta continuación.

## Compatibilidad y auditoría final

El primer arranque bloqueó correctamente por una diferencia de representación:
SQLite Windows 3.50.4 y Linux 3.40.1 exportan los mismos doubles con textos
distintos. Se demostró primero que el archivo DB era idéntico por SHA-256.
La auditoría v2 conserva esquema y valores tipados exactos (floats IEEE-754 en
hexadecimal), ordenando filas sin redondear métricas. El usuario aprobó la
actualización de los metadatos de la copia Docker; DB, artefactos y recibos
no cambiaron. `compose-seed-v1.json` y los logs de rechazo se conservaron.
La referencia portable de los valores coincidió en ambos sistemas:
`8a19538436f1c86e13176d384c3d2efe9994f614323557733eff435f9aa187d9`.

MLflow genera `registered_model_meta` con saltos de línea del cliente. El
loader solo restaura una representación si su hash coincide exactamente con
el ya aprobado; luego verifica los 50 archivos completos antes de cargar.
No se normalizan código ni pesos ni se cambia el manifiesto T19.

Evidencia local ignorada: `reports/smoke/t23-t25/docker-audit.json` y los tres
smoke JSON. Volumen persistente `nyc-taxi-local_tracking-state`, conservado tras
`down`/`up`; bootstrap repetido SKIPPED; cuatro runs/versiones y champion v4
intactos. Auditoría nativa independiente de 28 archivos originales (modelos,
evaluaciones, linaje y locks) antes/después PASS; SQLite original sin cambios.
No se reentrenó, reajustó ni promovió otro modelo. API y MLflow Docker quedan
saludables; la instancia 503 se retiró. No se afirma CI, monitoreo ni rollback.
