# Propuesta de ejecución T23–T25 — 2026-11-09

Estado: APROBADA explícitamente por el usuario el 2026-11-09.
El usuario instaló Docker Desktop con WSL2 durante las tareas y autorizó la
preparación/ejecución. Aprobó posteriormente la auditoría portable de metadatos
y API en 8080 para preservar el proceso que ocupa 8000. [Resultado](t23-t25-docker.md).
El usuario autorizó trabajar en T23–T25; no se instalará infraestructura de
Windows ni se alterará el Registry histórico sin autorización específica.

## Hallazgos

Docker CLI 29.9.2 y Compose 5.6.1 existen, pero `docker version` no encuentra
el motor. No existe Docker Desktop en su ruta habitual y `wsl --status`
informa que WSL no está instalado. Por tanto, build, contenedores, volúmenes
y reinicios todavía NO VERIFICADOS.

El lock serving de 97 paquetes fue resuelto en Windows: incluye pywin32 y
no acredita las dependencias condicionales de Linux. El modelo/recibo T19
fijan la identidad y hashes aprobados y su URI histórica loopback. Dentro
de Compose, `127.0.0.1` de la API no es el contenedor MLflow. El MLflow
nativo usa actualmente el puerto 5000.

## Perfil propuesto

- Imagen oficial Python 3.14.7 slim Bookworm, Linux amd64, fijada por digest
  verificado; usuario sin privilegios. Lock Linux separado con hashes,
  preservando versiones compatibles y los locks históricos. Documentar y
  consultar cualquier incompatibilidad o cambio de versión necesario.
- Servicios API y MLflow, más CLI pipeline bajo perfil manual. Red interna
  Compose: `http://mlflow:5000`, permitida solo como transporte explícito del
  operador; conservar intactos elección, recibo y modelo T19.
- Copia aislada del Registry mediante backup SQLite consistente, artefactos
  con hashes y recibos intactos. Persistencia local separada para Compose;
  no compartir una SQLite activa entre Windows y Linux ni modificar su
  contenido para trasladarla. Las URI de artefactos existentes son relativas
  `mlflow-artifacts:/...` y permiten probar la copia sin reescribirlas.
- MLflow Docker publicado solo en `127.0.0.1:5001`, API en
  `127.0.0.1:8080`; MLflow nativo en 5000 permanece intacto. El cambio desde
  8000 fue aprobado después de detectar un proceso ajeno escuchando allí. Puertos
  configurables. API y MLflow con máximo 2 GiB/2 CPU cada uno y un worker;
  pipeline manual, sin entrenamiento durante estas tareas. Healthchecks y
  dependencia de MLflow saludable; no promocionar ni registrar modelos.
- Descargar únicamente la base, dependencias y paquetes del sistema de la
  imagen; ningún dataset. Propuesta de presupuesto de transferencia: hasta
  2 GiB para las capas base y ruedas Python; detener y revisar si no alcanza.
  Verificar al menos 50 GiB libres antes del build. Instalar libgomp para
  LightGBM dentro de la imagen con versión fijada; no modificar el host.

La habilitación de WSL2/Docker Desktop es una instalación del sistema y puede
requerir permisos de administrador/reinicio: se consultará quién la realiza.
La imagen y el lock Linux se verificarán antes de declarar compatibilidad.

## Archivos y aceptación

`Dockerfile`, `.dockerignore`, `docker-compose.yml`, lock Linux de serving,
`.env.example`, adaptador de transporte local de serving, preparación de la
copia de tracking, `scripts/smoke_api.py`, pruebas y guía de operación.

T23 exige build real e imagen arrancable. T24 exige `compose config`, MLflow
saludable y persistencia después de `down` sin `-v`. T25 exige predicciones
reales del champion v4 por HTTP, 422 inválido, 503 en instancia aislada sin
aprobación, identidad coherente y repetición tras reinicio. Auditar cuatro
runs/cuatro versiones, alias v4, modelos/recibos históricos intactos. Nunca
quitar el alias del Registry real para probar 503 ni ejecutar `down -v`.

Si el motor no está disponible, se entregarán únicamente las partes probadas
con ese límite explícito; T23–T25/G4 no se marcarán completadas por escribir
archivos o por una validación estática.
