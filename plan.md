# PLAN — Implementación incremental NYC Yellow Taxi MLOps

**Versión:** 1.0 · **Estado:** T14–T34 con cierre técnico verificado; G5 PASS técnico; T35–T38 pendientes. PR #1 integrado en main (21a6abf), CI verde; T32–T34 locales, aún sin publicar · **Entorno:** Windows local y Docker Linux amd64; API 8080/MLflow Docker 5001.
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
| D-01 | Periodos | Ciclo original intacto. Nuevo ciclo T33: train 2025 completo, validation conocida ene–mar 2026 y comparación final nueva abr–jun 2026 | APROBADOS y auditados por separado; [contrato T32–T34](docs/t32-t34-retraining.md) |
| D-02 | Recursos | Todos los elegibles. Preparación 4 GiB libres/2 GiB RSS; entrenamiento 8/4; inferencia final 6/2; cuatro hilos, un candidato, dos horas y 50 GiB disco. Docker serving: 2 GiB/2 CPU por API/MLflow y un worker | APROBADOS y verificados; sin entrenamiento Docker en T23–T25 |
| D-03 | Herramientas | Locks Windows 24/95/97 y Linux serving 99 intactos. Actions verificado. Evidently 0.7.23 con pandas 2.3.3 en renderer aislado; predicciones conservan pandas 3.1.1 | APROBADO para T29–T31, compatibilidad y locks separados verificados; [evidencia](docs/t29-t31-monitoring.md) |
| D-04 | Umbrales DQ | D-04 v1 congelada; diez excepciones exactas de 2025 y seis de ene–jun 2026, ligadas a mes/hash/reporte; inválidos excluidos | APROBADA E IMPLEMENTADA; 30 lotes: 14 pasan calidad y 16 aceptados excepcionalmente |
| D-05 | Drift y promoción | T32/T34 aprobados: MAE >115 % o misma feature PSI >0,20, dos meses; gate MAE mejora >=2 %, RMSE/P90 globales sin empeorar y segmentos MAE/P90 <=5 % | APROBADO para este ciclo; solo recomendación/revisión humana, sin promoción. [Contrato](docs/t32-t34-execution-proposal.md) |
| D-06 | API | Contrato REST v1 aprobado el 2026-11-09: offset, origen del catálogo, pasajeros opcionales 0–6, whitelist estricta y errores 422/503/500 | APROBADA; [contrato y pruebas T20–T22](docs/t20-t22-serving.md) |
| D-07 | MLflow | MLflow 3.16.1 en entorno separado; SQLite persistente, artefactos locales, loopback y cuatro versiones; LightGBM v4 champion por T19 | APROBADA, IMPLEMENTADA Y VERIFICADA; registro/reinicio/carga/linaje auditados |
| D-08 | Definition of Done | T14–T34 con cierre técnico, G3/G4/G5 verificados. PR #1 integrado por solicitud humana; T32–T34 aún locales | Revisión humana de resultados independiente; G6/T35–T38 pendientes |

**Gate G0, decisiones:** D-01/D-02/D-04 aprobadas; excepción puntual de marzo aprobada posteriormente. T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [evaluación real auditada](reports/quality/t15_baseline_validation.md). Marzo aceptado por excepción humana solo para su hash/reporte; FAIL original y exclusiones conservados, sin cambiar D-04 global. T14 integral y primera comparación T16/T17 ya auditadas; test evaluado tras selección, replay sin métricas predictivas. Sin registro/promoción. G2/G3 requieren sus condiciones y revisión propias.

**Activación D-04 posterior aprobada:** la propuesta basada en 240.000 filas de 2024 fue aprobada; perfil real probado y enero completo ejecutado. [Política](docs/d04-quality-proposal.md), [activación](docs/d04-activation.md), [piloto](reports/quality/pilot_2024_01.md). Resultado: 2.964.624 raw, 2.961.753 elegibles, 2.871 exclusiones y 60 normalizaciones; WARN, sin entrenamiento. Suite del piloto inicial: 255 pruebas en desarrollo y wheel. Después se aprobaron D-01/D-02 y se amplió autorización académica a los 24 archivos, ratificando/congelando D-04; [protocolo](docs/d01-d02-protocol.md). G2 conserva revisión humana y no implica calidad aprobada de otros lotes.

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
- **Estado T07:** verificación técnica PASS: SHA-256, esquema/volumen, SKIPPED sin red, registro local, divergencias, concurrencia y fallo intermedio probados con fixtures. Estado inicial sin manifiestos; tras aprobar D-04 se registró solo enero 2024, con origen/fecha desconocidos conservados. Revisión humana G2 pendiente.
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
- **Estado T09 actual:** perfil real D-04 provisional implementado, UTC alineado con D-06 y piloto enero 2024 completo aprobado con WARN. Revisión humana G2 pendiente; approved_for_training siempre false. [Evidencia inicial](docs/t08-t09-validation.md) y [activación actual](docs/d04-activation.md).

### T10 — Pipeline raw → validated
- **Depende de:** T07–T09.
- **Trabajo:** CLI `python -m src.validation.run --year YYYY --month MM`; persistir datos validados y reportes por lote con escritura segura.
- **Entregables:** `src/validation/run.py`, `data/validated/` (ignorado en Git), `reports/quality/`.
- **Aceptación/prueba:** ejecución con fixture válida, fallo controlado con fixture inválida, trazabilidad al manifiesto raw.
- **Alcance actual:** CLI verifica integridad/exhaustividad y autorización; persiste reportes y salidas REAL o TEST_ONLY con marcador final, sin reemplazos. Perfil real APPROVED_REAL, data_quality_approved separado de approved_for_training=false.
- **Estado T10 actual:** fixtures y perfil real verificados; enero 2024 publicado VALIDATED_REAL bajo D-04 aprobada. Revisión humana pendiente; no habilita entrenamiento ni otros meses. [Evidencia inicial](docs/t10-t11-data-pipeline.md), [activación](docs/d04-activation.md).

### T11 — Pruebas de integración de datos
- **Depende de:** T10.
- **Trabajo:** simular descarga → manifiesto → validación con fixtures y respuestas HTTP mock.
- **Entregables:** `tests/integration/test_data_pipeline.py`.
- **Aceptación/prueba:** éxito y fallo reproducibles sin Internet, sin datos TLC grandes.
- **Estado T11:** verificación técnica PASS: 33 pruebas de integración nuevas, 162 en suite total; HTTP simulado, gates críticos, exclusiones, integridad, fallos de lectura/publicación, reejecución y CLI. No prueba Internet ni operación con datos reales. Revisión humana pendiente. [Evidencia](docs/t10-t11-data-pipeline.md).

**Gate G2:** ingesta idempotente, calidad auditable y bloqueo de datos no aprobados.

Evidencia offline y piloto real enero 2024 disponibles. D-04 provisional y semántica temporal resueltas; G2 conserva revisión humana. El piloto aprueba calidad de un lote, no de los 24, y no habilita entrenamiento.

## 5. Sprint 3 — Features, modelado, MLflow

### T12 — Target y selección anti-leakage
- **Depende de:** T10, D-06 para aprobar las features de destino.
- **Trabajo aprobado:** derivar target histórico en minutos UTC; whitelist origen/calendario/pasajeros opcionales. Destino deshabilitado; prohibir llegada, importes, pagos, taxímetro y target como predictores. Contexto temporal de etiquetas separado de X.
- **Entregables:** `src/features/target.py`, `src/features/schema.py`.
- **Aceptación/prueba:** test automatizado comprueba columnas permitidas y que ninguna variable post-viaje llega al estimador.
- **Estado T12:** verificación técnica PASS con fixtures; whitelist/causalidad v1 y política temporal aprobadas tras revisar el diccionario TLC. Revisión humana final pendiente. [Evidencia](docs/t12-t13-features.md).

### T13 — Transformaciones reutilizables
- **Depende de:** T12, D-06.
- **Trabajo:** features de hora/día/mes en America/New_York; tratamiento explícito de pasajero opcional; serializar preprocesador junto al estimador.
- **Entregables:** `src/features/build.py`, pipeline sklearn y pruebas de DST/zonas horarias.
- **Aceptación/prueba:** mismo payload produce mismas features en train/serving; timestamps sin offset rechazados según contrato.
- **Estado T13:** verificación técnica PASS: Pipeline serializable, fit de categorías solo sobre entradas train de pruebas, pasajeros ausentes explícitos, DST y CLI sobre lote validado identificado. Sin fit al construir archivos de features. Suite inicial de 227 pruebas (65 nuevas). Tras D-04, lector REAL probado con fixtures; enero validado sin extraer features ni entrenar; suite actual 255. [Evidencia](docs/t12-t13-features.md).

### T14 — Particiones temporales y lectura completa por bloques
- **Depende de:** T10, T13, D-01/D-02.
- **Trabajo aprobado en D-01/D-02:** cortes cronológicos 2024/train, ene–mar 2025/val, abr–jun/test y jul–dic/replay; todos los elegibles sin submuestreo, por bloques y con linaje. Implementación y ejecución real de las cuatro particiones completadas y auditadas; [evidencia](reports/quality/t14_completion.md).
- **Entregables:** `src/training/split.py`, `configs/model.yaml`.
- **Aceptación/prueba:** `max(train.time) < min(val.time)` y `max(val.time) < min(test.time)`; sin solapamiento, cobertura completa de elegibles y exclusiones causales auditadas; repetición reproduce hashes/conteos/orden. No se concatena el histórico completo en una matriz densa.
- **Aceptación temporal adicional:** verificar etiquetas disponibles al corte; probar viajes que empiezan antes y terminan después del corte, excluyéndolos del entrenamiento simulado en ese instante. Documentar replay retrospectivo frente a disponibilidad real de publicación de lotes, conforme a la política aprobada D-01/D-06; no inferir disponibilidad por el solo mes del archivo.

- **Estado T14:** T14 CIERRE TÉCNICO PASS: 24 meses registrados, validados/aceptados y con features; 89.892.322 raw, 627.221 exclusiones de calidad y 2.952 por disponibilidad de etiqueta. Particiones auditadas: train 41.119.495; validation 11.163.264; test 12.712.466; replay 24.266.924. Todas las identidades y valores publicados coinciden con las fuentes; train/validation coinciden con T15 congelada. D-04, 24 raw y diez FAIL originales intactos. Revisión humana de resultados independiente del cierre técnico. T16/T17 completadas y auditadas después de T14; ver sus resultados a continuación. [Evidencia integral](reports/quality/t14_completion.md). Split `e02156de2ac5477bafc4657774e31673`; 391 pruebas en ambos entornos. [Autorizaciones exactas](docs/t14-quality-exceptions-proposal.md) y [protocolo T16/T17 aprobado](docs/t16-t17-execution-proposal.md).

### T15 — Baseline
- **Depende de:** lector temporal de T14 y datos aprobados train/validation. La continuación autorizada separa ajuste/evaluación de la preparación integral de test/replay; no cierra T14.
- **Trabajo aprobado:** mediana global exacta solo de train 2024; evaluación de enero–marzo 2025, reutilizando el ajuste congelado y la excepción puntual autorizada.
- **Entregables:** `src/training/baseline.py` y artefacto de resultados.
- **Aceptación/prueba:** predicciones finitas y positivas; baseline reproducible; no utilizar test para elegir modelos.

- **Estado T15 actual:** CIERRE TÉCNICO PASS; mediana 12,983333 min sobre 41.119.495 etiquetas train y 11.163.264 predicciones validation, MAE 7,741890/RMSE 11,912962 min. [Evidencia congelada](reports/quality/t15_baseline_validation.md). T14 integral terminó después y confirmó sus hashes/conteos sin reajustar el baseline. Revisión humana independiente; T16 añadió candidatos y T17 los evaluó, sin alterar este baseline ni promoverlos.

### T16 — Dos modelos candidatos

Extensión adicional aprobada y completada: **LightGBM**, ajuste sobre todo train y evaluación solo en validation; [evidencia](reports/evaluation/lightgbm_validation.md). La evaluación final independiente posterior también terminó y está [auditada](reports/evaluation/lightgbm_final_evaluation.md).

- **Depende de:** T14, T15.
- **Trabajo aprobado en D-02:** SGDRegressor Huber y MLP16 con partial_fit sobre todos los bloques train, una pasada y semilla 42; preprocesador train-only congelado y Pipeline serializable. Perfil revisado aprobado: cuatro hilos, un candidato, 4 GiB RSS, dos horas y preflight 8 GiB RAM/50 GiB disco libres. [Protocolo](docs/t16-t17-execution-proposal.md) y [revisión de recursos](docs/d02-t16-resource-review.md). Exceder detiene sin reducir datos.
- **Entregables:** `src/training/train.py`, configuraciones de hiperparámetros.
- **Protocolo concreto aprobado el 2026-11-05:** [perfil T16](docs/t16-t17-execution-proposal.md), condicionado al cierre auditado de T14: preprocesador train-only con escalado, SGD Huber y MLP16, una pasada completa por candidato, bloques de 4.096, semilla 42 y salida acotada con recortes registrados. La revisión posterior D-02 8/4 fue aprobada y aplicada. Entrenamiento completo y auditado.
- **Aceptación/prueba:** fixtures verifican aprendizaje por bloques, coherencia train/serving y límites de RAM/tiempo/disco. La ejecución real auditada usó todos los elegibles y registró pasadas, cobertura y recursos. La extensión LightGBM verificó además la supervisión y cancelación del proceso nativo real.

### T17 — Evaluación temporal y segmentos
- **Depende de:** T15, T16.
- **Trabajo:** MAE, RMSE, MedAE, P90 error absoluto; análisis por mes/franja/rutas frecuentes; elegir con validación y reservar test para reporte final.
- **Entregables:** `src/evaluation/metrics.py`, `reports/evaluation/`.
- **Protocolo concreto aprobado el 2026-11-05:** [evaluación T17](docs/t16-t17-execution-proposal.md), después de T14/T16: métricas exactas, franjas de seis horas y top 20 rutas con soporte mínimo 1.000 definido solo por frecuencia en validation. Destino solo como segmento; selección congelada antes de test, sin reajuste ni promoción. Ejecución completa y auditada.
- **Aceptación/prueba:** tests de métricas con valores conocidos; no ajustar hiperparámetros tras mirar test.

- **Extensión final T17:** CIERRE TÉCNICO PASS; 10.937.087 viajes de enero–marzo 2026, 474 pruebas por entorno y auditoría completa. [Resultados y reinicio autorizado](reports/evaluation/lightgbm_final_evaluation.md). Sin promoción; revisión humana independiente.

### T18 — MLflow tracking y Registry
- **Depende de:** T16, T17, D-07.
- **Estado T18:** CIERRE TÉCNICO PASS; D-07 aprobada/implementada. Cuatro candidatos reales registrados sin alias; carga, métricas/linaje y persistencia tras reiniciar auditadas. 488 pruebas nativas y una omisión explícita, 489 sobre wheel MLflow. [Evidencia](reports/tracking/t18_completion.md), [guía](docs/t18-mlflow.md). Revisión humana independiente; sin promoción ni T19 implementada.
- **Precondición por resolver en D-07:** acordar y probar el entorno local acotado de MLflow antes de esta tarea; Compose completo sigue en T24. No asumir infraestructura disponible por su aparición en el diagrama.
- **Trabajo:** registrar parámetros, métricas, artefactos, hash de datos, commit, dependencias; registrar candidatos sin promoverlos automáticamente.
- **Entregables:** `src/training/tracking.py`, configuración MLflow persistente.
- **Aceptación/prueba:** reiniciar servicio sin perder runs; cada modelo tiene run y linaje; un registro candidato no altera champion.

### T19 — Selección y aprobación inicial del champion
- **Estado T19:** CIERRE TÉCNICO PASS; elección humana LightGBM v4 aplicada y auditada. Alias, recibo, paquete y resolución exacta verificados; 501 pruebas nativas más dos omisiones explícitas, 503 sobre wheel MLflow. [Evidencia](reports/model_selection.md). Sin reajustes ni promoción automática futura.
- **Depende de:** T18 y revisión humana.
- **Trabajo:** documentar decisión de modelo inicial y asignar alias/estado aprobado, con versión fija y registro de auditoría.
- **Entregables:** `reports/model_selection.md`, mecanismo de resolución del champion.
- **Aceptación/prueba:** resolución de versión exacta, rechazo si no hay modelo aprobado; sin promoción automática por simple entrenamiento.

**Gate G3: PASS para Sprint 3.** Baseline/candidatos, validación cronológica, tracking trazable y champion LightGBM v4 aprobado explícitamente/aplicado/auditado en T19. No acredita API, Docker ni gates posteriores. [Evidencia](reports/model_selection.md).

## 6. Sprint 4 — API y contenerización

### T20 — Esquemas Pydantic y errores
- **Depende de:** T13, D-06.
- **Trabajo:** request con timestamp offset, zonas positivas/catálogo, pasajero opcional; response con minutos, unidad, versión y timestamp UTC.
- **Entregables:** `src/api/schemas.py`.
- **Aceptación/prueba:** payload válido; 422 para valores/timestamps inválidos.
- **Estado T20: CIERRE TÉCNICO PASS.** Contrato D-06 y HTTPX aprobados expresamente; [contrato y verificación](docs/t20-t22-serving.md). Límites, campos prohibidos, catálogo y timestamps probados con 422.

### T21 — Carga segura del champion
- **Depende de:** T19.
- **Trabajo:** resolver y cargar pipeline serializado aprobado al arranque, sin usar artefacto arbitrario del usuario; fallo controlado si falta.
- **Entregables:** `src/api/model_loader.py`.
- **Aceptación/prueba:** modelo correcto y versión expuesta; ausencia del champion da estado no listo, no predicción ficticia.
- **Estado T21: CIERRE TÉCNICO PASS.** Carga real de LightGBM v4, 50 archivos verificados antes de deserializar y seis smoke exactos; [T20–T22](docs/t20-t22-serving.md). Sin promoción ni recarga automática.

### T22 — Endpoints FastAPI
- **Depende de:** T20, T21.
- **Trabajo:** `POST /predict`, `GET /health`, `GET /model-info`, logging básico sin secretos.
- **Entregables:** `src/api/main.py`, `tests/api/`.
- **Aceptación/prueba:** 200 válido, 422 inválido, 503 sin modelo, metadatos coherentes, pruebas con TestClient.
- **Estado T22: CIERRE TÉCNICO PASS.** 50 pruebas específicas y auditoría REST con champion real; suite serving de 553 casos verificados (un reinicio requirió reintento fuera del sandbox), 501 nativos y 51 sobre wheel fuera de src. [Evidencia y límites](docs/t20-t22-serving.md). Revisión humana independiente; Docker/G4 pendientes.

### T23 — Dockerfile reproducible
- **Depende de:** T03, T22.
- **Trabajo:** imagen Python con versiones fijadas, usuario no root cuando sea viable, sin datasets ni secretos embebidos.
- **Entregables:** `Dockerfile`, `.dockerignore`.
- **Aceptación/prueba:** `docker build -t nyc-taxi-api:local .` y prueba de arranque local.
- **Estado T23: CIERRE TÉCNICO PASS.** Build real Python 3.14.7 amd64 fijado por digest, lock Linux y paquetes Debian con hashes; imports/predicción Linux verificados. Usuario 10001 y contexto por whitelist. [Perfil aprobado](docs/t23-t25-execution-proposal.md), [pruebas](docs/t23-t25-docker.md).

### T24 — Docker Compose y volúmenes
- **Depende de:** T18, T23.
- **Trabajo:** servicios `mlflow`, `api`, `pipeline` bajo demanda; persistencia SQLite/artefactos/datos/reportes; bind localhost 5000/8000; healthchecks.
- **Entregables:** `docker-compose.yml`, `.env.example`, instrucciones bootstrap.
- **Aceptación/prueba:** `docker compose config`, `docker compose up -d mlflow`, persistencia tras `down` sin `-v`, arranque de API con champion.
- **Estado T24: CIERRE TÉCNICO PASS.** Configuración, servicios saludables y volumen Linux persistente tras down/up; bootstrap repetido SKIPPED. Copia aislada conserva cuatro runs/versiones y champion v4; original intacto. Perfil aprobado: API 8080 y MLflow 5001. [Evidencia y comandos](docs/t23-t25-docker.md).

### T25 — Smoke test de serving
- **Depende de:** T24.
- **Trabajo:** levantar entorno, consultar `/health`, `/model-info`, `/predict` y comprobar reinicio.
- **Entregables:** `scripts/smoke_api.py`, `reports/smoke/`.
- **Aceptación/prueba:** HTTP esperado y versión correcta; prueba de 503 sin champion; reinicio no pierde registro.
- **Estado T25: CIERRE TÉCNICO PASS.** Smoke nativo y Compose, 200/422/503, diez predicciones Docker exactas, reinicio y auditoría de persistencia PASS. Corrección portable SQLite conserva valores exactos y evidencia legacy; actualización de metadatos aprobada. [Evidencia y límites](docs/t23-t25-docker.md). Revisión humana independiente.

**Gate G4: PASS técnico.** Demo local con Docker Compose y predicción real del champion LightGBM v4, persistencia y 503 aislado verificadas. Revisión humana independiente; no acredita T26–T38.

## 7. Sprint 5 — CI/CD y observabilidad

### T26 — CI de pull request
- **Depende de:** T03, T11, T22, T23.
- **Trabajo:** GitHub Actions con Ruff, Pytest, fixtures, smoke API y build Docker; evitar descarga masiva/entrenamiento pesado.
- **Entregables:** `.github/workflows/ci.yml`.
- **Aceptación/prueba:** PR verde en GitHub; introducir fallo de prueba en rama de demostración y observar CI rojo; restaurar.
- **Estado:** PASS técnico. Perfil CI aprobado (2 CPU/4 GiB, 10 GiB disco, 20 minutos); 601 pruebas, Ruff, dependencias, smoke HTTP e imagen de producción, local y GitHub. PR #1 verde y demostración roja/verde separada verificadas; sin merge. [Evidencia remota](reports/monitoring/t26_github_ci.md).

### T27 — Métricas operativas del servicio
- **Depende de:** T22.
- **Trabajo:** registrar latencia p50/p95, throughput, códigos 4xx/5xx, health; agregar por ventana; no prometer disponibilidad real sin medición.
- **Entregables:** `src/api/metrics.py`, reportes/logs agregados.
- **Aceptación/prueba:** solicitudes sintéticas actualizan contadores y latencias; errores no revelan datos internos.
- **Estado:** PASS técnico con solicitudes reales Docker 200/422/503; ventanas de 60 s, percentiles exactos hasta 10.000 solicitudes y exportación sin endpoint adicional. [Evidencia y límites](docs/t26-t28.md).

### T28 — Monitoreo de calidad y schema drift
- **Depende de:** T10, T05.
- **Trabajo:** comparar nuevos lotes con referencia aprobada, cambios de columnas, volumen, nulos y categorías.
- **Entregables:** `src/monitoring/data_quality.py`, reporte por mes.
- **Aceptación/prueba:** fixture con columna incompatible/valores anómalos dispara señal verificable.
- **Estado:** PASS técnico; referencia aprobada con doce reportes completos 2024, replay julio–diciembre 2025 por mismo mes. Cambios descriptivos y FAIL/excepciones conservados, sin umbrales nuevos. [Reporte](reports/monitoring/t28_quality_replay.md).

### T29 — Data drift con Evidently
- **Depende de:** T13, T28 y versión de Evidently fijada.
- **Trabajo:** comparar distribuciones de features críticas respecto a referencia; generar reporte reproducible; parametrizar umbrales.
- **Entregables:** `src/monitoring/drift.py`, `reports/monitoring/`.
- **Aceptación/prueba:** referencia estable y muestra alterada producen resultados distinguibles; reporte indica ventanas y tamaños.
- **Estado:** PASS técnico. Referencia de las 41.119.495 filas train y seis meses replay completos; bins agregados, PSI y Evidently JSON/HTML verificados. Renderer aislado por incompatibilidad pandas, aprobado y probado. [Resultados](reports/monitoring/t29-t31_monthly_replay.md).

### T30 — Performance con ground truth posterior
- **Depende de:** T17, T29.
- **Trabajo:** unir predicciones con resultados observados mediante identificador o protocolo de simulación explícito; calcular MAE/RMSE por mes y segmento solo cuando haya etiqueta.
- **Entregables:** `src/monitoring/performance.py`.
- **Aceptación/prueba:** sin etiquetas reporta `NOT_AVAILABLE` y no inventa MAE; con etiquetas calcula métricas correctas.
- **Estado:** PASS técnico. 24.266.924 predicciones/etiquetas maduras, identidad por split/feature/fila, métricas exactas y segmentos T17. Auditoría recalculó todas las predicciones y validó cuantiles por CDF; modelo/runtime congelados, sin test/holdout nuevos ni reajuste.

### T31 — Comando y reporte mensual de monitoreo
- **Depende de:** T27–T30.
- **Trabajo:** `python -m src.monitoring.run --year YYYY --month MM`; persistir reportes versionados y decisión preliminar de alerta.
- **Entregables:** CLI, JSON/HTML según compatibilidad Evidently, tests.
- **Aceptación/prueba:** dos ventanas de simulación producen evidencia, sin modificar champion.
- **Estado:** PASS técnico. CLI, seis reportes reales versionados, dos ventanas sintéticas y ausencia de etiquetas probados. CI verde: 625 pruebas principales y 17 del renderer separado; FAIL/excepciones conservados. Servicio histórico 2025 NOT_AVAILABLE; T27 aporta métricas actuales. [Guía](docs/t29-t31-monitoring.md).

**Gate G5:** CI ejecutado en GitHub, reportes de drift/calidad, desempeño condicionado a etiquetas y métricas de servicio.

**G5 PASS técnico — 2026-11-09.** Evidencia en [T29–T31](reports/monitoring/t29-t31_monthly_replay.md) y T27/T28. Revisión humana/merge independientes; no se inicia T32 ni se aprueban triggers o promociones.

## 8. Sprint 6 — Retraining, promoción, rollback y defensa

### T32 — Evaluador de triggers
- **Depende de:** T31, D-05.
- **Trabajo:** implementar condiciones configurables (propuestas 115 % MAE dos ventanas, PSI > 0.20, cambios sostenidos, revisión trimestral), severidad y volumen mínimo.
- **Entregables:** `src/retraining/triggers.py`, `configs/monitoring.yaml`.
- **Aceptación/prueba:** escenarios `NO_ACTION` y `RETRAIN_RECOMMENDED` deterministas; no confundir alerta con promoción.
- **Estado:** PASS técnico. Reglas aprobadas, 100 pruebas focalizadas y ejecución real sobre seis reportes congelados: RETRAIN_RECOMMENDED por PSI de ausencia de pasajeros julio/agosto y deterioro MAE en parejas septiembre–diciembre. Sin entrenamiento desde el evaluador. [Evidencia](reports/retraining/t32_trigger.md).

### T33 — Entrenamiento challenger
- **Depende de:** T18, T32.
- **Trabajo:** entrenar con datos nuevos aprobados y ventanas temporales válidas; registrar nueva versión en MLflow.
- **Entregables:** `src/retraining/train_challenger.py`.
- **Aceptación/prueba:** challenger trazable, champion intacto, sin mezclar periodos futuros en evaluación retrospectiva.
- **Estado:** PASS técnico. LightGBM desde cero, 100 árboles y 48.144.298 filas train 2025; validation conocida de 10.937.087 filas. Auditorías exhaustivas, fit/serialización y registro v5 sin alias completos. Primer fit cancelado conservado; escritura por bloques permitió respetar 4 GiB combinados sin cambiar datos/parámetros. Champion v4 intacto. [Resultados T33](reports/retraining/t33_challenger.md).

### T34 — Gate champion/challenger
- **Depende de:** T17, T25, T33, D-05.
- **Trabajo:** comparar sobre mismo conjunto temporal de evaluación, segmentos, calidad, smoke tests y criterio mejora ≥2 % o no inferioridad definida.
- **Entregables:** `src/retraining/compare.py`, reporte firmado por ejecución.
- **Aceptación/prueba:** challenger peor rechazado; mejora no basta si falla calidad o segmentos; decisión auditada.
- **Estado:** PASS técnico. Abril–junio 2026, 11.603.243 filas y métricas de ambos modelos auditadas completas. Gate CHALLENGER_REJECTED: MAE mejora 0,737317 %, menor al 2 % exigido; demás controles y 27 segmentos cumplen. Resultado y métricas registrados en el run v5; champion=4 conservado. [Resultados T34](reports/retraining/t34_comparison.md). Las tres excepciones aprobadas excluyen 155.207 inválidos, más 874 por corte temporal, conservando FAIL y D-04.

### T35 — Promoción controlada y rollback
- **Depende de:** T21, T34.
- **Trabajo:** promover solo con aprobación explícita, registrar versión previa, actualizar alias/estado de manera controlada, reiniciar/recargar API, revertir si falla.
- **Entregables:** `src/retraining/promote.py`, `src/retraining/rollback.py`, runbook.
- **Aceptación/prueba:** versionado previo recuperable; rollback restituye versión anterior y smoke API verde; no borrar artefactos.
- **Estado:** PASS técnico TEST_ONLY. MLflow/FastAPI aislados, promoción, rollback desde otro proceso y recuperación ante caída HTTP verificados. Diario encadenado, bytes previos, bloqueo local e identidad de procesos. V4 real intacto; v5 bloqueado. [Cierre](reports/final/completion.md).

### T36 — Workflow de reentrenamiento bajo demanda
- **Depende de:** T32–T35.
- **Trabajo:** orquestar pasos por CLI/Compose y, si corresponde, GitHub Actions manual; acciones de promoción protegidas por aprobación.
- **Entregables:** `src/retraining/evaluate.py`, `.github/workflows/retraining.yml` (opcional según permisos/recursos).
- **Aceptación/prueba:** ejecución sin trigger no entrena; con trigger registra challenger, pero no lo promueve automáticamente.
- **Estado:** PASS técnico. CLI manual plan/resume, motor con autorización acotada y grafo sin promoción. Flujo completo con 48 filas sintéticas registra candidato sin alias; campaña real T32–T34 verificada/reutilizada sin fits/evaluaciones nuevas. Sin workflow remoto adicional. [Runbook](docs/runbook.md).

### T37 — README, reproducibilidad y revisión cruzada
- **Depende de:** T25, T26, T31, T35.
- **Trabajo:** guía Windows/VS Code, requisitos, bootstrap completo, troubleshooting, limpieza segura, comandos, decisiones, limitaciones, riesgos, rutas de evidencia.
- **Entregables:** `README.md`, `docs/runbook.md`, ADR y matriz de trazabilidad.
- **Aceptación/prueba:** otro integrante clona y ejecuta desde entorno limpio; documenta errores y correcciones.
- **Estado:** PASS técnico aprobado por separado. Export de 306 archivos, venv limpio y wheels exactos de caché; 681 pruebas PASS/una omisión, Ruff/formato/pip check PASS. Timeout inicial y repetición trazados, sin cambiar código/presupuesto. Clon/ejecución por otro integrante NO VERIFICADOS. [Trazabilidad](reports/final/traceability.md).

### T38 — Demo final y evidencias académicas
- **Depende de:** T37.
- **Trabajo:** guion: ingesta → gate inválido → train → MLflow → API → CI → drift → trigger → challenger rechazado/promovido → rollback.
- **Entregables:** `reports/final/`, guion de demostración, resultados reales y limitaciones, material para presentación.
- **Aceptación/prueba:** cada afirmación tiene evidencia (comando/log/run/screenshot); reproducibilidad demostrada y ninguna métrica inventada.
- **Estado:** PASS técnico. Guion, presentación Markdown y evidencias cruzadas verificados, sin nuevos fits reales ni consumo del holdout. Evidencia científica real separada de demos TEST_ONLY; defensa oral NO VERIFICADA. [Material](reports/final/presentation.md), [guion](reports/final/demo-script.md).

**Gate G6:** ciclo MLOps de extremo a extremo demostrado, decisiones de promoción reversibles y defensa reproducible.

La aprobación T35–T38 separa cierre técnico de revisión humana y defensa oral,
que no se darán por realizadas. [Evaluación por condición](reports/final/completion.md).

## 9. Comandos de referencia y orden de arranque

> **Importante:** T14 integral tiene cierre técnico auditado sobre los 24 meses. T15 permanece congelada y coincide con train/validation publicados. Las diez aceptaciones excepcionales no alteran D-04 ni conservan filas inválidas; cualquier incumplimiento nuevo requiere aprobación. La primera comparación T16/T17 ya terminó con auditoría; LightGBM es una extensión aprobada pendiente, solo con validation. [Evidencia T14](reports/quality/t14_completion.md).

```powershell
# Desde la raíz del repositorio en PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --require-hashes --only-binary=:all: -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m pytest -q
ruff check .

docker compose config
docker compose build
docker compose up -d mlflow

# Pipeline (una vez implementados los módulos y aprobados los meses)
python -m src.ingestion.download --year 2025 --month 01
python -m src.validation.run --year 2025 --month 01
python -m src.features.build --help
python -m src.training.train --help
python -m src.evaluation.run --help

# SOLO después de aprobar y registrar un champion
docker compose up -d api
Invoke-RestMethod http://127.0.0.1:8080/health
Invoke-RestMethod http://127.0.0.1:8080/model-info

# Monitoreo y evaluación de trigger
python -m src.monitoring.run --year 2025 --month 07
python -m src.retraining.evaluate --help
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

- [x] G0 Decisiones D-01/D-02/D-04 registradas y aprobadas para el protocolo local existente, sin descargas masivas. No acredita controles implementados ni autoriza entrenamiento/T14 por sí solo; G2/G3 siguen independientes.
- [ ] G1 Arquitectura, entorno y fixtures reproducibles.
- [ ] G2 Ingesta y DQ auditables.
- [x] G3 Modelado temporal, MLflow y champion inicial aprobado/aplicado/auditado; alcance Sprint 3, no API/Docker.
- [x] G4 API y Docker Compose operativos; smoke real, persistencia y champion v4 verificados técnicamente.
- [x] G5 CI y observabilidad verificables; cierre técnico con replay completo y renderer aislado, revisión humana independiente.
- [x] G6 Cierre técnico: retraining real, operación reversible TEST_ONLY y reproducción offline auditados; revisión cruzada humana/defensa NO VERIFICADAS por separación aprobada. [Evidencia](reports/final/completion.md).

**Definición de terminado por tarea:** dependencias satisfechas; código y tests ejecutados; evidencia conservada; README/contratos actualizados cuando aplique; revisión humana; sin secretos ni datos grandes en Git. Una tarea que no se pudo ejecutar queda `NO VERIFICADO`, no completada.

**Aplicación a T01:** al ser exclusivamente documental, no requiere código ni tests de aplicación. Exige lectura cruzada, matriz de trazabilidad, validación de referencias/estados y revisión humana de los entregables. Los componentes de ejecución futura permanecen `NO VERIFICADOS`; T01 no se cierra hasta la revisión del equipo. El criterio general de D-08 sigue pendiente.

**Nota de procedencia:** los seis sprints, entregables D1–D9, tecnologías, política anti-leakage, métricas y gates generales provienen del PDF y de `intent.md`/`spec.md`. Los IDs T01–T38, su granularidad, comandos de validación, fixtures, organización de prompts y gates G0–G6 son propuestas de ejecución de este plan, sujetas a aprobación del equipo.

## Actualización de resultados T16/T17 — 2026-11-05

SGD Huber y MLP16 se ajustaron con las 41.119.495 filas train, una pasada por candidato. SGD fue elegido con validation antes de abrir test: MAE 6,876910 frente a 7,741890 del baseline. En test obtuvo MAE 7,965068 frente a 9,032999. MLP fue peor que el baseline; SGD empeoró ligeramente P90 en validation. Sin reajustes después de test ni promoción.

**T16: CIERRE TÉCNICO PASS.** Ambos candidatos cubren todo train, sin submuestreo, vocabulario/escalado train-only y Pipeline serializable. [Informe y recursos reales](reports/quality/t16_training.md).

**T17: CIERRE TÉCNICO PASS de la primera comparación.** 11.163.264 filas validation, 12.712.466 test; métricas y 28 segmentos más el global por ventana/modelo auditados independientemente. [Resultados completos](reports/evaluation/t17_model_comparison.md). 423 pruebas por entorno; [evidencia](docs/t16-t17-validation.md).

**Extensión T16/T17 aprobada:** [LightGBM](docs/t16-lightgbm-extension-proposal.md), todos los elegibles de train, 100 árboles y perfil 8/4. Evaluación únicamente con validation; nueva evaluación final independiente pendiente. No sustituye la selección ni el test originales. Estado de ejecución: CIERRE TÉCNICO PASS para ajuste y validation; nueva evaluación final independiente pendiente.

Revisión humana de resultados independiente. G3 sigue abierto por T18/T19: falta tracking, registry y aprobación de champion. No se inician esos trabajos en esta continuación.

## Extensión LightGBM — Resultado auditado

LightGBM 4.7.0 fue entrenado con las 41.119.495 filas train y 100 árboles. En las 11.163.264 filas validation: MAE 6.496404, RMSE 9.847425, MedAE 4.631360 y P90 13.478764 minutos. Ajuste y evaluación auditados; 447 pruebas por entorno. Solo validation: una nueva evaluación final independiente sigue pendiente. La selección SGD y el test de la primera comparación permanecen intactos; no hay promoción.

[Informe y segmentos](reports/evaluation/lightgbm_validation.md). Configuración aprobada separada en [lightgbm.yaml](configs/lightgbm.yaml); no modifica candidates.yaml, los modelos previos ni sus hashes. Los límites 8/4/cuatro hilos/dos horas se respetaron. G3 continúa pendiente de T18/T19 y revisión humana.


**Evaluación final independiente completada y auditada — 2026-11-05:**
enero–marzo de 2026, 10.937.087 viajes; MAE LightGBM **7,742891 min**, SGD
**8,352735** y baseline **9,141254**. Se excluyeron 139.305 filas DQ mediante
tres excepciones humanas exactas y 814 por corte de etiqueta; los 27 raw,
modelos y selección de 2025 permanecen intactos. Reinicio de recursos aprobado
6 GiB libres/2 GiB RSS solo para inferencia final; entrenamiento 8/4 y preparación
4/2 sin cambios. 474 pruebas por entorno y auditoría completa. Sin promoción.
[Evidencia final](reports/evaluation/lightgbm_final_evaluation.md). Las menciones
previas a evaluación pendiente son históricas. Se solicita continuar T18; la
[propuesta D-07](docs/d07-mlflow-proposal.md) requiere aprobación antes de instalar.


**T18 verificada — 2026-11-05:** D-07 aprobada e implementada con MLflow 3.16.1
en entorno separado, SQLite y artefactos persistentes. Cuatro candidatos:
baseline v1, SGD v2, MLP v3 y LightGBM v4, sin alias. Reinicio real, carga,
idempotencia y auditoría independiente PASS; 488 pruebas nativas más una omisión
explícita y 489 sobre wheel MLflow. Los modelos y evaluaciones anteriores no
cambian. Champion/T19 y G3 permanecen pendientes de aprobación.
[Evidencia completa T18](reports/tracking/t18_completion.md). Las menciones
previas a ausencia de tracking describen sus entregas históricas.


**T19 verificada — 2026-11-05:** el usuario aprobó LightGBM v4 como champion
inicial, después de conocer las limitaciones por rutas, y descartó optimización
de hiperparámetros. Alias `champion` aplicado a la versión fija 4, run
`be28c76c84c44efa8914c5950a2959bf`; paquete, aprobación y resolución auditados.
501 pruebas nativas PASS y dos omisiones explícitas; 503 PASS sobre wheel MLflow.
G3 cumple sus condiciones de Sprint 3. D-05 conserva pendientes sus reglas
automáticas de drift y promociones futuras; no se aprueban nuevos umbrales.
[Evidencia completa T19](reports/model_selection.md). T20 y tareas siguientes
no se implementaron en esta continuación. Las entregas anteriores conservan
sus estados históricos; T19 no reescribe métricas, pesos ni selección T17.
