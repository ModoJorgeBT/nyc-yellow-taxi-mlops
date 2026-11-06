# T19 — Champion inicial aprobado: LightGBM v4

**Estado: CHAMPION APLICADO Y AUDITADO; T19 CIERRE TÉCNICO PASS.**
Fecha de decisión: 2026-11-05, America/Costa_Rica. El usuario indicó:
«Entonces no, favor usar LightGBM como champion y hacer T19», después de conocer
la mejora global y las regresiones por rutas. También descartó optimizar
hiperparámetros en esta continuación.

## Elección y alcance

Champion inicial local: **LightGBM v4** de `nyc-yellow-taxi-duration`.
Run `be28c76c84c44efa8914c5950a2959bf`; modelo original SHA-256
`8bd17196b3a5c1974036c11456f61083d2a5f601236d55d56f884802b477cff6`.
La aprobación está en [champion.yaml](../configs/champion.yaml), ligada al run,
versión, hashes de todos los archivos del paquete, métricas y parámetros del run,
y evidencia T18/evaluación final. La aprobación se aplicó sin champion previo; ahora el alias apunta a v4.

| Modelo | MAE validation 2025 (min) | MAE final independiente 2026 (min) |
|---|---:|---:|
| Baseline | 7,741890 | 9,141254 |
| SGD | 6,876910 | 8,352735 |
| LightGBM | **6,496404** | **7,742891** |

La evaluación final empleó las mismas 10.937.087 filas para los tres modelos:
LightGBM mejoró el MAE observado 7,301 % frente a SGD y 15,297 % frente al
baseline; RMSE 12,368333, MedAE 5,048365 y P90 absoluto 16,815384 minutos.
[Resultados congelados y segmentos](evaluation/lightgbm_final_evaluation.md).
El entrenamiento original usó todo train 2024: 41.119.495 filas y 100 árboles.

Esta es una elección humana inicial después de revisar resultados; no modifica
la selección histórica SGD de la primera comparación, ni reelige parámetros
usando el holdout. Las condiciones automáticas de futuras promociones y drift
de D-05/T34 siguen pendientes. La API, su carga operativa y Docker corresponden
a T20–T25; asignar champion no los declara implementados.

## Limitaciones aceptadas para esta elección

- Mayor MAE que SGD en 14/20 pares origen–destino congelados; mayor MAE que
  baseline en 132→132 y 236→161. La mejora global no es uniforme.
- P90 de madrugada [00,06) peor que baseline: 13,879320 frente a 13,516667 min.
- Evaluación retrospectiva de un trimestre; no garantiza desempeño futuro.
  Train mantiene procedencia LOCAL_UNVERIFIED aprobada para uso académico.
- Excepciones D-04 por mes/hash/reporte y exclusiones se conservan; no se
  conceden nuevas excepciones de calidad ni tolerancias generales por segmento.

La aceptación es contextual: el usuario eligió LightGBM después de la explicación
de las 14/20 rutas. No se presenta como aprobación de umbrales generales de D-05.
Destino sigue exclusivamente como segmento de evaluación; las features continúan
siendo origen, calendario local y pasajeros opcionales. La decisión no incorpora
una selección dinámica de modelos basada en el destino observado.

## Aplicación y resolución previstas

[champion.py](../src/training/champion.py) verifica las evidencias y el paquete
completo antes de ejecutar pickle; comprueba seis payloads sintéticos contra la
referencia de T18. Después añade tags de aprobación a v4 y asigna únicamente
el alias `champion`. Conserva un evento preparado y otro aplicado, sin reemplazo.
Los candidatos v1/v2/v3, pesos, runs y evaluaciones originales se conservan.

La resolución exige aprobación aplicada, alias correcto, run/hash/tags y huellas
de métricas/parámetros coincidentes. Devuelve la URI fija
`models:/nyc-yellow-taxi-duration/4`; no resuelve por «última versión».
Ausencia de aprobación/alias o divergencia provoca rechazo. La resolución de
metadatos no deserializa el modelo; T21 deberá verificar sus archivos antes de
cargarlo mediante la función compartida `verify_artifact_files`.

Una interrupción entre alias y recibo aplicado mantiene la resolución bloqueada;
solo se puede completar la misma aprobación preparada, sin sustituir otro
champion. Un marcador local impide dos activaciones propias simultáneas. El
Registry no ofrece compare-and-set del alias: se mantiene la operación con un
único operador acordada en D-07, con comprobación antes y después de escribir.

```powershell
$env:MLFLOW_DISABLE_TELEMETRY='true'
$env:PYTHONUTF8='1'
# Mutación explícita, únicamente para la aprobación inicial registrada
.\.venv-mlflow\Scripts\python.exe -m src.training.champion --approve-initial
# Lectura posterior, sin promoción ni entrenamiento
.\.venv-mlflow\Scripts\python.exe -m src.training.champion --resolve
```

Los metadatos de artefacto/run creados como candidatos en T18 son históricos y
permanecen intactos. El estado aprobado actual procede del contrato y recibo T19
y de los tags/alias de la versión, no de reescribir el modelo serializado.

## Evidencia de ejecución

El alias `models:/nyc-yellow-taxi-duration@champion` resuelve a la versión fija
`models:/nyc-yellow-taxi-duration/4`. El recibo preparado conservó los alias
vacíos; el aplicado registra únicamente `champion: 4`, aprobador, instrucción,
fecha UTC, versión/run/hashes, prueba del paquete y recursos.

La auditoría leyó SQLite por separado y verificó exactamente cuatro runs y
cuatro versiones; únicamente v4 tiene `serving_approved=true` y tags de esta
aprobación. Los demás candidatos siguen no aprobados. Los tags históricos de
los runs, parámetros y métricas no cambiaron. Se verificaron otra vez los
50 archivos descargando mediante el alias: 49 almacenados y el metadato de
nombre/versión que genera el SDK. Se cargó el paquete verificado y sus seis
payloads sintéticos produjeron las mismas predicciones esperadas, diferencia
máxima **0 minutos**.

El CLI de resolución devolvió nombre, versión 4, run, URI fija y SHA esperado.
Repetir la aprobación devuelve el mismo recibo y no crea runs/versiones.
La ausencia o divergencia de alias, aprobación, paquete, métricas, parámetros
o run se cubrió con pruebas negativas; la recuperación de una operación
interrumpida también está probada, sin sustituir un champion ajeno.

Validación: **501 pruebas PASS y dos integraciones MLflow omitidas** en el
entorno histórico; **503 PASS** con wheel instalado en el entorno MLflow,
desde una copia sin `src` ni datos reales. 40 imports aislados. Ruff y formato
PASS; `pip check` nativo/MLflow PASS. Las advertencias son batches MLP de
fixtures y una deprecación de SQLAlchemy dentro de MLflow; no se cambiaron
dependencias para silenciarlas.

La operación real tardó 1.044 segundos,
con pico RSS 0.2268 GiB;
respetó el perfil ya aprobado 4 GiB RAM libres/2 GiB RSS/50 GiB disco y cuatro
hilos. No se entrenaron modelos ni se recalcularon resultados del holdout.

Identidades de la decisión y el software:

- Aprobación canónica: `5bf76fd9c9ab1f678268b652fedcfa3fc04670517e7cb3b087cd871be1d6c962`.
- Recibo preparado: `de1f70375cdb3054f964f315ca87130cecffdde5f5f63e634dc6e37fe2f15538`.
- Recibo aplicado: `17970d32fd9378060e8d87cb20329d23550db996d06854790cda64b891377806`.
- Manifiesto del paquete: `9f4e730920df728616191d552718e9120ed0e98e4fb700bc32093958c775c02e`.
- Código del ejecutor T19: `3875bfbd83f9db150eb66569e7147ce6583ff991514ef33a91554e98682f420c`.
- Wheel probado: `a605d7524611be4e72b7ebca66c6017d842a4191cd0a8642240d31b63abe821d`.
- Lock nativo conservado: `0a91f93e814050fe7171cbd91bdc12ae0693468c34267192cfbdffc28c61b079`.
- Lock MLflow conservado: `0edf1a477310dc667c97e3c74e7709f05216484aef81b8e0bc7ab79df460784f`.

Recibos persistentes: `tracking/approvals/<huella>.prepared.json` y
`<huella>.applied.json`; copias de auditoría en
`reports/model-selection/initial-lightgbm-v4/`, excluidas de Git. Conservar el
contrato y el recibo aplicado junto al Registry para la resolución. El contrato
actual autoriza solo esta versión: una promoción futura requiere una nueva
aprobación coherente, no basta cambiar el alias.

**G3 cumple sus condiciones de Sprint 3:** baseline/candidatos, evaluación
temporal, tracking trazable y champion inicial aprobado explícitamente y
verificado. API, Docker/Compose y sus gates no se declaran completados.
**Siguiente tarea: T20**, contrato de entrada/salida y errores; fuera de T19.
