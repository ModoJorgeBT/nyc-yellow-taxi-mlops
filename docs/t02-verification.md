# T02 — Preparación y verificación de estructura

Fecha: 2026-11-03, America/Costa_Rica. Estado técnico: VERIFICADO. Cierre humano: APROBADO por el usuario al solicitar T03. Este archivo conserva la evidencia de T02: estructura y Git local en `main`, sin commits ni publicación, instalaciones ni procesamiento de datasets durante esa tarea. La continuación autorizada tiene su [evidencia T03](t03-environment.md).

## Entregables

Paquetes vacíos `src` y sus ocho módulos previstos; carpetas de pruebas, configs, scripts, notebooks, reports, raw/validated/processed y workflows con marcadores. [README](../README.md), [.gitignore](../.gitignore) y [.env.example](../.env.example) describen estructura, datos locales y configuración propuesta. Los inicializadores no implementan comportamiento.

La carpeta [data/raw](../data/raw) está preparada para los Parquet aportados por el equipo. Se colocarán por año/mes; tenerlos no acredita procedencia, calidad, periodos aprobados ni ingesta exitosa. El perfilado se hará únicamente en la tarea autorizada correspondiente.

## Criterios de aceptación y evidencia

| Comprobación | Estado |
|---|---|
| Estructura y marcadores presentes | PASS: nueve inicializadores y once carpetas con `.gitkeep`. |
| Importación de los nueve paquetes sin dependencias externas | PASS: imports con `python -B`; AST confirma solo docstrings en inicializadores. |
| Git local en main, sin commits ni remotos | PASS: `git init -b main`; rama main; cero commits, remotos y archivos en índice. |
| Datos/secretos/artefactos excluidos y plantilla/marcadores permitidos | PASS: 33 rutas protegidas y 13 rutas permitidas mediante `git check-ignore --no-index --stdin -z`; revisión de `git status` y `git ls-files`. |
| Sin rutas absolutas Windows en archivos del proyecto | PASS: revisión de los ocho Markdown, `.env.example`, `.gitignore` y nueve inicializadores. Las rutas usadas para seleccionar el intérprete en la auditoría no se guardaron como configuración del proyecto. |
| Enlaces Markdown válidos y PDF intacto | PASS final: ocho Markdown y 39 enlaces locales comprobados; SHA-256 del PDF coincide con el registrado en T01. |
| Disponibilidad de Pytest | Consultada previamente: 9.2.0; no acredita suite exitosa. |
| Instalación reproducible, suite funcional, Docker y CI | NO EJECUTADOS; corresponden a tareas posteriores. |
| Cierre humano de T01/T02 | APROBADO explícitamente por el usuario el 2026-11-03, después de presentar estos resultados. |

## Comandos y resultados

Se ejecutaron `git init -b main`, `git symbolic-ref --short HEAD`, `git rev-list --all --count`, `git remote`, `git ls-files` y `git status --short --untracked-files=all`. Resultado: rama `main`, cero commits/remotos/archivos en índice; 31 archivos públicos aparecen como no rastreados. Ese estado es esperado al no haber commits; no se exige un árbol limpio ni se añaden archivos al índice para simularlo.

La importación de `src` y sus ocho subpaquetes se ejecutó con un intérprete existente Python 3.14.7 y `-B`, sin instalar dependencias ni generar bytecode. Se inspeccionó su AST y se comprobaron once marcadores de carpetas. No se fija esa versión como versión del proyecto.

Se ejecutó `python -m pytest --version` con el intérprete existente: `pytest 9.2.0`. No se ejecutó una suite funcional ni se afirmó que hubiera tests verdes.

Para probar `.gitignore` se suministraron rutas representativas, sin crear archivos de datos o secretos. Se verificaron raw/validated/processed, Parquet fuera de fixtures, `.env` y variantes, credenciales locales, modelos, tracking/SQLite, reportes generados y caches; también se comprobó que plantilla, marcadores, documentación y futura fixture sintética permanezcan permitidos. La comprobación inicial por stdin en modo texto no pasó por el formato de entrada; se corrigió usando delimitadores NUL (`-z`, bytes), sin cambiar las reglas. La repetición pasó los 46 casos.

La verificación documental mediante `node -e` y módulos integrados comprobó UTF-8, bloques cerrados, enlaces locales, ausencia de rutas Windows absolutas, dependencias T04/T03, T12/D-06 y T34/T25, criterios de corte T14, precondición de MLflow T18 y muestra local T05. También comprobó D-01…D-08, gates sin marcar y PDF intacto. No se renderizó Mermaid ni se probaron servicios.

## Límites

Durante T02 no se eligió una versión de Python ni se crearon pyproject, lock, fixtures, YAML de modelos, Dockerfile, Compose o workflows. Sus comprobaciones no acreditaban una suite funcional. Después se autorizó T03 y la organización/revisión de los archivos aportados; sus resultados se registran aparte. No se creó un remoto GitHub ni se promovieron modelos. G0/G1 no se cierran por esta estructura.
