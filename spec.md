# SPEC — Especificación técnica de NYC Yellow Taxi MLOps

**Versión:** 1.0 (propuesta para revisión)  
**Proyecto:** Diseño de una Plataforma MLOps para Predicción de Duración de Viajes de NYC Yellow Taxi  
**Entorno:** desarrollo y demostración local mediante Visual Studio Code, Python y Docker Compose  
**Documentos rectores:** `intent.md` y «Proyecto_Maestria_MLOps_NYC_Taxi_Estructura», v1.0, septiembre de 2026.

> **Estado de decisiones.** `[BASE]` identifica un requisito del documento académico o de `intent.md`; `[DECISIÓN]` una elección confirmada por el equipo (ejecución local con Docker Compose); `[PROPUESTA]` una concreción técnica que debe revisarse antes de implementarse; `[PENDIENTE]` una cuestión todavía no aprobada. Los valores propuestos no deben interpretarse como requisitos académicos definitivos.

**Acuerdo T01 (2026-11-03):** Python, MLflow, FastAPI y Docker Compose para ejecución local confirmados por el equipo. Herramientas adicionales e hipótesis de destino conocido permanecen pendientes. La aprobación de entregables documentales no aprueba toda esta especificación ni las tareas posteriores. Evidencia y trazabilidad en [docs/decisions.md](docs/decisions.md).

**Segunda revisión T01:** el equipo aprobó las siete correcciones documentales y Git local en `main` para T02, sin commits ni publicación. La estructura de T02 puede prepararse para revisión conjunta, conservando separados los estados de autorización, verificación técnica y cierre humano.

**Acuerdo posterior T03:** T01/T02 cerradas por aprobación del equipo el 2026-11-03. Se autorizó T03 con Python 3.14.7, `.venv`, setuptools/Ruff/Pytest/pip-tools fijados y hashes; PyArrow aprobado para metadatos de los archivos locales. Ver [entorno y evidencia T03](docs/t03-environment.md). Las herramientas restantes y el destino conocido siguen pendientes; no se aprueba todavía el stack completo ni infraestructura.

**Continuación T04/T05:** el usuario solicitó ambas tareas y aprobó perfilar solo 2024 con las primeras 2.048 filas por row group, manteniendo 2025 sin perfilado de filas. Las fixtures sintéticas siguen siendo necesarias para casos controlados en CI; no se mezclan con datos reales. [Evidencia y límites](docs/t04-t05-verification.md). El contrato sintético no sustituye T08/T09 ni aprueba D-01/D-02/D-04.

**Continuación T06/T07:** implementación y pruebas autorizadas sin descargas masivas ni reemplazos. El usuario aprobó registro local explícito con procedencia no verificada; se prueba con fixtures y no se aplica aún a los 24 archivos reales. [Contrato de ingesta y evidencia](docs/t06-t07-ingestion.md).

**Continuación T08/T09:** el usuario aprobó el contrato raw de cuatro campos esenciales, compatibilidad explícita y columnas nuevas con WARN; también el motor configurable con políticas exclusivamente sintéticas y bloqueo de lotes reales mientras D-04 siga pendiente. Catálogo explícito, repeticiones sin borrado y pasajeros medidos aparte. [Contrato, límites y evidencia](docs/t08-t09-validation.md). Esta aprobación inicial no abarcó T10/T11 ni features de destino.

**Continuación T10/T11:** posteriormente el usuario solicitó estas dos tareas. Se implementan CLI e integración mediante fixtures, sin resolver D-04/D-06 ni aprobar datos reales. Salidas de prueba aisladas, linaje y exhaustividad verificados, reportes y publicación sin reemplazo. [Contrato y evidencia](docs/t10-t11-data-pipeline.md). No se incorporan automáticamente los 24 archivos ni se autoriza T12.

**Publicación GitHub:** después el usuario autorizó subir el estado actual a [ModoJorgeBT/nyc-yellow-taxi-mlops](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops), incluido commit inicial y remoto sobre `main`. Sustituye la restricción histórica de no publicar; no autoriza más tareas, CI ni aprobación de políticas/datos reales. Se mantienen las exclusiones de datos y secretos.

**Acuerdo T12/T13:** el usuario solicitó ambas tareas y, tras revisión del diccionario oficial, aprobó origen/calendario/pasajeros opcionales, destino deshabilitado y convención temporal America/New_York con cuarentena DST y duración UTC. Aprobó scikit-learn, tzdata y sus dependencias con hashes. [Contrato y evidencia](docs/t12-t13-features.md). En esa entrega D-04 seguía abierta y las salidas eran TEST_ONLY. Posteriormente el usuario aprobó D-04 provisional y el piloto académico solo de enero 2024; [activación](docs/d04-activation.md). Calidad REAL aprobada con WARN, entrenamiento false y T14 sin autorización.

## 1. Propósito y límites

**[BASE]** Implementar un sistema MLOps reproducible para predecir la duración, en **minutos**, de un viaje de taxi amarillo de Nueva York al comenzar el recorrido. El sistema debe cubrir ingesta mensual, validación, transformación, entrenamiento, evaluación temporal, seguimiento de experimentos, registro de modelos, inferencia REST, contenerización, CI, monitoreo y reentrenamiento controlado.

**[DECISIÓN]** La demostración inicial será **100 % local** mediante Docker Compose; no se requiere nube pública, Kubernetes, Airflow, Kafka ni Terraform.

**Fuera de alcance del MVP:** predicción de tarifas o propinas; optimización de rutas; tráfico en tiempo real; frontend web completo; orquestación distribuida; entrenamiento automático sin revisión de promoción; infraestructura cloud.

## 2. Arquitectura lógica

```text
NYC TLC Parquet mensual
       |
       v
CLI ingesta -> data/raw + manifiesto (URL, SHA-256, fecha, tamaño)
       |
       v
Validación + Quality Gates -> data/validated + reporte de calidad
       |
       v
Features reproducibles -> data/processed
       |
       v
Entrenamiento temporal -> evaluación -> MLflow Tracking / Registry
                                              |
                                              v
                                       Champion aprobado
                                              |
                                              v
Cliente REST -> FastAPI /predict -> pipeline de inferencia -> minutos
                      |                        |
                /health /model-info       logs y métricas
                                               |
Lotes posteriores -> Evidently + evaluación observada -> trigger
                                               |
                                         challenger -> gates
                                               |
                                       promoción / rollback

GitHub Actions: lint + pruebas + smoke tests + Docker build
Docker Compose: API + MLflow + almacenamiento persistente local
```

**[BASE]** Las etapas deben poder ejecutarse desde CLI y no depender exclusivamente de notebooks. **[PROPUESTA]** Un servicio de tareas CLI se ejecutará desde el mismo entorno Python del repositorio, o con `docker compose run --rm pipeline ...`, sin mantener un scheduler permanente.

## 3. Componentes y responsabilidades

| Componente | Entrada | Salida | Condición de fallo |
|---|---|---|---|
| Ingesta | año, mes, URL TLC | Parquet raw y manifiesto | HTTP fallido, archivo corrupto, hash inconsistente |
| Calidad | raw + reglas | reporte y dataset validado | gate crítico incumplido |
| Features | dataset validado + configuración | transformaciones y datos procesados | features incompatibles, fuga temporal |
| Training | histórico procesado + parámetros | modelos, métricas y artefactos | datos insuficientes, entrenamiento fallido |
| Registry | run y evaluación | versión candidata y alias/estado | versión no rastreable |
| Serving | petición validada + champion | duración estimada y metadatos | entrada inválida o modelo no disponible |
| Monitoring | lotes nuevos, referencia, resultados observados | reportes de drift/calidad/desempeño | ausencia de referencia o error de evaluación |
| Retraining | trigger + datos aprobados | challenger y decisión auditada | gates no superados |
| CI | cambios de Git | pruebas y build reproducibles | pruebas, lint o build fallidos |

## 4. Datos, procedencia y particiones

### 4.1 Fuente

**[BASE]** NYC Taxi & Limousine Commission, archivos mensuales Parquet de Yellow Taxi Trip Records. Fuente: https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page . Diccionario: https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf .

**[PROPUESTA]** Convención de almacenamiento: `data/raw/YYYY/MM/yellow_tripdata_YYYY-MM.parquet`. El descargador construye la URL del archivo desde año y mes; verifica HTTP, legibilidad Parquet y metadatos. No se presupone que todos los meses estén publicados.

**[DECISIÓN: T01/T02]** Los Parquet que el equipo ya posee pueden colocarse en esa estructura local sin descargarlos nuevamente. Almacenarlos no acredita calidad, ingesta trazable ni aprobación de periodos. T02 prepara la carpeta y las exclusiones; el inventario y perfilado acotado corresponden a T05. Si se desconoce procedencia o fecha de descarga, registrar esa ausencia; no inventar metadatos. El protocolo de incorporación al manifiesto debe resolverse antes de T07/T10 sin relajar los gates de trazabilidad.

**Revisión adicional autorizada con T03:** se inventariaron y reorganizaron 24 Parquet locales (2024/2025) por año/mes, conservando SHA-256. Se leyeron solo footers y esquemas mediante PyArrow; el perfilado de filas y Quality Gates siguen pendientes. Evidencia: [inventario local](reports/raw_inventory.md). D-01 no se resuelve por disponibilidad de archivos y no hay lotes 2026 en el inventario local observado.

### 4.2 Ventanas temporales

**[DECISIÓN D-01]** Entrenamiento: todo 2024. Validación/selección: enero–marzo 2025. Test final reservado: abril–junio 2025. Monitoreo por replay retrospectivo: julio–diciembre 2025. Esta aprobación sustituye la recomendación académica inicial de train 2025/monitoreo 2026; no requiere nuevas descargas. [Protocolo aprobado](docs/d01-d02-protocol.md).

**[DECISIÓN D-02]** Usar todas las filas elegibles de cada partición, sin submuestreo de modelado. Intervalos de recogida [inicio, fin) en America/New_York, disponibilidad de etiqueta por evento anterior al corte y exclusión auditada de viajes que lo atraviesan. Nunca split aleatorio entre train/validación/test. El replay no acredita disponibilidad histórica de publicación de archivos.

**Estado T14/T15:** CIERRE TÉCNICO PASS: 24 meses registrados, validados/aceptados y con features; 89.892.322 raw, 627.221 exclusiones de calidad y 2.952 por disponibilidad de etiqueta. Particiones auditadas: train 41.119.495; validation 11.163.264; test 12.712.466; replay 24.266.924. Todas las identidades y valores publicados coinciden con las fuentes; train/validation coinciden con T15 congelada. D-04, 24 raw y diez FAIL originales intactos. [Auditoría T14](reports/quality/t14_completion.md) y [T15 congelada](reports/quality/t15_baseline_validation.md). Posteriormente terminaron el ajuste/evaluación de SGD/MLP y la extensión LightGBM solo con validation; [resultados](reports/evaluation/lightgbm_validation.md). La revisión humana y los gates generales G2/G3 siguen siendo independientes; registry, champion y Docker permanecen pendientes.

**Aceptación temporal de T14:** además de separar por recogida, comprobar la disponibilidad de etiquetas al corte del entrenamiento. Un viaje que termina después del corte no aporta una etiqueta disponible en ese instante. Documentar si se realiza replay retrospectivo o una simulación con disponibilidad real de publicación de lotes; la política concreta debe aprobarse con D-01/D-06. No atribuir disponibilidad histórica de datos sin evidencia.

### 4.3 Manifiesto y linaje

**[PROPUESTA]** Cada lote tendrá un JSON de manifiesto con `source_url`, `year`, `month`, `downloaded_at_utc`, `sha256`, `file_size_bytes`, `row_count` (si se calcula), `schema_fingerprint`, `pipeline_version` y `status`. Los runs de MLflow referenciarán hashes de datasets, versión de configuración y commit Git cuando exista.

**[IMPLEMENTADO T07]** `manifest.json` por lote y eventos en `ingestion-events.jsonl`. El manifiesto añade versión de formato, nombre de archivo, esquema, origen, URL esperada y fecha de registro. Para un archivo incorporado con `--register-local`, `source_url` y `downloaded_at_utc` quedan nulos, `status=LOCAL_UNVERIFIED` y `provenance_status=UNVERIFIED_LOCAL`; la URL esperada no acredita procedencia. Para descarga por pipeline se registra URL y timestamp de descarga. Este contrato de ingesta no concede aprobación de calidad ni sustituye las decisiones de trazabilidad T08/T09.

### 4.4 Idempotencia

**[BASE]** Reejecutar una ingesta del mismo mes no debe crear inconsistencias. **[PROPUESTA]** Si archivo y hash ya existen, omitir descarga y registrar `SKIPPED`; si hay divergencia, conservar evidencia y exigir una opción explícita de reemplazo, sin sobrescribir silenciosamente.

**[IMPLEMENTADO T06/T07]** Verificar hash, tamaño, esquema, volumen y metadatos antes de `SKIPPED`, sin petición remota; el evento se guarda aparte y el manifiesto original no cambia. Archivo sin manifiesto: conflicto salvo registro local explícito. Divergencias y estados incompletos bloquean la operación, sin ofrecer reemplazo en esta versión; cualquier recuperación/reemplazo requiere un procedimiento autorizado. Bloqueo por mes y publicación sin reemplazo mediante hard links en el mismo volumen. Datos y manifiesto no constituyen una transacción atómica conjunta: si falla la segunda publicación, se conserva el archivo completo huérfano y la siguiente ejecución bloquea. Validación de legibilidad del footer, sin escaneo de todas las páginas ni Quality Gates.

## 5. Target, features y prevención de leakage

**Target histórico:**

```python
# Despues de localizar ambos eventos historicos sin ambiguedad:
trip_duration_minutes = (
    dropoff_datetime.astimezone(UTC) - pickup_datetime.astimezone(UTC)
).total_seconds() / 60.0
```

**[BASE]** El target se calcula únicamente para entrenamiento/evaluación; `tpep_dropoff_datetime` nunca es una entrada de inferencia.

**[DECISIÓN T12/T13] Features v1:** origen, hora/día de semana/mes de recogida en America/New_York y pasajeros opcionales bajo la hipótesis de conteo conocido al abordar. Pasajero ausente: relleno constante 0 más indicador de ausencia. Destino, RatecodeID y agregados históricos deshabilitados; no se seleccionan por su mera presencia en raw.

**Features prohibidas en MVP:** `tpep_dropoff_datetime`, `trip_duration_minutes`, `fare_amount`, `total_amount`, `tip_amount`, `payment_type`, `tolls_amount`, cargos finales y `trip_distance` medida por taxímetro. Tampoco utilizar campos indirectamente derivados del resultado del viaje.

**[DECISIÓN T12/T13] Tiempo:** históricos naive interpretados en America/New_York; horarios ambiguos/inexistentes apartados con motivo. Target = diferencia en minutos entre instantes UTC localizados. Inferencia exige offset y convierte a Nueva York para calendario. Es una convención del proyecto, no una garantía explícita del diccionario. El contexto de evento final de etiqueta no acredita publicación del lote.

**[DECISIÓN D-06]** Whitelist, convención temporal, catálogo operativo y contrato REST v1 aprobados; [implementación y pruebas T20–T22](docs/t20-t22-serving.md). Reintroducir destino requiere nueva aprobación causal. El perfil real D-04 aplica duración UTC coherente con T12; T09 conserva además la política sintética anterior para pruebas aisladas.

**Regla de consistencia:** serializar un único pipeline de preprocesamiento + estimador; reutilizarlo en inferencia, sin reconstruir transformaciones ad hoc. Los agregados de ruta, si se incorporan, se calculan mediante ventanas históricas sin mirar al futuro y deben poder resolverse en serving.

## 6. Data Quality Gates

**[BASE]** Comprobar esquema, volumen, fechas, duración, duplicados, nulos de zonas, categorías, rangos, cambios de esquema y trazabilidad. Cada gate genera resultado `PASS`, `WARN` o `FAIL`, con regla, valor observado, umbral, severidad y evidencia. Por defecto, un fallo crítico detiene el pipeline y no genera un dataset aprobado. La excepción humana puntual de marzo, descrita abajo, conserva el FAIL medido y excluye las filas inválidas antes de aceptar el lote.

Los reportes de lotes rechazados también alimentan la observación de calidad. Los datos rechazados no pasan al entrenamiento ni se presentan como lotes aprobados para evaluación de desempeño. T28 tiene una referencia aprobada e identificable para calidad/schema: los doce reportes completos de train 2024, con comparación por mismo mes de replay julio–diciembre 2025. La referencia para drift de distribuciones y sus umbrales D-05 siguen pendientes; no se deducen de esos agregados.

**[CONTINUACIÓN APROBADA 2026-11-05]** Los nueve permisos exactos de abril–diciembre de 2025 ya se aplicaron por mes/hash/reporte y conjunto de fallos. Se excluyeron 543.725 filas inválidas, manteniendo D-04 y los FAIL originales; el lector v2 conserva marzo v1. Las 24 versiones y sus cuatro particiones terminaron la auditoría. [Evidencia](reports/quality/t14_completion.md). Cualquier archivo, medición o fallo distinto requiere nueva consulta/aprobación.

**[PROPUESTA]** Reglas iniciales configurables en `configs/data.yaml`:

| Regla | Comportamiento |
|---|---|
| Esquema | exigir columnas esenciales y tipos compatibles; reportar columnas nuevas |
| Fechas | `pickup < dropoff`; controlar coherencia con mes del lote, considerando viajes limítrofes |
| Duración | exigir `duration > 0`; máximo configurable, **sin fijar aquí un valor definitivo** |
| Volumen | umbral mínimo por lote configurable tras perfilar datos |
| Duplicados | tasa observada y umbral configurable |
| Zonas | tasa de nulos y códigos fuera de catálogo, con tolerancias configurables |
| Categorías y pasajeros | conjuntos/rangos admisibles definidos tras EDA y diccionario |
| Integridad | hash, año/mes y fecha de registro obligatorios; URL/fecha de descarga registradas o nulas bajo autorización LOCAL_UNVERIFIED explícita |

**Precisión importante:** distinguir la **tasa de registros inválidos** del **fallo del lote completo**. **[PROPUESTA]** Una fracción tolerable de filas inválidas puede excluirse con reporte; fallos estructurales, ausencia de columnas esenciales o tasas superiores a límites aprobados bloquean el lote. No asumir que cualquier fila de duración inválida debe abortar automáticamente millones de registros.

**[APROBADO PROVISIONAL: D-04]** Umbrales versionados tras perfilado 2024 y aprobación explícita; cualquier revisión posterior requiere nueva decisión, sin calibrar sobre test.

**[D-04 APROBADA E IMPLEMENTADA]** D-04 v1 conserva sus tasas, reglas, mínimos, catálogo y normalizaciones. La [excepción de marzo 2025](docs/t15-march-exception.md) fue implementada por hash/configuración/reporte para duración no positiva. El 2026-11-05 se aprobaron además nueve autorizaciones exactas para abril–diciembre, descritas arriba. Se conservan raw_quality_status=FAIL, checks FAIL y quality_passed=false; aceptación efectiva VALIDATED_REAL_EXCEPTION/WARN/data_quality_approved=true. Cualquier fallo fuera de la autorización concreta requiere consulta y bloquea su consumo mientras no se apruebe. Todas las filas inválidas siguen excluidas; no cambia procedencia ni se concede promoción.

**[EVIDENCIA HISTÓRICA T08/T09; actualizada por D-04 arriba]** `configs/data.yaml` usa sintaxis JSON compatible con YAML, sin parser adicional. Esenciales: pickup/dropoff `timestamp[us]` sin zona y zonas enteras con signo de 32/64 bits; otros campos históricos opcionales, comprobados si existen. Se conserva `Airport_fee`; `cbd_congestion_fee` es conocido opcional. El motor devuelve reportes en memoria con tasas/conteos y versiones; configuración real PENDIENTE y controles no evaluados explícitos. Un perfil TEST_ONLY completo solo puede superar calidad con fixtures marcadas; `approved_for_training=false` y linaje no comprobado hasta T10. La semántica de reloj local usada en pruebas no resuelve DST de D-06. Ningún límite sintético se adopta para TLC; T09 no tiene cierre operativo mientras D-04 siga abierta.

**[EVIDENCIA HISTÓRICA T10/T11; actualizada por D-04 arriba]** El CLI verifica manifiesto/hash antes y después de escanear y contrasta filas leídas con el footer; reutiliza elegibilidad T09 para escribir por bloques. Modo normal: rechazo por política real pendiente, sin lectura de filas ni dataset. `--test-only`: exige perfil y fixture de prueba, publica bajo `data/validated/_test_only/YYYY/MM/<id>/` y conserva `approved_for_training=false`. Reportes JSON por intento en `reports/quality/`, con configuración y linaje; `validation.json` interno es marcador final. Fallos no habilitan datos; no existe transacción conjunta de todos los archivos. Los 24 Parquet siguen sin incorporación automática ni validación de filas.

## 7. Modelado y evaluación

**[BASE]** Baseline y al menos dos candidatos. **[DECISIÓN T15]** Mediana global exacta de todas las etiquetas elegibles de train 2024, obtenida en disco, aplicada solo a validación; sin acceso a test/replay. [Contrato T15](docs/t15-baseline.md). **[DECISIÓN D-02]** Para usar todos los registros sin materializar la matriz completa en RAM, los candidatos aprobados son `SGDRegressor` y `MLPRegressor` pequeño con entrenamiento incremental por bloques. Son los candidatos de la primera comparación. Posteriormente el usuario aprobó añadir LightGBM mediante un protocolo separado, sin sustituir sus artefactos ni la selección original. Particiones cronológicas, semillas, parámetros, pasadas y versiones registrados; preprocesador ajustado solo con train y serializado junto al estimador.

**Métricas:** MAE (principal, minutos), RMSE, MedAE y percentil 90 del error absoluto. Latencia p95 se mide por separado como métrica de servicio.

**[PROPUESTA]** Entrenar primero un baseline global; luego al menos dos candidatos con el mismo protocolo temporal. La selección se basa en validación; el conjunto de prueba permanece reservado para evaluación final. Reportar resultados por mes, franja y zonas/rutas frecuentes cuando haya soporte estadístico suficiente. No afirmar mejora porcentual hasta medirla.

**[DECISIÓN D-02]** Todas las filas elegibles, cuatro hilos, un candidato y dos horas por candidato. Perfil T16/T17 revisado y aprobado: **8 GiB RAM libre/4 GiB RSS/50 GiB disco**. [Decisión y justificación](docs/d02-t16-resource-review.md). El perfil inicial 12/8 se conserva como historia en el contrato T14 congelado; no se modifica su hash. Preparación T14/T15 mantiene 4/2. Calidad por bloques ≤ 65.536; entrenamiento por bloques de 4.096. Límites/timeout probados con fixtures y respetados en el fit/evaluación reales de SGD/MLP; supervisión cooperativa, Docker todavía sin verificar. Exceder detiene el intento sin muestrear ni ampliar presupuesto automáticamente.

## 8. MLflow Tracking y Model Registry

**[BASE]** Registrar parámetros, métricas, artefactos, datasets, versiones de código y modelos; separar entrenamiento de promoción. **[PROPUESTA]** Ejecutar MLflow local como servicio de Compose, con base de metadatos SQLite y directorio persistente de artefactos en volúmenes montados. Establecer `MLFLOW_TRACKING_URI=http://mlflow:5000` entre contenedores y `http://localhost:5000` desde el host.

Cada run debe incluir: nombre de experimento, versión de dataset, rango temporal, configuración, semilla, commit Git cuando exista, métricas, pipeline serializado y evaluación. El modelo registrado se identifica mediante nombre estable, versión y alias de operación (`champion`, si la versión de MLflow elegida lo permite). No asumir que el último run es el modelo en producción.

**[PROPUESTA]** Promoción mediante comando explícito con auditoría de versión previa, nueva versión, métricas comparativas, fecha, responsable y resultado de smoke tests. Rollback revierte el alias o puntero de versión y reinicia/recarga el servicio de forma controlada.

## 9. Contrato REST de inferencia

**[BASE]** Endpoints `POST /predict`, `GET /health` y `GET /model-info`, validación Pydantic y respuesta con predicción, unidad, versión y timestamp.

**[DECISIÓN D-06: contrato REST v1 aprobado el 2026-11-09]** [Contrato y verificación T20–T22](docs/t20-t22-serving.md).

`POST /predict`

```json
{
  "pickup_datetime": "2026-03-12T08:30:00-04:00",
  "pickup_location_id": 161,
  "passenger_count": 1
}
```

`passenger_count` es opcional/null o entero estricto 0–6; origen es entero estricto del catálogo aprobado, incluidas zonas 264/265. Fuera de catálogo/rango o campos extra producen 422, sin coerción de strings, decimales ni booleanos. Destino deshabilitado. **La fecha/hora ISO debe incluir offset**: convertir a `America/New_York` mediante el pipeline compartido. El contrato REST rechaza timestamps numéricos. La normalización histórica D-04 permanece intacta.

Respuesta `200` de ejemplo **ilustrativo, no una predicción real**:

```json
{
  "predicted_duration_minutes": 18.4,
  "unit": "minutes",
  "model_version": "4",
  "predicted_at_utc": "2026-11-03T16:00:00Z"
}
```

`GET /health`: `200` solo si API y modelo activo están listos; `503` si falta el modelo. Responder `{"status":"ok","model_loaded":true}`.

`GET /model-info`: nombre, versión activa, fecha de entrenamiento (si se registra), rango de datos y estado; **no revelar secretos ni rutas internas**.

Errores: `422` para payload inválido; `503` para ausencia de modelo en los tres endpoints; `500` para error inesperado sin exponer trazas al cliente. La API carga la versión fija aprobada al iniciar; un cambio de champion requiere reinicio controlado, sin recarga automática.

## 10. Docker Compose y persistencia local

**[DECISIÓN]** Ejecutar la solución en local con Docker Compose.

**[DECISIÓN T23–T25]** Servicios verificados en Docker Linux amd64:

- `mlflow`: puerto host `127.0.0.1:5001`, copia aislada de tracking/artefactos en volumen Linux; MLflow nativo conserva 5000.
- `api`: puerto host `127.0.0.1:8080`, champion LightGBM v4; conexión interna `http://mlflow:5000`, recibos de lectura y versión fija al iniciar.
- `pipeline`: perfil manual, probado con ayuda de CLI; sin entrenamiento Linux en estas tareas. `bootstrap` inicializa sin reemplazar el volumen y `smoke` prueba 503 en una instancia sin recibos.

Perfil, actualización portable de metadatos y puerto 8080 aprobados; build,
200/422/503 y persistencia tras down/up verificados. [Guía y evidencia](docs/t23-t25-docker.md).

Montajes separados para datos, tracking y reportes. Variables configurables por `.env.example`; `.env` real excluido de Git. No publicar puertos en interfaces públicas por defecto; para desarrollo, enlazar al loopback del host cuando sea viable. Usar versiones de imágenes/dependencias fijadas, usuario no root donde sea viable, health checks y arranque documentado.

**Dependencia crítica:** Docker Compose **no crea por sí mismo un modelo champion**. El README debe documentar el bootstrap: ingesta → calidad → entrenamiento → registro → aprobación → arranque de API (o estado `503` hasta completar la promoción).

## 11. Monitoreo y reentrenamiento

**[BASE]** Monitorear calidad de entradas, drift de distribuciones, desempeño cuando existan etiquetas verdaderas y métricas del servicio (latencia p50/p95, tasa de errores 4xx/5xx, throughput, disponibilidad). **[PROPUESTA: D-03 pendiente]** Utilizar Evidently para reportes por ventana temporal.

**[APROBADO T27/T28, 2026-11-09]** Ventanas operativas de 60 segundos; p50/p95 exactos hasta 10.000 solicitudes por ventana, no disponibles al superarlas y contadores conservados. Logs agregados y exportación local, sin endpoint adicional ni afirmación de disponibilidad continua. Calidad/schema utiliza los reportes completos congelados, preserva D-04 y excepciones exactas; cambios de volumen/tasas descriptivos, sin nuevos umbrales ni distribuciones inventadas. [Contrato y evidencia](docs/t26-t28.md).

**[PROPUESTA: D-05 pendiente, PDF §9.1]** Posible trigger si MAE mensual supera 115 % del MAE de referencia durante dos ventanas consecutivas; PSI > 0.20 en features críticas; cambios sostenidos de calidad/esquema; evaluación trimestral preventiva. Estos valores no están aprobados como configuración ejecutable.

**[BASE]** Separar entrenamiento de promoción, exigir calidad, pruebas y evaluación por segmentos; si falla, champion permanece activo. **[PROPUESTA: D-05 pendiente, PDF §9.2]** Exigir mejora de MAE de al menos 2 % **o** no inferioridad predefinida, junto con smoke tests. El margen de no inferioridad y las tolerancias por segmento aún deben definirse y aprobarse.

**[PROPUESTA]** Los triggers generan una **recomendación auditable**, no una promoción automática. Registrar reportes y decisiones `NO_ACTION`, `RETRAIN_RECOMMENDED`, `CHALLENGER_REJECTED`, `PROMOTED`, `ROLLED_BACK`. Para medir performance se requieren etiquetas posteriores al viaje: no inferir MAE a partir de solicitudes sin ground truth.

## 12. CI/CD y pruebas

**[BASE]** GitHub Actions debe ejecutar lint/formato, unit tests, smoke tests del pipeline y API, y construcción de imagen Docker. **[PROPUESTA]** PR: `ruff check`, `ruff format --check`, `pytest`, test con muestra pequeña y `docker build`. Merge a `main`: repetir verificaciones y generar imagen etiquetada con commit. No se requiere despliegue cloud.

**[APROBADO T26, 2026-11-09]** Perfil exclusivo CI con fixtures: 2 CPU/4 GiB RAM, mínimo 10 GiB disco y 20 minutos por job. No entrena con datos reales; conserva el mínimo de 50 GiB para build local y los presupuestos científicos. El workflow está preparado; se requiere evidencia remota real para cerrar T26, sin publicar imágenes ni implementar T36 ahora.

Cobertura mínima funcional:

1. Ingesta idempotente y error HTTP.
2. Detección de cambio incompatible de esquema.
3. Quality Gate que bloquea lote inválido y emite reporte.
4. Construcción de target y ausencia de leakage.
5. División temporal sin solapamiento.
6. Serialización/carga de pipeline con predicción consistente.
7. API: petición válida, 422, modelo ausente y endpoints informativos.
8. Comparación champion/challenger, rechazo, promoción y rollback.
9. Smoke test de Docker Compose y persistencia de artefactos.

**[PROPUESTA]** Usar fixtures sintéticas y un Parquet de prueba pequeño; CI no debe descargar todos los meses de TLC ni entrenar modelos pesados.

## 13. Estructura del repositorio

```text
nyc-yellow-taxi-mlops/
├── intent.md
├── spec.md
├── plan.md
├── README.md
├── .env.example
├── .gitignore
├── .github/workflows/
│   ├── ci.yml
│   └── retraining.yml
├── configs/
│   ├── data.yaml
│   ├── model.yaml
│   └── monitoring.yaml
├── data/
│   ├── raw/.gitkeep
│   ├── validated/.gitkeep
│   └── processed/.gitkeep
├── notebooks/
├── src/
│   ├── ingestion/
│   ├── validation/
│   ├── features/
│   ├── training/
│   ├── evaluation/
│   ├── monitoring/
│   ├── retraining/
│   └── api/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── api/
├── scripts/
├── reports/
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── Makefile
```

**[BASE]** No subir Parquet grandes, binarios de modelos, MLflow local, credenciales ni reportes pesados a Git. Versionar código, configuración, documentación, fixtures pequeñas y metadatos.

## 14. Interfaces CLI propuestas

Ingesta, validación, features, particionado y baseline ya ofrecen CLI. Los 24 meses tienen features REAL y cuatro particiones publicadas/auditadas. T15 permanece congelada y T16/T17 ya tienen entrenamiento/evaluación reales auditados. Los comandos de candidatos están implementados y requieren entradas explícitas; monitoreo/Docker siguen como contratos objetivo:

```bash
python -m src.ingestion.download --year 2025 --month 01
python -m src.validation.run --year 2025 --month 01
python -m src.features.build --help
python -m src.training.train --help
python -m src.evaluation.run --help
python -m src.monitoring.run --year 2025 --month 07
python -m src.retraining.evaluate --config configs/monitoring.yaml
pytest

docker compose up -d mlflow
docker compose build
```

**[PROPUESTA]** Todo comando debe ofrecer `--help`, devolver código distinto de cero ante error, escribir logs útiles y guardar evidencia cuando corresponda. La sintaxis exacta se congela durante la implementación del `plan.md`.

## 15. Seguridad, operación y reproducibilidad

- No guardar secretos ni credenciales en el repositorio.
- No exponer MLflow o la API fuera de localhost en la demo sin autenticación/red segura.
- Validar payloads, limitar mensajes de error y registrar fallos sin datos sensibles innecesarios.
- Fijar versiones de dependencias y documentar versión de Python y Docker.
- Mantener persistencia local y procedimientos de backup/rollback de metadatos y artefactos.
- Evitar rutas absolutas específicas de Windows; utilizar `pathlib`, variables de entorno y rutas relativas.
- Registrar timestamps operativos en UTC y tratar eventos del taxi con zona `America/New_York`.
- Probar la instalación en una segunda máquina o entorno limpio.

## 16. Criterios de aceptación de la especificación

- [ ] El equipo puede levantar MLflow y API localmente con Compose y datos persistentes.
- [ ] Un mes puede descargarse de forma parametrizada, idempotente y auditable.
- [ ] Un lote inválido es bloqueado con reporte explicativo.
- [ ] Ninguna feature de inferencia depende del final del viaje.
- [x] Baseline y dos candidatos comparados con cortes temporales y métricas trazables; revisión humana de resultados independiente.
- [ ] MLflow identifica el champion vigente y conserva el challenger.
- [ ] `/predict` retorna minutos, versión y timestamp; `/health` y `/model-info` funcionan.
- [ ] CI verifica código, pruebas y construcción Docker.
- [ ] Existe un reporte de drift y una decisión de reentrenamiento justificada.
- [ ] Se demuestra rechazo de challenger, promoción controlada y rollback.
- [ ] Un integrante distinto reproduce el flujo siguiendo el README.

## 17. Decisiones pendientes antes de cerrar versión 1.0

| ID | Decisión | Propuesta inicial | Responsable |
|---|---|---|---|
| D-01 | Meses y volumen | APROBADA: train 2024; validation ene–mar 2025; test original abr–jun; replay jul–dic. Evaluación final independiente ene–mar 2026 aprobada y auditada por separado | equipo |
| D-02 | Límites de hardware | Todos los elegibles; preparación 4/2, entrenamiento 8/4 e inferencia final 2026 6 GiB libres/2 GiB RSS; cuatro hilos, un candidato, 2 h/candidato y 50 GiB disco. Perfiles aprobados y verificados | equipo |
| D-03 | Herramientas | Locks históricos 24/95 intactos; serving Windows 97 y Linux 99 fijados. API/Compose verificados; workflow Actions con Ruff fijado preparado y perfil CI aprobado, ejecución remota pendiente. Evidently pendiente | equipo/docente |
| D-04 | Umbrales DQ | V1 global congelada; diez excepciones exactas de 2025 y tres de ene–mar 2026 aplicadas. 14 lotes pasan calidad y 13 aceptados excepcionalmente; FAIL y exclusiones conservados. Todo incumplimiento nuevo requiere consulta/aprobación | equipo |
| D-05 | Drift/retraining | Reglas automáticas 115 %, PSI 0.20 y 2 % pendientes; elección humana inicial LightGBM v4 aprobada y aplicada en T19 | equipo |
| D-06 | Contrato API | whitelist origen/calendario/pasajeros, convención temporal y catálogo operativo aprobados; destino deshabilitado. Contrato REST completo pendiente | equipo |
| D-07 | Persistencia MLflow | APROBADA/IMPLEMENTADA/VERIFICADA: SQLite y artefactos locales, loopback, entorno aislado y cuatro versiones registradas y LightGBM v4 champion por T19. [Evidencia T18](reports/tracking/t18_completion.md) | equipo |
| D-08 | Criterio de terminado | T14/T15/T16/T17, evaluación final independiente y T18/T19 auditadas con datos reales; revisión humana independiente y criterio general de PR pendiente | equipo |

## 18. Instrucciones para Codex / agente

1. Leer `intent.md` y este `spec.md` antes de proponer código.
2. No implementar el proyecto completo hasta que exista y se apruebe `plan.md`.
3. Tratar `[PENDIENTE]` como decisión abierta, no como autorización implícita.
4. No modificar la definición del target ni incluir variables con leakage.
5. No añadir infraestructura cloud o dependencias principales sin autorización.
6. Antes de cada fase: resumir archivos que creará/modificará, pruebas y criterios de aceptación.
7. Ejecutar pruebas disponibles, informar resultados reales y registrar limitaciones.
8. No declarar completada una tarea sin evidencia verificable.
9. No promover modelos ni sobrescribir datasets/artefactos sin aprobación.
10. Mantener consistencia entre `intent.md`, `spec.md`, `plan.md`, README y código.

## 19. Trazabilidad con el documento académico

- Resumen ejecutivo y arquitectura: páginas 2 y 5.
- Datos, target y política anti-leakage: páginas 3–4.
- Pipeline, CLI, MLflow, API y Docker: página 6.
- Quality Gates y modelos: página 7.
- Métricas, drift y retraining: páginas 8–9.
- Stack, repositorio, CI/CD: páginas 9–10.
- Entregables, aceptación y sprints: páginas 10–12.
- Decisiones abiertas: página 13.

T01 contrastó el texto completo de las 14 páginas del [PDF académico local](Proyecto_Maestria_MLOps_NYC_Taxi_Estructura.pdf). La matriz detallada y sus límites están en [docs/decisions.md](docs/decisions.md); la comprobación documental no demuestra implementación.

**Estado:** documento técnico propuesto, pendiente de aprobación del equipo. Su adopción no implica que las pruebas o los componentes estén implementados.

**Evidencia histórica del ajuste T15 anterior a la excepción:** Ajuste exacto train 2024 completo y auditado: 41.119.495 etiquetas, mediana 12,983333 minutos; 561 filas apartadas por corte de etiqueta entre 41.120.056 elegibles DQ. Evaluación y cierre de T14/T15 pendientes de marzo 2025; D-04 permanece congelada. [ajuste real auditado](reports/quality/t15_train_fit.md). Las referencias previas a ausencia de fit describen el estado anterior a aprobar la separación; el bloqueo de evaluación por D-04 continúa. No cambian objetivo, periodos, reglas ni candidatos.

## 20. Resultados y extensión de modelado — 2026-11-05

SGD Huber y MLP16 se ajustaron con las 41.119.495 filas train, una pasada por candidato. SGD fue elegido con validation antes de abrir test: MAE 6,876910 frente a 7,741890 del baseline. En test obtuvo MAE 7,965068 frente a 9,032999. MLP fue peor que el baseline; SGD empeoró ligeramente P90 en validation. Sin reajustes después de test ni promoción.

[Resultados y segmentos](reports/evaluation/t17_model_comparison.md), [evidencia del software](docs/t16-t17-validation.md). Los artefactos de esta primera comparación quedan congelados. G3 sigue abierto: no hay MLflow, registry ni champion aprobado.

**LightGBM aprobado como extensión:** dependencia 4.7.0 con hashes, seis features causales, origen categórico, todas las filas train, 100 árboles, cuatro hilos y perfil 8 GiB libres/4 GiB RSS. Discretización con hasta 200.000 filas train, sin reducir las filas usadas para ajustar árboles. Evaluación solo con validation; nueva evaluación final independiente pendiente. [Contrato completo](docs/t16-lightgbm-extension-proposal.md). Compatibilidad, límites y ajuste/evaluación reales verificados con auditoría; nueva evaluación final independiente pendiente.

**Resultado de la extensión LightGBM:** LightGBM 4.7.0 fue entrenado con las 41.119.495 filas train y 100 árboles. En las 11.163.264 filas validation: MAE 6.496404, RMSE 9.847425, MedAE 4.631360 y P90 13.478764 minutos. Ajuste y evaluación auditados; 447 pruebas por entorno. Solo validation: una nueva evaluación final independiente sigue pendiente. La selección SGD y el test de la primera comparación permanecen intactos; no hay promoción. [Reporte](reports/evaluation/lightgbm_validation.md). Sus CLI implementados son `python -m src.training.lightgbm_train --help` y `python -m src.evaluation.lightgbm_run --help`. No acepta una opción para evaluar test/replay.


**Evaluación final independiente completada y auditada — 2026-11-05:**
enero–marzo de 2026, 10.937.087 viajes; MAE LightGBM **7,742891 min**, SGD
**8,352735** y baseline **9,141254**. Se excluyeron 139.305 filas DQ mediante
tres excepciones humanas exactas y 814 por corte de etiqueta; los 27 raw,
modelos y selección de 2025 permanecen intactos. Reinicio de recursos aprobado
6 GiB libres/2 GiB RSS solo para inferencia final; entrenamiento 8/4 y preparación
4/2 sin cambios. 474 pruebas por entorno y auditoría completa. Sin promoción.
[Reporte final y trazabilidad](reports/evaluation/lightgbm_final_evaluation.md). Las referencias anteriores a evaluación
final pendiente describen la entrega histórica previa a esta aprobación. T18
requiere D-07 y dependencias; no hay Registry ni champion todavía.


**T18 verificada — 2026-11-05:** D-07 aprobada e implementada con MLflow 3.16.1
en entorno separado, SQLite y artefactos persistentes. Cuatro candidatos:
baseline v1, SGD v2, MLP v3 y LightGBM v4, sin alias. Reinicio real, carga,
idempotencia y auditoría independiente PASS; 488 pruebas nativas más una omisión
explícita y 489 sobre wheel MLflow. Los modelos y evaluaciones anteriores no
cambian. Champion/T19 y G3 permanecen pendientes de aprobación.
[Registro y evidencia](reports/tracking/t18_completion.md). Las referencias previas a D-07 o Registry
pendientes describen la cronología anterior a esta aprobación y ejecución.


**T19 verificada — 2026-11-05:** el usuario aprobó LightGBM v4 como champion
inicial, después de conocer las limitaciones por rutas, y descartó optimización
de hiperparámetros. Alias `champion` aplicado a la versión fija 4, run
`be28c76c84c44efa8914c5950a2959bf`; paquete, aprobación y resolución auditados.
501 pruebas nativas PASS y dos omisiones explícitas; 503 PASS sobre wheel MLflow.
G3 cumple sus condiciones de Sprint 3. D-05 conserva pendientes sus reglas
automáticas de drift y promociones futuras; no se aprueban nuevos umbrales.
[Decisión, pruebas y evidencia](reports/model_selection.md). Las menciones anteriores a champion
pendiente son históricas; API y despliegue siguen en sus tareas posteriores.
