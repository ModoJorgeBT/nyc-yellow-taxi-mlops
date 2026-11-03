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

**[BASE: recomendación académica, aún por confirmar]** entrenamiento: enero–septiembre de 2025; validación: octubre de 2025; prueba: noviembre–diciembre de 2025; simulación de lotes productivos: meses disponibles de 2026.

**[PENDIENTE]** Aprobar meses concretos, límite de filas/muestreo y recursos locales. Si se utiliza muestreo, debe ser reproducible, documentado y respetar las fronteras temporales. Nunca se realiza split aleatorio entre entrenamiento y prueba como protocolo principal.

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
trip_duration_minutes = (
    tpep_dropoff_datetime - tpep_pickup_datetime
).total_seconds() / 60.0
```

**[BASE]** El target se calcula únicamente para entrenamiento/evaluación; `tpep_dropoff_datetime` nunca es una entrada de inferencia.

**Features admisibles al inicio:** `PULocationID`, `DOLocationID`, hora/semana/mes derivados de `tpep_pickup_datetime`, `passenger_count` si está disponible, `RatecodeID` solo tras validar su disponibilidad operativa y agregados históricos calculados con datos anteriores al instante de predicción.

**Features prohibidas en MVP:** `tpep_dropoff_datetime`, `trip_duration_minutes`, `fare_amount`, `total_amount`, `tip_amount`, `payment_type`, `tolls_amount`, cargos finales y `trip_distance` medida por taxímetro. Tampoco utilizar campos indirectamente derivados del resultado del viaje.

**[PROPUESTA]** Para simplificar el primer modelo, iniciar con origen, destino y calendario de recogida. `passenger_count` será opcional con tratamiento explícito de ausencias; `RatecodeID` y agregados históricos quedan deshabilitados hasta verificar su disponibilidad y causalidad. El contrato API no exigirá información que el usuario no pueda conocer al inicio.

**[PENDIENTE: D-06]** Aprobar la hipótesis de destino declarado al inicio y el uso del destino histórico observado como aproximación. La lista anterior de features admisibles no autoriza todavía el uso de `DOLocationID`. Resolver antes de T12/T13 y de cerrar el contrato REST; no cambiar el target para resolver esta incertidumbre.

**Regla de consistencia:** serializar un único pipeline de preprocesamiento + estimador; reutilizarlo en inferencia, sin reconstruir transformaciones ad hoc. Los agregados de ruta, si se incorporan, se calculan mediante ventanas históricas sin mirar al futuro y deben poder resolverse en serving.

## 6. Data Quality Gates

**[BASE]** Comprobar esquema, volumen, fechas, duración, duplicados, nulos de zonas, categorías, rangos, cambios de esquema y trazabilidad. Cada gate genera resultado `PASS`, `WARN` o `FAIL`, con regla, valor observado, umbral, severidad y evidencia. Un fallo crítico detiene el pipeline y no genera un dataset aprobado.

Los reportes de lotes rechazados también alimentan la observación de calidad. Los datos rechazados no pasan al entrenamiento ni se presentan como lotes aprobados para evaluación de desempeño. El monitoreo de drift requiere una referencia aprobada e identificable, aún pendiente de definición en D-05.

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
| Integridad | URL, hash, año/mes y timestamp obligatorios |

**Precisión importante:** distinguir la **tasa de registros inválidos** del **fallo del lote completo**. **[PROPUESTA]** Una fracción tolerable de filas inválidas puede excluirse con reporte; fallos estructurales, ausencia de columnas esenciales o tasas superiores a límites aprobados bloquean el lote. No asumir que cualquier fila de duración inválida debe abortar automáticamente millones de registros.

**[PENDIENTE]** Aprobar umbrales cuantitativos definitivos tras EDA.

**[IMPLEMENTADO T08/T09, alcance aprobado]** `configs/data.yaml` usa sintaxis JSON compatible con YAML, sin parser adicional. Esenciales: pickup/dropoff `timestamp[us]` sin zona y zonas enteras con signo de 32/64 bits; otros campos históricos opcionales, comprobados si existen. Se conserva `Airport_fee`; `cbd_congestion_fee` es conocido opcional. El motor devuelve reportes en memoria con tasas/conteos y versiones; configuración real PENDIENTE y controles no evaluados explícitos. Un perfil TEST_ONLY completo solo puede superar calidad con fixtures marcadas; `approved_for_training=false` y linaje no comprobado hasta T10. La semántica de reloj local usada en pruebas no resuelve DST de D-06. Ningún límite sintético se adopta para TLC; T09 no tiene cierre operativo mientras D-04 siga abierta.

**[IMPLEMENTADO T10/T11, alcance de prueba]** El CLI verifica manifiesto/hash antes y después de escanear y contrasta filas leídas con el footer; reutiliza elegibilidad T09 para escribir por bloques. Modo normal: rechazo por política real pendiente, sin lectura de filas ni dataset. `--test-only`: exige perfil y fixture de prueba, publica bajo `data/validated/_test_only/YYYY/MM/<id>/` y conserva `approved_for_training=false`. Reportes JSON por intento en `reports/quality/`, con configuración y linaje; `validation.json` interno es marcador final. Fallos no habilitan datos; no existe transacción conjunta de todos los archivos. Los 24 Parquet siguen sin incorporación automática ni validación de filas.

## 7. Modelado y evaluación

**[BASE]** Baseline de mediana global o por ruta/franja; dos modelos candidatos, por ejemplo `HistGradientBoostingRegressor` y `RandomForestRegressor`/`GradientBoostingRegressor`. Usar particiones cronológicas y registrar semillas, hiperparámetros, versión de datos y código.

**Métricas:** MAE (principal, minutos), RMSE, MedAE y percentil 90 del error absoluto. Latencia p95 se mide por separado como métrica de servicio.

**[PROPUESTA]** Entrenar primero un baseline global; luego al menos dos candidatos con el mismo protocolo temporal. La selección se basa en validación; el conjunto de prueba permanece reservado para evaluación final. Reportar resultados por mes, franja y zonas/rutas frecuentes cuando haya soporte estadístico suficiente. No afirmar mejora porcentual hasta medirla.

**[PENDIENTE]** Determinar presupuesto de CPU/RAM y estrategia de muestreo/entrenamiento incremental si fuese necesaria.

## 8. MLflow Tracking y Model Registry

**[BASE]** Registrar parámetros, métricas, artefactos, datasets, versiones de código y modelos; separar entrenamiento de promoción. **[PROPUESTA]** Ejecutar MLflow local como servicio de Compose, con base de metadatos SQLite y directorio persistente de artefactos en volúmenes montados. Establecer `MLFLOW_TRACKING_URI=http://mlflow:5000` entre contenedores y `http://localhost:5000` desde el host.

Cada run debe incluir: nombre de experimento, versión de dataset, rango temporal, configuración, semilla, commit Git cuando exista, métricas, pipeline serializado y evaluación. El modelo registrado se identifica mediante nombre estable, versión y alias de operación (`champion`, si la versión de MLflow elegida lo permite). No asumir que el último run es el modelo en producción.

**[PROPUESTA]** Promoción mediante comando explícito con auditoría de versión previa, nueva versión, métricas comparativas, fecha, responsable y resultado de smoke tests. Rollback revierte el alias o puntero de versión y reinicia/recarga el servicio de forma controlada.

## 9. Contrato REST de inferencia

**[BASE]** Endpoints `POST /predict`, `GET /health` y `GET /model-info`, validación Pydantic y respuesta con predicción, unidad, versión y timestamp.

**[PROPUESTA: contrato v1]**

`POST /predict`

```json
{
  "pickup_datetime": "2026-03-12T08:30:00-04:00",
  "pickup_location_id": 161,
  "dropoff_location_id": 236,
  "passenger_count": 1
}
```

`passenger_count` es opcional; los identificadores de zona deben ser enteros positivos y validados frente al catálogo aprobado. **La fecha/hora debe incluir zona horaria**: convertir a `America/New_York` para extraer las características y manejar correctamente DST. No aceptar timestamps ambiguos sin offset salvo decisión documentada.

Respuesta `200` de ejemplo **ilustrativo, no una predicción real**:

```json
{
  "predicted_duration_minutes": 18.4,
  "unit": "minutes",
  "model_version": "3",
  "predicted_at_utc": "2026-11-03T16:00:00Z"
}
```

`GET /health`: `200` solo si API y modelo activo están listos; `503` si falta el modelo. **[PROPUESTA]** Responder `{"status":"ok","model_loaded":true}`.

`GET /model-info`: nombre, versión activa, fecha de entrenamiento (si se registra), rango de datos y estado; **no revelar secretos ni rutas internas**.

Errores: `422` para payload inválido; `503` para ausencia de modelo; `500` para error inesperado sin exponer trazas al cliente. **[PROPUESTA]** La API carga una versión aprobada al iniciar; un cambio de champion requiere recarga/reinicio controlado.

## 10. Docker Compose y persistencia local

**[DECISIÓN]** Ejecutar la solución en local con Docker Compose.

**[PROPUESTA]** Servicios mínimos:

- `mlflow`: puerto host `5000`, almacenamiento persistente de tracking/artefactos; sin exposición pública.
- `api`: puerto host `8000`, carga del champion aprobado; depende de disponibilidad de artefactos/modelo.
- `pipeline`: perfil o servicio de ejecución bajo demanda para ingesta, entrenamiento, monitoreo y retraining; no requiere puerto abierto.

Montajes separados para datos, tracking y reportes. Variables configurables por `.env.example`; `.env` real excluido de Git. No publicar puertos en interfaces públicas por defecto; para desarrollo, enlazar al loopback del host cuando sea viable. Usar versiones de imágenes/dependencias fijadas, usuario no root donde sea viable, health checks y arranque documentado.

**Dependencia crítica:** Docker Compose **no crea por sí mismo un modelo champion**. El README debe documentar el bootstrap: ingesta → calidad → entrenamiento → registro → aprobación → arranque de API (o estado `503` hasta completar la promoción).

## 11. Monitoreo y reentrenamiento

**[BASE]** Monitorear calidad de entradas, drift de distribuciones, desempeño cuando existan etiquetas verdaderas y métricas del servicio (latencia p50/p95, tasa de errores 4xx/5xx, throughput, disponibilidad). **[PROPUESTA: D-03 pendiente]** Utilizar Evidently para reportes por ventana temporal.

**[PROPUESTA: D-05 pendiente, PDF §9.1]** Posible trigger si MAE mensual supera 115 % del MAE de referencia durante dos ventanas consecutivas; PSI > 0.20 en features críticas; cambios sostenidos de calidad/esquema; evaluación trimestral preventiva. Estos valores no están aprobados como configuración ejecutable.

**[BASE]** Separar entrenamiento de promoción, exigir calidad, pruebas y evaluación por segmentos; si falla, champion permanece activo. **[PROPUESTA: D-05 pendiente, PDF §9.2]** Exigir mejora de MAE de al menos 2 % **o** no inferioridad predefinida, junto con smoke tests. El margen de no inferioridad y las tolerancias por segmento aún deben definirse y aprobarse.

**[PROPUESTA]** Los triggers generan una **recomendación auditable**, no una promoción automática. Registrar reportes y decisiones `NO_ACTION`, `RETRAIN_RECOMMENDED`, `CHALLENGER_REJECTED`, `PROMOTED`, `ROLLED_BACK`. Para medir performance se requieren etiquetas posteriores al viaje: no inferir MAE a partir de solicitudes sin ground truth.

## 12. CI/CD y pruebas

**[BASE]** GitHub Actions debe ejecutar lint/formato, unit tests, smoke tests del pipeline y API, y construcción de imagen Docker. **[PROPUESTA]** PR: `ruff check`, `ruff format --check`, `pytest`, test con muestra pequeña y `docker build`. Merge a `main`: repetir verificaciones y generar imagen etiquetada con commit. No se requiere despliegue cloud.

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

Ingesta y validación ya ofrecen CLI; validación real permanece bloqueada por política pendiente. Los comandos de features/modelado/monitoreo/Docker siguientes son **contratos objetivo**, no componentes ya implementados:

```bash
python -m src.ingestion.download --year 2025 --month 01
python -m src.validation.run --year 2025 --month 01
python -m src.features.build --year 2025 --month 01
python -m src.training.train --config configs/model.yaml
python -m src.monitoring.run --year 2026 --month 01
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
- [ ] Baseline y dos candidatos se comparan con cortes temporales y métricas trazables.
- [ ] MLflow identifica el champion vigente y conserva el challenger.
- [ ] `/predict` retorna minutos, versión y timestamp; `/health` y `/model-info` funcionan.
- [ ] CI verifica código, pruebas y construcción Docker.
- [ ] Existe un reporte de drift y una decisión de reentrenamiento justificada.
- [ ] Se demuestra rechazo de challenger, promoción controlada y rollback.
- [ ] Un integrante distinto reproduce el flujo siguiendo el README.

## 17. Decisiones pendientes antes de cerrar versión 1.0

| ID | Decisión | Propuesta inicial | Responsable |
|---|---|---|---|
| D-01 | Meses y volumen | histórico 2025 y lotes disponibles 2026 | equipo |
| D-02 | Límites de hardware | host y muestra T05 medidos; presupuesto de entrenamiento/muestreo y límites Docker pendientes | equipo |
| D-03 | Herramientas | T03: Python 3.14.7, setuptools/Ruff/Pytest/pip-tools y PyArrow aprobados y fijados; MLflow/FastAPI/Compose confirmados sin instalar; resto pendiente | equipo/docente |
| D-04 | Umbrales DQ | esquema T08 aprobado; motor T09 probado con políticas sintéticas; configuración real PENDIENTE y tasas, duración, volumen/catálogos pendientes | equipo |
| D-05 | Drift/retraining | evaluar 115 %, PSI 0.20 y 2 % como hipótesis | equipo |
| D-06 | Contrato API | aprobar payload v1, zonas horarias e hipótesis de destino conocido | equipo |
| D-07 | Persistencia MLflow | SQLite + artefactos en volumen local | equipo |
| D-08 | Criterio de terminado | T10/T11 autorizadas y verificadas técnicamente con fixtures para revisión humana; flujo real sin cierre operativo, criterio general de PR pendiente | equipo |

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
