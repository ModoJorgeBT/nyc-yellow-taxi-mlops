# T03 — Entorno Python y calidad de código

Fecha: 2026-11-03, America/Costa_Rica. Estado técnico T03: VERIFICADO; el usuario autorizó después continuar con T04/T05. Este archivo conserva evidencia histórica de T03 (entorno y metadatos). La continuación está en [T04/T05](t04-t05-verification.md); no implica aprobación del stack completo ni de sprints posteriores.

**Entorno vigente, 2026-11-05:** después se aprobaron scikit-learn/tzdata y LightGBM 4.7.0. El lock vigente tiene 24 paquetes; añadir LightGBM conservó las 23 versiones previas. La extensión pasó 447 pruebas en desarrollo y 447 desde wheel instalado, con 35 imports aislados. La evidencia de quince paquetes que sigue corresponde al snapshot T03. [Alcance de modelado actual](t16-t17-validation.md).

## Versiones y alcance

| Componente directo | Versión fijada |
|---|---|
| CPython 64 bits | 3.14.7 |
| pip | 26.2.1 |
| setuptools | 84.2.1 |
| wheel | 0.48.0 |
| Ruff | 0.17.3 |
| Pytest | 9.2.0 |
| pip-tools | 7.6.2 |
| PyArrow | 26.0.1 |

Fuentes de configuración: [pyproject.toml](../pyproject.toml), [.python-version](../.python-version), [requirements-dev.lock](../requirements-dev.lock). El lock incluye 15 paquetes externos con versiones transitivas y hashes. El paquete local `nyc-yellow-taxi-mlops==0.1.0` se instala aparte, sin resolver dependencias. No se instaló MLflow/FastAPI ni bibliotecas de modelado pendientes.

Python se limita a la rama 3.14 en el metadata del proyecto; la versión exacta reproducida es 3.14.7. El lock se generó bajo Windows/CPython 3.14. No se declara validado en Linux, Docker ni otra versión de Python, ni compatible con el futuro stack completo. El código aún no tiene commit por instrucción del usuario; el lock fija dependencias, no sustituye una revisión de código identificada.

## Reproducir instalación y comprobaciones

Los comandos se ejecutan desde la raíz en PowerShell. Elegir el intérprete 3.14.7; `py -3.14 --version` permite comprobarlo. Si el alias no funciona, seleccionar el intérprete en VS Code. No se guardan rutas absolutas específicas de esta máquina en el proyecto.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip --isolated install --require-hashes --only-binary=:all: --index-url https://pypi.org/simple --cache-dir .cache/pip -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip --isolated install --no-index --no-deps --no-build-isolation -e .
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Crear `.venv` solo si no existe. No se requiere activación ni cambiar la política de PowerShell. Ruff revisa Python y pyproject, excluyendo datos, cachés y reportes; no reformatea ejemplos normativos de Markdown. Pytest usa importlib, configuración estricta y temporales/caché bajo `.cache`, reservado para archivos desechables de herramientas.

La prueba [test_installation.py](../tests/unit/test_installation.py) importa los nueve paquetes en un subprocess con `-I`, desde un directorio de prueba sin fuentes. Así detecta que una instalación no incluya módulos que los imports desde la raíz podrían ocultar. Es una prueba de empaquetado, no una prueba ficticia de modelo o de datos.

## Generación del lock

Con herramientas aprobadas instaladas en el entorno de mantenimiento:

```powershell
.\.venv\Scripts\python.exe -m piptools compile --extra dev --extra data --extra features --extra boosting --allow-unsafe --strip-extras --generate-hashes --index-url https://pypi.org/simple --no-emit-index-url --no-emit-trusted-host --cache-dir .cache/pip-tools --output-file requirements-dev.lock pyproject.toml
```

`--allow-unsafe` es el nombre histórico de la opción de pip-tools que incorpora pip/setuptools al lock; no desactiva la verificación de hashes. Las versiones directas están fijadas en pyproject y las transitivas en el lock. Al cambiar dependencias hay que regenerar y revisar el lock y repetir su instalación limpia; no añadir paquetes sin registrar aprobación cuando corresponda.

Referencias del mecanismo: [pip-compile](https://pip-tools.pypa.io/en/latest/reference/pip-compile/) y [compatibilidad de PyArrow](https://arrow.apache.org/docs/python/install.html). El funcionamiento local se comprueba con la evidencia de ejecución, no solo con la documentación.

## Segunda instalación limpia

Se descargaron las 15 distribuciones con `--require-hashes --only-binary=:all:` hacia `.cache/wheels`. Se creó `.venv-verify` con el mismo intérprete y sin paquetes del entorno de desarrollo. Se instalaron desde esos wheels con `--no-index --require-hashes --force-reinstall`, incluyendo pip/setuptools fijados. La repetición no necesitó red.

Se construyó el wheel local con `pip wheel --no-index --no-deps --no-build-isolation --wheel-dir .cache/dist .` y se instaló en `.venv-verify` como distribución normal, sin editable. Se comprobó la importación aislada, Ruff y `pip check`. `.venv-verify`, `.cache`, wheels y binarios quedan excluidos de Git; no son entregables que deban subirse.

La instalación normal desde PyPI sigue necesitando conectividad; la repetición offline es posible si se conserva la caché local de wheels verificados. No se presenta como prueba en una segunda máquina: se hizo en un segundo entorno limpio de la misma máquina Windows.

## Evidencia y límites

| Comprobación | Resultado observado |
|---|---|
| Entorno `.venv` con paquetes aprobados | Instalado, proyecto editable sin resolver dependencias adicionales. |
| Lock de dependencias | 15 paquetes fijados, hashes verificados al descargar e instalar. |
| Segundo entorno `.venv-verify` | Instalación offline limpia desde lock y wheel local. |
| `pip check` | Sin dependencias rotas en ambos entornos. |
| Ruff lint | PASS. |
| Ruff formato | PASS: diez archivos de Python/TOML revisados. |
| Pytest, editable | Una prueba de empaquetado aprobada. |
| Pytest, wheel en entorno limpio | Una prueba de empaquetado aprobada. |
| Dataset y repositorio | PASS: 24 Parquet en rutas previstas y hashes conservados durante organización; 31 rutas reales/representativas excluidas; Git en main, sin commits/remotos/índice. |
| Empaquetado y versiones | PASS: wheel solo contiene nueve paquetes y dist-info; las versiones de los 15 externos coinciden con el lock en ambos entornos, sin paquetes ajenos. |
| Documentación y PDF | PASS: diez Markdown, referencias locales comprobadas, bloques/UTF-8 correctos y PDF con SHA-256 original. |
| Continuación humana desde T03 | Usuario solicitó avanzar a T04/T05 tras estos resultados; la evidencia y decisiones de esas tareas se registran aparte. |

Incidentes reales: la primera descarga fue bloqueada por red del sandbox y se repitió con autorización. La primera prueba falló al acceder al temporal de Pytest externo al proyecto; se configuraron temporales/caché bajo `.cache`. Al alternar ejecuciones dentro/fuera del sandbox hubo permisos de limpieza y advertencias de caché; las repeticiones autorizadas aprobaron la prueba con una advertencia de caché que no cambia la aserción. Se conservan estos límites sin declarar como exitosas las ejecuciones fallidas. La ejecución inicial del formateador incluyó un ejemplo de spec.md; se restringió su alcance antes de aplicar cambios, sin modificar el target.

La verificación final usó directorios nuevos independientes por entorno para evitar mezclar permisos de cachés anteriores. Ambas ejecuciones finalizaron con `1 passed`, sin advertencias; Ruff indicó `All checks passed!` y `10 files already formatted`, y `pip check` indicó `No broken requirements found.` Los comandos finales de prueba fueron:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-dev-final -o cache_dir=.cache/pytest-cache-dev-final
.\.venv-verify\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-wheel-final -o cache_dir=.cache/pytest-cache-wheel-final
```

La auditoría final también comparó las 15 versiones y los hashes de sus wheels descargados con el lock, confirmó que el wheel local no incluye datasets ni directorios ajenos, y revisó exclusiones, referencias y PDF. Los resultados son de esta máquina; los temporales de herramienta se mantienen fuera de Git y no sustituyen pruebas en Docker u otra máquina.

## Revisión adicional de los datos aportados

Ver [inventario y hashes](../reports/raw_inventory.md). Los 24 archivos 2024/2025 se movieron a `data/raw/YYYY/MM/`, con verificación SHA-256 antes/después y sin sobrescribir destinos. Se leyeron solo metadatos/esquemas, no el conjunto completo en memoria.

Observado: 1,522,975,012 bytes (1.418 GiB), 89,892,322 filas declaradas, 19 columnas en 2024 y 20 en 2025 con `cbd_congestion_fee` adicional. Timestamps `timestamp[us]` sin zona declarada: D-06 todavía debe decidir interpretación histórica/DST. No hay archivos 2026 en raw observado.

No se aprobaron periodos, umbrales DQ, destino conocido ni recursos de entrenamiento; tampoco se calcularon métricas de duración/calidad ni se validaron todas las páginas Parquet. Procedencia y fecha de descarga no verificadas. No se implementaron fixtures T04, EDA T05 completa, ingesta, modelos ni serving. G0/G1 permanecen abiertos.
