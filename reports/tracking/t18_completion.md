# T18 — Tracking y Registry verificados

**CIERRE TÉCNICO PASS — 2026-11-05, America/Costa_Rica.**
El usuario aprobó D-07 y el registro local aislado. Cuatro candidatos congelados
registrados, cargados y verificados después de reiniciar el servicio conservando
SQLite y artefactos. Sin entrenamiento, nuevas métricas predictivas ni promoción.
Revisión humana de resultados independiente.

## Modelos registrados

Nombre estable: `nyc-yellow-taxi-duration`. Servidor activo al cierre en
<http://127.0.0.1:5000>. Todos los runs están FINISHED y versiones READY;
`current_stage=None` y ningún alias asignado.

| Familia | Versión candidata | Run ID | Ventanas registradas | Valores de métricas |
|---|---:|---|---|---:|
| baseline | 1 | `0087c40168864e3488e2e31a84d11b3a` | validation_2025, test_2025, final_2026 | 435 |
| sgd | 2 | `c41da0ab87d343439dbbd7e7f8d8ecb5` | validation_2025, test_2025, final_2026 | 435 |
| mlp | 3 | `f495a0e77acf423ebf186cabdec59291` | validation_2025, test_2025 | 290 |
| lightgbm | 4 | `be28c76c84c44efa8914c5950a2959bf` | validation_2025, final_2026 | 290 |

Cada ventana incluye MAE/RMSE/MedAE/P90 y número de filas, para el global y los
28 segmentos congelados. Los valores se importaron de manifiestos de evaluación
auditados; no se recalcularon resultados con el holdout para elegir un modelo.
MLP no tiene evaluación 2026 y LightGBM no tiene test original 2025; esas
ausencias se conservan. Los registros son posteriores al entrenamiento y no
atribuyen al fit la fecha del registro en MLflow.

## Trazabilidad y persistencia

La auditoría leyó SQLite por una conexión independiente en modo lectura y
comparó todos los parámetros y métricas con los manifiestos originales.
Verificó cuatro runs/cuatro versiones/ningún alias; los mismos IDs después
de reiniciar y de un registro idempotente, sin duplicados.

Por modelo verificó el SHA-256 del binario/JSON original y de su copia MLflow,
el código incluido en `code/src`, el lock aislado, perfil de registro y todas
las copias del linaje (configuración, datasets/splits, ajustes, evaluaciones
y sus auditorías). Los 27 raw conservan sus bytes; la selección de 2025 y
el manifest de evaluación final independiente no cambiaron.

| Familia | SHA-256 del modelo original y del artefacto registrado |
|---|---|
| baseline | `7d6e3eefd040f04f46e7a8f6ef6068fd65dcf86c56bb0e97cde5ecb8f0c8abf9` |
| sgd | `bfe284f297e7eb8d67261242ab1d4d35dc9639d181760dc923da128e52082541` |
| mlp | `518a7e34ac0ff5c44d93ed6b767457daf8b3e604a51d080a0d2ad4471b9e53c8` |
| lightgbm | `8bd17196b3a5c1974036c11456f61083d2a5f601236d55d56f884802b477cff6` |

Artefactos locales persistentes: `tracking/mlflow.db` y `tracking/artifacts/`,
fuera de Git. El reinicio detuvo únicamente el árbol propio identificado por
PID/token; no borró la base ni sus artefactos. Las lecturas y verificaciones
posteriores descargaron y cargaron modelos por nombre y versión exacta.

Se compararon seis payloads sintéticos con las predicciones del entorno original:
offsets equivalentes, DST explícito, pasajeros ausentes/cero/dos y origen no
observado. Las predicciones por lotes de ambos entornos fueron idénticas. Al
cargar desde Registry y consultar fila a fila se observaron estas diferencias
máximas frente al lote de referencia, atribuibles a la aritmética float32:

- baseline: `0.0` minutos.
- sgd: `4.76837158203125e-07` minutos.
- mlp: `1.430511474609375e-06` minutos.
- lightgbm: `0.0` minutos.

Se usó una tolerancia fijada antes de consultar estas predicciones sintéticas:
`atol=2e-5`, `rtol=1e-6`; las pruebas del adaptador sobre el mismo batch comparan
con tolerancia absoluta `1e-10`. No hubo fit ni actualización de transformaciones.

## Software y recursos

MLflow 3.16.1 y 95 paquetes con versiones/hashes en el entorno `.venv-mlflow`.
PyArrow 25 solo allí; las 24 dependencias históricas no cambiaron. La suite del
entorno original pasó **488 pruebas**, con una integración MLflow omitida
explícitamente; el wheel instalado en el entorno MLflow pasó **489 pruebas**
desde una copia sin `src` ni datos reales. 39 módulos importados de forma aislada.
Ruff/check/formato y `pip check` de los tres entornos PASS. Las dos advertencias
de la suite son los batches MLP de fixtures pequeñas.

La integración usa fixtures sintéticas y HTTP real: registro, carga, reinicio
y ausencia de duplicados/alias. Los tres casos adicionales de corrupción de
reportes comprueban que un SHA coincidente no permite reutilizar una evaluación
incompleta o enlazada a otro ajuste/modelo.

El cliente real tardó **31.031 segundos**, con pico RSS
**0.2405 GiB**. El worker HTTP alcanzó
0.2570 GiB antes del reinicio y
0.2466 GiB después, medidos por separado.
El cliente respetó 4 GiB RAM/50 GiB disco libres y 2 GiB RSS; los controles
son cooperativos, sin afirmar límites duros del sistema operativo.

Las pruebas previas corrigieron una ruta de artefactos y salida Unicode de
Windows antes del registro real. Un lector del log del helper falló después
del registro completo; se corrigió y terminó la auditoría sin crear nuevos runs.
Los intentos y logs se conservan localmente. Windows denegó `taskkill` dentro
del sandbox; el permiso de ejecución permitió cerrar solo los árboles propios.

## Identidades y límites

- Perfil de registro: `d9f2a299e7c904b5f55b21abf73c62d0cd3e7a26a1fd62d3fcee964487c6fdec`.
- Código registrado: `410f05ffa50167d19c1be940ccb63b9d58dfc10be50ee77171f8f24c0ef68e7c`.
- Wheel probado: `f42ec3c6829182b0ce83bd9ed90074f43cf51750878eadaa50b7474d4cd51019`.
- Lock T18: `0edf1a477310dc667c97e3c74e7709f05216484aef81b8e0bc7ab79df460784f`.
- Lock histórico: `0a91f93e814050fe7171cbd91bdc12ae0693468c34267192cfbdffc28c61b079`.
- Commit disponible al registrar: `27b09d2d0a0344b88bd9dbfefabb8154f81a99ec`.
- Árbol sucio al registrar: `True`; el commit por sí solo no representa estos cambios.

Recibos JSON locales: `reports/tracking/real/` y `.cache/t18/`;
auditoría independiente `independent-audit.json`, prueba de reinicio
`persistence-audit.json`, recibo de registro por huella y `software.json`.
El servidor que quedó activo tiene su identidad en `.cache/t18/real-server-state.json`.

MLflow informó que su backend de ejecución de jobs no soporta Windows; no se
utilizó esa función. Tracking/Registry/persistencia sí se probaron. El lock T18
es de Windows/Python 3.14; no demuestra compatibilidad Docker/Linux. Los avisos
de seguridad del candidato y sus condiciones excluidas se documentan en la
[guía T18](../../docs/t18-mlflow.md). El arranque local desactiva telemetría;
los clientes manuales deben usar la variable indicada en esa guía.

**Siguiente tarea: T19**, con revisión y aprobación explícita de champion.
La mejora global de LightGBM no aprueba automáticamente sus regresiones por
ruta ni resuelve D-05. API, Compose completo, CI y monitoreo continúan pendientes.

[Guía operativa](../../docs/t18-mlflow.md), [decisión D-07](../../docs/d07-mlflow-proposal.md),
[evaluación final congelada](../evaluation/lightgbm_final_evaluation.md).
