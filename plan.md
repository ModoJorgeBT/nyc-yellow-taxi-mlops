# PLAN — Implementación incremental NYC Yellow Taxi MLOps

**Versión:** 1.0 · **Estado:** T10/T11 autorizadas e implementadas, verificadas técnicamente con fixtures para revisión humana; flujo real sin cierre operativo por D-04/D-06; T12–T38 no ejecutadas · **Entorno:** VS Code + Codex, ejecución local Docker Compose.
**Fuentes de verdad:** `intent.md`, `spec.md`, y PDF académico *Proyecto_Maestria_MLOps_NYC_Taxi_Estructura*, septiembre 2026. En caso de contradicción, detenerse y pedir decisión; no cambiar el alcance silenciosamente.

## 0. Protocolo obligatorio para Codex

1. Leer los tres documentos Markdown antes de modificar archivos. Seguir una tarea identificada por ID a la vez; no implementar todo el plan en un solo prompt.
2. Antes de escribir: describir archivos previstos, comandos y pruebas. Solicitar confirmación para cambios destructivos, instalación global, descargas voluminosas, cambios de contratos o promoción de modelos.
3. Implementar código mínimo, tipado y testeable. Ejecutar pruebas de la tarea; informar comandos, resultado real y archivos afectados. Si no se pueden ejecutar, indicar `NO VERIFICADO`.
4. No usar datos futuros o variables post-viaje en inferencia; no filtrar información de validación/prueba al entrenamiento. Nunca inventar métricas.
5. Mantener el checklist de este plan actualizado únicamente con evidencia real (commit, test, archivo o captura). No marcar tareas completadas por escribir código sin probarlo.
6. No subir datasets grandes, modelos binarios, `.env`, bases SQLite de MLflow ni secretos a Git.
7. Cada tarea concluye con una revisión humana antes de la siguiente. Los comandos aquí son contratos previstos, no pruebas de que ya existan.

## 1. Decisiones y gates previos

| ID | Decisión | Valor de trabajo / criterio | Estado |
|---|---|---|---|
| D-01 | Periodos | Propuesta PDF: train ene–sep 2025, val oct 2025, test nov–dic 2025; monitoreo 2026. Disponibles localmente 24 archivos 2024/2025; no implica usarlos todos ni reasignar periodos | PENDIENTE aprobación |
| D-02 | Recursos y muestreo | Host y lectura acotada T05 medidos; muestra posicional 2024 autorizada, sin equivaler a protocolo de entrenamiento | PARCIAL: presupuesto y límites Docker pendientes |
| D-03 | Herramientas | Python 3.14.7, setuptools, Ruff, Pytest, pip-tools y PyArrow aprobados/fijados en T03; MLflow/FastAPI/Compose confirmados sin instalar; Pandas, sklearn, Pydantic, GitHub Actions y Evidently pendientes | PARCIAL; no equivale a compatibilidad del stack completo |
| D-04 | Umbrales DQ | Contrato estructural T08 aprobado; motor T09 probado con políticas sintéticas; tolerancias, volumen, duración y catálogo reales pendientes | PARCIAL; aprobación operativa pendiente |
| D-05 | Drift y promoción | Evaluar propuestas PDF: MAE > 115 % dos ventanas, PSI > 0.20, mejora MAE ≥ 2 % o no inferioridad definida | PENDIENTE |
| D-06 | API | `pickup_datetime` con offset, zonas origen/destino, pasajero opcional; America/New_York; hipótesis de destino conocido | PENDIENTE aprobación |
| D-07 | MLflow | SQLite persistente y artefactos locales; registry y alias champion según versión compatible | PENDIENTE prueba |
| D-08 | Definition of Done | Continuación T10/T11 solicitada; integración offline y CLI probados para revisión humana, datos reales bloqueados | PARCIAL; criterio general de PR pendiente |

**Gate G0:** no comenzar descargas masivas ni entrenamiento real antes de aprobar D-01/D-02/D-04. Continuación T10/T11 autorizada conservando configuración real PENDIENTE y bloqueo de aprobación hasta resolver D-04/D-06. Solo resultados sintéticos TEST_ONLY aislados, nunca aprobación para entrenamiento. Los 24 Parquet siguen sin incorporación a manifiestos. No se aprueban ventanas ni límites reales. El usuario autorizó después publicar el proyecto en GitHub, con commit inicial sobre `main`; los estados «sin commits/remotos» de las tareas anteriores son evidencia histórica. T12 y siguientes requieren autorización. Ver [docs/decisions.md](docs/decisions.md).

## 2. Mapa de dependencias y sprints

```text
S1 Arquitectura y repositorio (T01–T05)
     └── S2 Ingesta y calidad (T06–T11)
             └── S3 Features y modelos (T12–T19)
                     ├── S4 Serving y Docker (T20–T25)
                     └── S5 CI y observabilidad (T26–T31)
                              └── S6 Retraining, rollback y demo (T32–T38)
```

Las dependencias son técnicas, no fechas prometidas. Algunos tests de CI pueden prepararse antes de S5. **Orden crítico:** no iniciar la API con un champion inexistente; no calcular desempeño sin etiquetas; no promover un challenger sin gates.

## 3. Sprint 1 — Arquitectura, entorno y EDA técnica

**Resultado:** repositorio reproducible, convenciones, contratos y muestra verificable.

### T01 — Auditoría de requisitos y decisiones
- **Depende de:** ninguno.
- **Trabajo:** comparar `intent.md`, `spec.md` y PDF; registrar D-01…D-08 y riesgos; confirmar el único target (duración en minutos).
- **Entregables:** `docs/decisions.md`, `docs/architecture.md` con diagrama lógico y ADR inicial.
- **Aceptación/prueba:** matriz de trazabilidad y lista de pendientes; revisión del equipo; no modificar target ni alcance.
- **Estado T01:** COMPLETADA; correcciones y verificación documental realizadas. Cierre humano aprobado por el usuario el 2026-11-03 al solicitar T03. G0/G1 siguen pendientes.
- **Evidencia:** [decisiones y validación](docs/decisions.md), [arquitectura](docs/architecture.md), [ADR inicial](docs/adr/0001-arquitectura-local.md).
- **Dependencias posteriores:** T02 verifica estructura/importaciones/exclusiones; instalación reproducible y suite corresponden a T03. T04 depende de T03 y T34 depende de T25. T18 debe resolver D-07 y su entorno de prueba local antes del Compose completo de T24; no se implementa infraestructura en T01/T02.

### T02 — Scaffolding del repositorio
- **Depende de:** T01.
- **Autorización:** el equipo aprobó su preparación junto a las correcciones de T01; el cierre humano de ambos entregables se registra tras su presentación.
- **Trabajo:** crear estructura `src/{ingestion,validation,features,training,evaluation,api,monitoring,retraining}`, `tests/{unit,integration,api}`, `configs`, `scripts`, `reports`, `data/{raw,validated,processed}`, `.github/workflows` y `README.md`.
- **Entregables:** estructura de `spec.md`, `.gitignore`, `.env.example`, archivos `__init__.py` donde corresponda.
- **Aceptación/prueba:** estructura e importaciones de paquetes verificadas sin dependencias externas; referencias locales válidas; Git local en `main`, sin commits/remotos; exclusión de datos/secretos comprobada mediante `git check-ignore` y revisión del índice/estado. `.env.example` y marcadores se pueden versionar. No incluir rutas absolutas Windows en archivos del proyecto. Si existe Pytest, `python -m pytest --version` acredita solo disponibilidad; la instalación reproducible y la suite exitosa se verifican en T03. No añadir tests ficticios para declarar éxito.
- **Datos locales:** preparar `data/raw/`; el equipo colocará los Parquet por año/mes, sin inventariar ni procesar sus contenidos en T02. Su existencia no aprueba D-01 ni calidad/procedencia.
- **Estado T02:** COMPLETADA; verificaciones técnicas PASS y cierre humano aprobado por el usuario el 2026-11-03. Git local en `main` sin commits/remotos. Evidencia y límites: [verificación T02](docs/t02-verification.md).

### T03 — Entorno Python y calidad de código
- **Depende de:** T02.
- **Trabajo:** `pyproject.toml`, versión de Python documentada, dependencias fijadas/lock reproducible, Ruff y Pytest.
- **Entregables:** configuración de proyecto, `Makefile` opcional con comandos equivalentes Windows.
- **Aceptación/prueba:** instalación en venv limpio, `ruff check .`, `ruff format --check .`, `pytest -q` exitosos; registrar versiones.
- **Acuerdo de implementación:** Python 3.14.7; `.venv`; setuptools/Ruff/Pytest/pip-tools y PyArrow aprobados. Lock con versiones transitivas y hashes. No instalar todavía MLflow/FastAPI ni dependencias de modelado/monitoring pendientes.
- **Revisión adicional autorizada:** organizar y leer metadatos/esquemas de los 24 Parquet aportados; sin escanear todas sus filas, fijar umbrales ni ejecutar T04/T05 completas.
- **Evidencia:** [entorno T03](docs/t03-environment.md) e [inventario de datos](reports/raw_inventory.md).
- **Estado T03:** verificaciones técnicas PASS y continuación humana autorizada al solicitar T04/T05. Lock de 15 paquetes y hashes, instalación editable/wheel en segundo venv y calidad de código verificados. La evidencia histórica de T03 no cierra G0/G1.

### T04 — Fixtures y contratos de datos
- **Depende de:** T02, T03.
- **Trabajo:** generar Parquet sintético pequeño con columnas esenciales, viajes válidos, nulos, fechas inválidas y cambios de esquema; no usar datos reales en CI.
- **Entregables:** `tests/fixtures/`, factoría de datos sintéticos y tests de lectura.
- **Aceptación/prueba:** fixtures deterministas con semilla, tests que detecten cada anomalía.
- **Estado T04:** verificada técnicamente: diez Parquet sintéticos pequeños, semilla 42, contrato y pruebas offline. Los datos reales no sustituyen anomalías controladas. Revisión final pendiente; evidencia en [T04/T05](docs/t04-t05-verification.md).

### T05 — Perfilado técnico de muestra TLC
- **Depende de:** T03, T04 y aprobación del perfilado acotado; aprobación de descarga pequeña solo si faltan archivos locales adecuados.
- **Trabajo:** inventariar los Parquet locales aportados y perfilar una muestra limitada; descargar únicamente si hace falta y se autoriza. Inspeccionar esquema, nulos, rango de duración, volumen, RAM, cambios entre meses y zonas. Registrar procedencia desconocida sin inventar fechas/URL; no dar por aprobada la ingesta o calidad por colocar archivos en raw.
- **Entregables:** `reports/eda_schema.md`, evidencia de memoria y propuesta de umbrales DQ; no versionar datos grandes.
- **Aceptación/prueba:** métricas observadas y reproducibles, diferencias documentadas respecto al diccionario; revisión D-02/D-04.
- **Alcance aprobado:** solo 2024, primeras 2.048 filas de cada row group de sus doce meses; no representativo ni protocolo de entrenamiento. 2025 sin perfilado de filas; no se aprueban umbrales ni periodos.
- **Estado T05:** verificada técnicamente: 90.112 filas, recursos medidos, repetibilidad de rangos/hashes/estadísticas y reporte [EDA](reports/eda_schema.md). D-02 parcial y D-04 pendiente; revisión final pendiente.

**Gate G1:** ambiente reproducible, fixtures y decisiones documentadas; al menos un test de ejemplo verde.

Evidencia técnica G1 disponible en [verificación T04/T05](docs/t04-t05-verification.md): entorno, fixtures, decisiones registradas y 32 tests aprobados. El usuario solicitó después continuar con T06/T07. Esa autorización permite esas tareas, sin declarar cerradas D-01/D-02/D-04 ni los gates restantes.

## 4. Sprint 2 — Ingesta, trazabilidad y Data Quality

### T06 — Descarga parametrizada
- **Depende de:** T03, T04.
- **Trabajo:** implementar `python -m src.ingestion.download --year YYYY --month MM`, URL TLC, timeout, reintentos limitados, descarga temporal y validación Parquet.
- **Entregables:** `src/ingestion/download.py`, tests de red simulada.
- **Aceptación/prueba:** `--help`, manejo de 404/timeout, descarga sin archivos parciales, código de salida distinto de cero ante fallo.
- **Implementación:** `urllib` de biblioteca estándar y PyArrow ya aprobado; escritura temporal, timeout por operación, reintentos limitados, bloqueo por lote y publicación sin reemplazo. Pruebas con red simulada, sin descargar Parquet reales.
- **Estado T06:** verificación técnica PASS: CLI/help instalado desde wheel, pruebas de 404/timeout/reintentos/Parquet inválido y limpieza. Suite completa de 69 pruebas aprobada en desarrollo y en checkout sin src/raw con paquete instalado. Revisión humana pendiente.
- **Evidencia:** [T06/T07](docs/t06-t07-ingestion.md).

### T07 — Manifiestos, hash e idempotencia
- **Depende de:** T06.
- **Trabajo:** guardar URL, año/mes, fecha UTC, tamaño, SHA-256, esquema y estado; saltar lote idéntico; no sobrescribir divergencias sin autorización.
- **Entregables:** manifiesto JSON por lote y pruebas.
- **Aceptación/prueba:** segunda ejecución `SKIPPED`, hash consistente, conflicto explícito ante contenido distinto.
- **Política aprobada:** archivo local sin manifiesto bloquea salvo `--register-local`; ese registro conserva bytes y deja fuente/fecha de descarga desconocidas, sin aprobación de calidad. Se implementa/prueba con fixtures, sin aplicarlo a los 24 Parquet.
- **Estados:** manifiesto persistente DOWNLOADED o LOCAL_UNVERIFIED; ejecución SKIPPED no cambia procedencia. Conflictos/fallos conservan evidencia en log por lote y no permiten sobrescritura.
- **Estado T07:** verificación técnica PASS: SHA-256, esquema/volumen, SKIPPED sin red, registro local, divergencias, concurrencia y fallo intermedio probados con fixtures. Los 24 Parquet reales siguen sin manifiestos de ingesta nuevos. Revisión humana pendiente; G2 no cerrado.
- **Evidencia:** [T06/T07](docs/t06-t07-ingestion.md).

### T08 — Contrato y validación de esquema
- **Depende de:** T04, T05, T07.
- **Trabajo:** esquema esperado versionado, campos críticos, tipos, columnas nuevas compatibles y cambios incompatibles.
- **Entregables:** `src/validation/schema.py`, `configs/data.yaml`.
- **Aceptación/prueba:** fixtures con columna faltante/tipo incompatible bloqueadas; columnas adicionales reportadas según política.
- **Contrato aprobado:** cuatro esenciales (pickup/dropoff y zonas); otras columnas históricas opcionales con tipo comprobado, Airport_fee conservado, cbd_congestion_fee opcional y adicionales WARN. Compatibilidad int32/int64, string/large_string; timestamps sin zona en microsegundos, doubles conservados.
- **Estado T08:** verificación técnica PASS, revisión humana final pendiente. Evidencia: [T08/T09](docs/t08-t09-validation.md); 129 pruebas en suite total, 60 nuevas de esquema/calidad.

### T09 — Reglas de calidad por registro y lote
- **Depende de:** T08 y D-04.
- **Trabajo:** fechas pickup/dropoff, duración positiva, mes de pickup, zonas, duplicados, nulos, pasajeros y volumen; distinguir fila descartada de lote rechazado.
- **Entregables:** `src/validation/rules.py`, reporte PASS/WARN/FAIL con observación y umbral.
- **Aceptación/prueba:** un gate crítico impide salida aprobada; anomalías toleradas se contabilizan; casos limítrofes de cambio de mes probados.
- **Excepción de alcance aprobada por el usuario:** implementar/probar el motor con políticas sintéticas sin resolver D-04; configuración real PENDIENTE, catálogo/políticas explícitos, sin eliminar duplicados ni aprobar lotes reales.
- **Estado T09:** motor verificado técnicamente; SIN CIERRE OPERATIVO hasta aprobar D-04 y semántica histórica D-06. Reportes PASS/WARN/FAIL probados; approved_for_training siempre false hasta la integración/decisiones posteriores. [Evidencia y límites](docs/t08-t09-validation.md).

### T10 — Pipeline raw → validated
- **Depende de:** T07–T09.
- **Trabajo:** CLI `python -m src.validation.run --year YYYY --month MM`; persistir datos validados y reportes por lote con escritura segura.
- **Entregables:** `src/validation/run.py`, `data/validated/` (ignorado en Git), `reports/quality/`.
- **Aceptación/prueba:** ejecución con fixture válida, fallo controlado con fixture inválida, trazabilidad al manifiesto raw.
- **Alcance actual:** CLI verifica integridad y exhaustividad, reutiliza exclusiones T09, persiste reportes por intento y salidas sintéticas aisladas con marcador final, sin reemplazos. Modo normal bloqueado, approved_for_training=false; configuración real sin cambios.
- **Estado T10:** verificación técnica PASS con fixtures, revisión humana pendiente y SIN CIERRE OPERATIVO hasta resolver D-04/D-06. [Evidencia T10/T11](docs/t10-t11-data-pipeline.md).

### T11 — Pruebas de integración de datos
- **Depende de:** T10.
- **Trabajo:** simular descarga → manifiesto → validación con fixtures y respuestas HTTP mock.
- **Entregables:** `tests/integration/test_data_pipeline.py`.
- **Aceptación/prueba:** éxito y fallo reproducibles sin Internet, sin datos TLC grandes.
- **Estado T11:** verificación técnica PASS: 33 pruebas de integración nuevas, 162 en suite total; HTTP simulado, gates críticos, exclusiones, integridad, fallos de lectura/publicación, reejecución y CLI. No prueba Internet ni operación con datos reales. Revisión humana pendiente. [Evidencia](docs/t10-t11-data-pipeline.md).

**Gate G2:** ingesta idempotente, calidad auditable y bloqueo de datos no aprobados.

Evidencia técnica offline disponible en T06–T11. G2 no se marca cerrado operativamente: D-04/D-06 siguen pendientes, no se han aprobado ni validado filas de los 24 lotes reales y falta revisión humana.

## 5. Sprint 3 — Features, modelado, MLflow

### T12 — Target y selección anti-leakage
- **Depende de:** T10, D-06 para aprobar las features de destino.
- **Trabajo:** derivar duración solo para entrenamiento; whitelist de origen/destino/calendario; prohibir dropoff, tarifas, propinas, pagos, taxímetro y target como predictores.
- **Entregables:** `src/features/target.py`, `src/features/schema.py`.
- **Aceptación/prueba:** test automatizado comprueba columnas permitidas y que ninguna variable post-viaje llega al estimador.

### T13 — Transformaciones reutilizables
- **Depende de:** T12, D-06.
- **Trabajo:** features de hora/día/mes en America/New_York; tratamiento explícito de pasajero opcional; serializar preprocesador junto al estimador.
- **Entregables:** `src/features/build.py`, pipeline sklearn y pruebas de DST/zonas horarias.
- **Aceptación/prueba:** mismo payload produce mismas features en train/serving; timestamps sin offset rechazados según contrato.

### T14 — Particiones temporales y muestreo
- **Depende de:** T10, T13, D-01/D-02.
- **Trabajo:** cortes cronológicos configurables, muestreo determinista por partición, separación estricta de train/val/test.
- **Entregables:** `src/training/split.py`, `configs/model.yaml`.
- **Aceptación/prueba:** `max(train.time) < min(val.time)` y `max(val.time) < min(test.time)`; sin solapamiento de filas; misma semilla reproduce muestras.
- **Aceptación temporal adicional:** verificar etiquetas disponibles al corte; probar viajes que empiezan antes y terminan después del corte, excluyéndolos del entrenamiento simulado en ese instante. Documentar replay retrospectivo frente a disponibilidad real de publicación de lotes, conforme a la política aprobada D-01/D-06; no inferir disponibilidad por el solo mes del archivo.

### T15 — Baseline
- **Depende de:** T14.
- **Trabajo:** mediana global o por ruta/franja calculada solo con train; predicción de validación.
- **Entregables:** `src/training/baseline.py` y artefacto de resultados.
- **Aceptación/prueba:** predicciones finitas y positivas; baseline reproducible; no utilizar test para elegir modelos.

### T16 — Dos modelos candidatos
- **Depende de:** T14, T15.
- **Trabajo:** HistGradientBoostingRegressor y RandomForestRegressor o GradientBoostingRegressor; controlar memoria, semillas y preprocesamiento compatible.
- **Entregables:** `src/training/train.py`, configuraciones de hiperparámetros.
- **Aceptación/prueba:** entrenamiento en fixture/muestra acotada, inferencia válida y métricas registrables para ambos.

### T17 — Evaluación temporal y segmentos
- **Depende de:** T15, T16.
- **Trabajo:** MAE, RMSE, MedAE, P90 error absoluto; análisis por mes/franja/rutas frecuentes; elegir con validación y reservar test para reporte final.
- **Entregables:** `src/evaluation/metrics.py`, `reports/evaluation/`.
- **Aceptación/prueba:** tests de métricas con valores conocidos; no ajustar hiperparámetros tras mirar test.

### T18 — MLflow tracking y Registry
- **Depende de:** T16, T17, D-07.
- **Precondición por resolver en D-07:** acordar y probar el entorno local acotado de MLflow antes de esta tarea; Compose completo sigue en T24. No asumir infraestructura disponible por su aparición en el diagrama.
- **Trabajo:** registrar parámetros, métricas, artefactos, hash de datos, commit, dependencias; registrar candidatos sin promoverlos automáticamente.
- **Entregables:** `src/training/tracking.py`, configuración MLflow persistente.
- **Aceptación/prueba:** reiniciar servicio sin perder runs; cada modelo tiene run y linaje; un registro candidato no altera champion.

### T19 — Selección y aprobación inicial del champion
- **Depende de:** T18 y revisión humana.
- **Trabajo:** documentar decisión de modelo inicial y asignar alias/estado aprobado, con versión fija y registro de auditoría.
- **Entregables:** `reports/model_selection.md`, mecanismo de resolución del champion.
- **Aceptación/prueba:** resolución de versión exacta, rechazo si no hay modelo aprobado; sin promoción automática por simple entrenamiento.

**Gate G3:** baseline + 2 candidatos, validación cronológica, tracking trazable y champion aprobado explícitamente.

## 6. Sprint 4 — API y contenerización

### T20 — Esquemas Pydantic y errores
- **Depende de:** T13, D-06.
- **Trabajo:** request con timestamp offset, zonas positivas/catálogo, pasajero opcional; response con minutos, unidad, versión y timestamp UTC.
- **Entregables:** `src/api/schemas.py`.
- **Aceptación/prueba:** payload válido; 422 para valores/timestamps inválidos.

### T21 — Carga segura del champion
- **Depende de:** T19.
- **Trabajo:** resolver y cargar pipeline serializado aprobado al arranque, sin usar artefacto arbitrario del usuario; fallo controlado si falta.
- **Entregables:** `src/api/model_loader.py`.
- **Aceptación/prueba:** modelo correcto y versión expuesta; ausencia del champion da estado no listo, no predicción ficticia.

### T22 — Endpoints FastAPI
- **Depende de:** T20, T21.
- **Trabajo:** `POST /predict`, `GET /health`, `GET /model-info`, logging básico sin secretos.
- **Entregables:** `src/api/main.py`, `tests/api/`.
- **Aceptación/prueba:** 200 válido, 422 inválido, 503 sin modelo, metadatos coherentes, pruebas con TestClient.

### T23 — Dockerfile reproducible
- **Depende de:** T03, T22.
- **Trabajo:** imagen Python con versiones fijadas, usuario no root cuando sea viable, sin datasets ni secretos embebidos.
- **Entregables:** `Dockerfile`, `.dockerignore`.
- **Aceptación/prueba:** `docker build -t nyc-taxi-api:local .` y prueba de arranque local.

### T24 — Docker Compose y volúmenes
- **Depende de:** T18, T23.
- **Trabajo:** servicios `mlflow`, `api`, `pipeline` bajo demanda; persistencia SQLite/artefactos/datos/reportes; bind localhost 5000/8000; healthchecks.
- **Entregables:** `docker-compose.yml`, `.env.example`, instrucciones bootstrap.
- **Aceptación/prueba:** `docker compose config`, `docker compose up -d mlflow`, persistencia tras `down` sin `-v`, arranque de API con champion.

### T25 — Smoke test de serving
- **Depende de:** T24.
- **Trabajo:** levantar entorno, consultar `/health`, `/model-info`, `/predict` y comprobar reinicio.
- **Entregables:** `scripts/smoke_api.py`, `reports/smoke/`.
- **Aceptación/prueba:** HTTP esperado y versión correcta; prueba de 503 sin champion; reinicio no pierde registro.

**Gate G4:** demo local con Docker Compose y predicción real de modelo registrado.

## 7. Sprint 5 — CI/CD y observabilidad

### T26 — CI de pull request
- **Depende de:** T03, T11, T22, T23.
- **Trabajo:** GitHub Actions con Ruff, Pytest, fixtures, smoke API y build Docker; evitar descarga masiva/entrenamiento pesado.
- **Entregables:** `.github/workflows/ci.yml`.
- **Aceptación/prueba:** PR verde en GitHub; introducir fallo de prueba en rama de demostración y observar CI rojo; restaurar.

### T27 — Métricas operativas del servicio
- **Depende de:** T22.
- **Trabajo:** registrar latencia p50/p95, throughput, códigos 4xx/5xx, health; agregar por ventana; no prometer disponibilidad real sin medición.
- **Entregables:** `src/api/metrics.py`, reportes/logs agregados.
- **Aceptación/prueba:** solicitudes sintéticas actualizan contadores y latencias; errores no revelan datos internos.

### T28 — Monitoreo de calidad y schema drift
- **Depende de:** T10, T05.
- **Trabajo:** comparar nuevos lotes con referencia aprobada, cambios de columnas, volumen, nulos y categorías.
- **Entregables:** `src/monitoring/data_quality.py`, reporte por mes.
- **Aceptación/prueba:** fixture con columna incompatible/valores anómalos dispara señal verificable.

### T29 — Data drift con Evidently
- **Depende de:** T13, T28 y versión de Evidently fijada.
- **Trabajo:** comparar distribuciones de features críticas respecto a referencia; generar reporte reproducible; parametrizar umbrales.
- **Entregables:** `src/monitoring/drift.py`, `reports/monitoring/`.
- **Aceptación/prueba:** referencia estable y muestra alterada producen resultados distinguibles; reporte indica ventanas y tamaños.

### T30 — Performance con ground truth posterior
- **Depende de:** T17, T29.
- **Trabajo:** unir predicciones con resultados observados mediante identificador o protocolo de simulación explícito; calcular MAE/RMSE por mes y segmento solo cuando haya etiqueta.
- **Entregables:** `src/monitoring/performance.py`.
- **Aceptación/prueba:** sin etiquetas reporta `NOT_AVAILABLE` y no inventa MAE; con etiquetas calcula métricas correctas.

### T31 — Comando y reporte mensual de monitoreo
- **Depende de:** T27–T30.
- **Trabajo:** `python -m src.monitoring.run --year YYYY --month MM`; persistir reportes versionados y decisión preliminar de alerta.
- **Entregables:** CLI, JSON/HTML según compatibilidad Evidently, tests.
- **Aceptación/prueba:** dos ventanas de simulación producen evidencia, sin modificar champion.

**Gate G5:** CI ejecutado en GitHub, reportes de drift/calidad, desempeño condicionado a etiquetas y métricas de servicio.

## 8. Sprint 6 — Retraining, promoción, rollback y defensa

### T32 — Evaluador de triggers
- **Depende de:** T31, D-05.
- **Trabajo:** implementar condiciones configurables (propuestas 115 % MAE dos ventanas, PSI > 0.20, cambios sostenidos, revisión trimestral), severidad y volumen mínimo.
- **Entregables:** `src/retraining/triggers.py`, `configs/monitoring.yaml`.
- **Aceptación/prueba:** escenarios `NO_ACTION` y `RETRAIN_RECOMMENDED` deterministas; no confundir alerta con promoción.

### T33 — Entrenamiento challenger
- **Depende de:** T18, T32.
- **Trabajo:** entrenar con datos nuevos aprobados y ventanas temporales válidas; registrar nueva versión en MLflow.
- **Entregables:** `src/retraining/train_challenger.py`.
- **Aceptación/prueba:** challenger trazable, champion intacto, sin mezclar periodos futuros en evaluación retrospectiva.

### T34 — Gate champion/challenger
- **Depende de:** T17, T25, T33, D-05.
- **Trabajo:** comparar sobre mismo conjunto temporal de evaluación, segmentos, calidad, smoke tests y criterio mejora ≥2 % o no inferioridad definida.
- **Entregables:** `src/retraining/compare.py`, reporte firmado por ejecución.
- **Aceptación/prueba:** challenger peor rechazado; mejora no basta si falla calidad o segmentos; decisión auditada.

### T35 — Promoción controlada y rollback
- **Depende de:** T21, T34.
- **Trabajo:** promover solo con aprobación explícita, registrar versión previa, actualizar alias/estado de manera controlada, reiniciar/recargar API, revertir si falla.
- **Entregables:** `src/retraining/promote.py`, `src/retraining/rollback.py`, runbook.
- **Aceptación/prueba:** versionado previo recuperable; rollback restituye versión anterior y smoke API verde; no borrar artefactos.

### T36 — Workflow de reentrenamiento bajo demanda
- **Depende de:** T32–T35.
- **Trabajo:** orquestar pasos por CLI/Compose y, si corresponde, GitHub Actions manual; acciones de promoción protegidas por aprobación.
- **Entregables:** `src/retraining/evaluate.py`, `.github/workflows/retraining.yml` (opcional según permisos/recursos).
- **Aceptación/prueba:** ejecución sin trigger no entrena; con trigger registra challenger, pero no lo promueve automáticamente.

### T37 — README, reproducibilidad y revisión cruzada
- **Depende de:** T25, T26, T31, T35.
- **Trabajo:** guía Windows/VS Code, requisitos, bootstrap completo, troubleshooting, limpieza segura, comandos, decisiones, limitaciones, riesgos, rutas de evidencia.
- **Entregables:** `README.md`, `docs/runbook.md`, ADR y matriz de trazabilidad.
- **Aceptación/prueba:** otro integrante clona y ejecuta desde entorno limpio; documenta errores y correcciones.

### T38 — Demo final y evidencias académicas
- **Depende de:** T37.
- **Trabajo:** guion: ingesta → gate inválido → train → MLflow → API → CI → drift → trigger → challenger rechazado/promovido → rollback.
- **Entregables:** `reports/final/`, guion de demostración, resultados reales y limitaciones, material para presentación.
- **Aceptación/prueba:** cada afirmación tiene evidencia (comando/log/run/screenshot); reproducibilidad demostrada y ninguna métrica inventada.

**Gate G6:** ciclo MLOps de extremo a extremo demostrado, decisiones de promoción reversibles y defensa reproducible.

## 9. Comandos de referencia y orden de arranque

> **Importante:** ingesta y validación ya ofrecen CLI; el modo normal de validación rechaza mientras la política real siga pendiente. Los demás son comandos objetivo y solo funcionarán al implementar su tarea y aprobar sus dependencias.

```powershell
# Desde la raíz del repositorio en PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m pytest -q
ruff check .

docker compose config
docker compose build
docker compose up -d mlflow

# Pipeline (una vez implementados los módulos y aprobados los meses)
python -m src.ingestion.download --year 2025 --month 01
python -m src.validation.run --year 2025 --month 01
python -m src.features.build --year 2025 --month 01
python -m src.training.train --config configs/model.yaml

# SOLO después de aprobar y registrar un champion
docker compose up -d api
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/model-info

# Monitoreo y evaluación de trigger
python -m src.monitoring.run --year 2026 --month 01
python -m src.retraining.evaluate --config configs/monitoring.yaml
```

El entrenamiento real requiere todos los meses acordados, no solo enero; el comando de un mes es demostrativo. `docker compose down` conserva volúmenes por defecto; **no usar `down -v`** sin backup y autorización.

## 10. Prompts operativos para Codex (copiar uno a la vez)

### P0 — Auditoría antes de implementar
```text
Lee intent.md, spec.md y plan.md completos. Resume el objetivo, la arquitectura local con Docker Compose, los riesgos de leakage y las decisiones D-01 a D-08 aún abiertas. No escribas código. Propón cómo verificar el Gate G0 y señala contradicciones concretas con archivo y sección.
```

### P1 — Ejecutar una tarea aislada
```text
Trabajaremos únicamente en la tarea T[ID] de plan.md. Primero lee sus dependencias y criterios de aceptación, además de intent.md y spec.md. Antes de editar, enumera archivos a crear/modificar, comandos y pruebas. No cambies contratos ni agregues infraestructura. Implementa solo tras mi confirmación; ejecuta tests y entrega evidencia verificable y riesgos pendientes.
```

### P2 — Revisión de código independiente
```text
Revisa los cambios de la tarea T[ID] contra intent.md, spec.md y plan.md. Busca leakage, inconsistencias temporales, errores de zonas horarias, secretos, falta de idempotencia, ausencia de tests y problemas Windows/Docker. No refactorices fuera del alcance. Devuelve hallazgos priorizados con archivo/línea y propone tests faltantes.
```

### P3 — Cierre de gate
```text
Evalúa el Gate G[N] de plan.md. Para cada condición presenta evidencia concreta: archivo, comando ejecutado, resultado y limitación. No marques PASS sin prueba real. Si falta evidencia, responde BLOCKED con el siguiente paso mínimo. No continúes al sprint siguiente hasta mi aprobación.
```

### P4 — Demo controlada
```text
Prepara un guion reproducible para la demostración de la plataforma local. Usa únicamente funciones ya implementadas y verificadas. Incluye comandos PowerShell, URL de MLflow y API, datos sintéticos para provocar un gate fallido y drift, y una demostración reversible de champion/challenger. No promociones modelos ni borres datos sin autorización explícita.
```

## 11. Matriz compacta de entregables académicos

| Entregable PDF | Evidencia planificada |
|---|---|
| D1 Arquitectura/problema | T01, decisiones y diagrama |
| D2 GitHub | T02, T03, T26, T37 |
| D3 Datos y DQ | T06–T11 |
| D4 Training y MLflow | T12–T19 |
| D5 API Dockerizada | T20–T25 |
| D6 CI/CD | T26, T36 |
| D7 Monitoreo | T27–T31 |
| D8 Retraining y rollback | T32–T36 |
| D9 Presentación final | T37–T38 |

## 12. Checklist de control (estado inicial)

- [ ] G0 Decisiones críticas registradas y aprobadas para descargas masivas y entrenamiento real (el registro documental de T01 no cierra este gate).
- [ ] G1 Arquitectura, entorno y fixtures reproducibles.
- [ ] G2 Ingesta y DQ auditables.
- [ ] G3 Modelado temporal, MLflow y champion.
- [ ] G4 API y Docker Compose operativos.
- [ ] G5 CI y observabilidad verificables.
- [ ] G6 Retraining, rollback y demo reproducible.

**Definición de terminado por tarea:** dependencias satisfechas; código y tests ejecutados; evidencia conservada; README/contratos actualizados cuando aplique; revisión humana; sin secretos ni datos grandes en Git. Una tarea que no se pudo ejecutar queda `NO VERIFICADO`, no completada.

**Aplicación a T01:** al ser exclusivamente documental, no requiere código ni tests de aplicación. Exige lectura cruzada, matriz de trazabilidad, validación de referencias/estados y revisión humana de los entregables. Los componentes de ejecución futura permanecen `NO VERIFICADOS`; T01 no se cierra hasta la revisión del equipo. El criterio general de D-08 sigue pendiente.

**Nota de procedencia:** los seis sprints, entregables D1–D9, tecnologías, política anti-leakage, métricas y gates generales provienen del PDF y de `intent.md`/`spec.md`. Los IDs T01–T38, su granularidad, comandos de validación, fixtures, organización de prompts y gates G0–G6 son propuestas de ejecución de este plan, sujetas a aprobación del equipo.
