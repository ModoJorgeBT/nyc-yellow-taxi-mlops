# T01 — Requisitos, decisiones y riesgos

Fecha inicial: 2026-11-03; actualización: 2026-11-05, America/Costa_Rica. **T14/T15, T16/T17, evaluación independiente y T18/T19 tienen cierre técnico auditado.** D-04 global, exclusiones y modelos conservados. [T14](../reports/quality/t14_completion.md), [evaluación 2026](../reports/evaluation/lightgbm_final_evaluation.md) y [tracking persistente](../reports/tracking/t18_completion.md). El usuario aprobó LightGBM v4 como champion inicial; alias, paquete y resolución verificados. [Decisión T19](../reports/model_selection.md). G3 cumple el alcance de Sprint 3; reglas automáticas de D-05, API y despliegue pendientes. Las secciones siguientes conservan la cronología.

## 1. Fuentes y evidencia de aprobación

- [Intent](../intent.md), leído completo: objetivo, restricciones y éxito.
- [Spec](../spec.md), leído completo: contratos propuestos y aceptación.
- [Plan](../plan.md), leído completo: T01, dependencias y gates.
- [PDF académico](../Proyecto_Maestria_MLOps_NYC_Taxi_Estructura.pdf), versión 1.0, septiembre de 2026: texto de las 14 páginas leído y contrastado. Se conserva en la raíz, sin modificarlo.
- SHA-256 del PDF: `A86673B4BC2C26155A43DBC2729382E0368C8C96F60FF21B429F929C80C8EBAE`.

El equipo solicitó Python, MLflow, FastAPI y Docker Compose en local y aprobó crear los tres entregables de T01 y sus correcciones documentales. En su respuesta mantuvo pendientes las herramientas adicionales y la hipótesis de destino conocido. Esta aprobación no es la revisión final de los entregables ni acredita aprobación docente de todas las herramientas.

En la segunda revisión el equipo aprobó las siete correcciones propuestas y la inicialización de Git local con rama `main`, sin commits ni publicación. También indicó que ya posee Parquet y que aún no existe repositorio. La preparación T02 queda autorizada para presentar ambos resultados; el cierre humano final no se presupone. Los archivos locales no cambian las decisiones sobre periodos, calidad o recursos.

Posteriormente el usuario aprobó explícitamente el cierre de T01/T02 y solicitó T03 y revisar/organizar los archivos locales. Aprobó usar Python 3.14.7 con `.venv`, setuptools/Ruff/Pytest/pip-tools fijados y lock con hashes; también PyArrow y lectura de metadatos sin cargar todos los meses. Esa aprobación no extiende D-03 a las herramientas aún pendientes ni asigna datos a particiones.

Después solicitó T04/T05 y aprobó la muestra posicional de 2024: primeras 2.048 filas de cada row group de doce meses, dejando 2025 sin perfilado de filas y los umbrales/periodos definitivos pendientes. Se mantuvieron datos sintéticos para pruebas controladas offline conforme al alcance, sin nuevas dependencias ni cambio de target.

Después solicitó T06/T07 y aprobó la política consultada: comando normal bloquea archivos sin manifiesto; `--register-local` registra únicamente por acción explícita, dejando fuente/fecha de descarga no verificadas y sin cambiar los bytes. Se implementa y prueba con fixtures sin incorporar todavía los 24 archivos reales.

Después solicitó T08/T09 y aprobó tres consultas: (1) cuatro esenciales pickup/dropoff/zonas, otros campos opcionales con control de tipo, enteros 32/64, string/large_string, timestamps sin zona en microsegundos, Airport_fee sin renombrar, cbd_congestion_fee conocido opcional y adicionales WARN; (2) motor probado con límites exclusivamente sintéticos, configuración real PENDIENTE y lotes reales bloqueados; (3) catálogo versionado explícito, repeticiones medidas sin eliminación automática y pasajeros medidos por separado. No se resuelven D-04/D-06 ni se aprueban predictores por esta validación. [Evidencia T08/T09](t08-t09-validation.md).

Posteriormente solicitó continuar con T10/T11. Se implementan el CLI y la integración offline conservando el bloqueo aprobado: manifiestos/hash, exhaustividad y escritura de filas elegibles probados solo con fixtures y salidas TEST_ONLY aisladas. No se registran los 24 archivos, no se fijan umbrales reales ni se concede aprobación para entrenamiento. Esta continuación no cierra D-04/D-06 ni autoriza T12. [Evidencia T10/T11](t10-t11-data-pipeline.md).

Después solicitó subir el proyecto a [ModoJorgeBT/nyc-yellow-taxi-mlops](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops). Esta instrucción autoriza crear el commit inicial, configurar ese remoto y publicar el código/documentación/fixtures pequeñas sobre `main`; sustituye la restricción anterior de no hacer commits ni publicar. Los datasets reales, entornos, cachés, secretos y reportes JSON generados permanecen excluidos. La revisión previa a publicación pasó 162 pruebas y Ruff; el repositorio remoto se observó vacío. Las evidencias históricas de tareas anteriores conservan su estado original y no se presentan como mediciones posteriores al push.

El PDF es un diseño inicial sujeto a refinamiento (p. 14), no evidencia de que el sistema exista. Se verificó su texto; no se validó visualmente la figura rasterizada de p. 5. El diagrama de arquitectura de T01 se deriva del flujo textual de §§5–6 y de spec §2.

Al solicitar T12/T13 el usuario pidió revisar el diccionario oficial TLC antes de decidir. Se leyó su página completa (18 de marzo de 2025); no establece destino declarado ni semántica de zona/DST. Después aprobó origen/calendario/pasajeros opcionales bajo conteo conocido al abordar, destino deshabilitado, históricos America/New_York con cuarentena de horas ambiguas/inexistentes y duración UTC; inferencia con offset. También aprobó scikit-learn/tzdata y transitivas, fijadas con hashes. [Contrato y evidencia T12/T13](t12-t13-features.md). D-04 y ventanas/recursos permanecen pendientes; no se cambia raw ni se habilita entrenamiento real.

Posteriormente solicitó preparar D-04 con perfilado acotado de 2024 y presentar umbrales antes de aplicarlos. Se analizaron 240.000 filas con muestreo aleatorio estratificado; por el formato Parquet se decodificaron 41.169.471 filas en bloques, con pico RSS 169,17 MiB en la repetición. No se abrieron archivos de 2025. [Propuesta D-04](d04-quality-proposal.md) y [evidencia](../reports/d04_profile_2024.md) presentadas antes de aplicar límites. Después el usuario aprobó la política completa y, separadamente, el registro/uso académico únicamente de enero de 2024. [Activación y límites](d04-activation.md): APPROVED_REAL, piloto completo WARN/VALIDATED_REAL, calidad true y entrenamiento false. Fuente/fecha de descarga siguen nulas; los otros 23 archivos no están incorporados.

Posteriormente se completaron el registro de los 24 archivos y la validación de abril–diciembre de 2025 bajo D-04 congelada: nueve rechazos, sin nuevas excepciones ni features para esos lotes. Quedan 15 versiones de features aceptadas; T14 integral no se cierra. [Resultados por mes](../reports/quality/t14_full_preparation.md).

El usuario solicitó expresamente crear el segundo commit y hacer push a GitHub, documentando ambas entregas. Esta autorización permite publicar los cambios acumulados de código, pruebas, configuración pública y evidencia documental. No concede nuevas excepciones de calidad, cierre de T14 ni promoción. El [historial de commits](commit-history.md) distingue el primer commit T01–T11 del segundo, con features, D-01/D-02/D-04 y baseline T15; los datos y artefactos locales permanecen excluidos.

Continuación del 2026-11-05: el usuario pidió terminar T14, presentar los incumplimientos D-04 para aprobación antes de consumir los lotes y continuar con T16/T17 después del cierre. Se revalidaron hashes/tamaños de nueve raw, manifiestos y reportes FAIL contra D-04 congelada. La [propuesta exacta](t14-quality-exceptions-proposal.md) cubre abril–diciembre de 2025, 543.725 filas inválidas a excluir y 36.980.851 potencialmente elegibles antes del corte temporal. Está PENDIENTE DE APROBACIÓN: no autoriza excepciones nuevas, modificación de umbrales ni cierre anticipado. La ampliación versionada del lector para conjuntos de dos fallos se somete a esa decisión antes de implementarse/aplicarse.

El usuario aprobó después la pregunta concreta: «Sí, aprobar los nueve meses con esas exclusiones y trazabilidad». Se registran nueve autorizaciones v2 por mes/hash/reporte, sin modificar D-04 ni la autorización v1 de marzo. El lector exige el conjunto exacto de fallos autorizado y conserva las exclusiones y FAIL medidos. Pruebas específicas: 22 aprobadas; suite de desarrollo: 391 aprobadas. Aplicación real y auditoría de T14 aún pendientes; estos resultados no cierran T14 ni inician T16.

El usuario aprobó también el [perfil concreto de T16 y el protocolo T17](t16-t17-execution-proposal.md): escalado train-only, SGD Huber y MLP16 con una pasada completa, predicciones acotadas y recortes registrados; métricas exactas y segmentos definidos por validation, con selección congelada antes de test. D-02 conserva 12 GiB libres/8 GiB RSS. Ambas fases quedan autorizadas después del cierre auditado de T14, sin promoción ni nuevas dependencias.

## 2. Invariantes

El único target es duración en minutos, calculada históricamente con llegada menos recogida. Solo puede inferirse con información disponible al inicio. No son predictores llegada, duración/target, tarifas, propinas, pagos, peajes, cargos finales ni distancia medida por taxímetro. No se cambia el caso de uso para acomodar datos disponibles.

El éxito es el ciclo MLOps auditable y reproducible, incluyendo baseline y dos candidatos, evaluación temporal, API, CI, monitoreo, decisión de retraining y rollback; no una mejora de precisión inventada.

## 3. Registro D-01…D-08

| ID | Estado y decisión | Responsable de resolver | Antes de / evidencia necesaria |
|---|---|---|---|
| D-01 | APROBADA. Train 2024; validation ene–mar 2025; test original abr–jun; replay jul–dic. Extensión final independiente ene–mar 2026 aprobada y auditada. | Equipo | [Protocolo original](d01-d02-protocol.md) y [evaluación final separada](../reports/evaluation/lightgbm_final_evaluation.md). T14 completa; sin presumir disponibilidad histórica de publicación. |
| D-02 | APROBADA. Todos los elegibles. Preparación 4/2; entrenamiento 8/4; inferencia final 2026 6 GiB libres/2 GiB RSS. Cuatro hilos, un candidato, 2 h y 50 GiB disco. CI exclusivo con fixtures: 2 CPU/4 GiB, 10 GiB disco y 20 min por job. | Equipo | [Revisión de entrenamiento](d02-t16-resource-review.md), [revisión final](d02-final-evaluation-resource-review.md) y [CI local](t26-t28.md). Presupuestos científicos y build local intactos. |
| D-03 | PARCIAL. Locks Windows 24/95/97 intactos; Linux 99 paquetes y Debian fijados. Serving/Compose y Actions verificados. Ruff/BuildKit fijados y perfil CI aprobado 2 CPU/4 GiB/10 GiB disco/20 min; PR verde y demostración roja/verde reales. Evidently pendiente. | Equipo | [T23–T25 y G4](t23-t25-docker.md); [T26–T28](t26-t28.md), solo fixtures en CI. |
| D-04 | V1 congelada; diez excepciones exactas de 2025 y tres de ene–mar 2026 por mes/hash/reporte aprobadas y aplicadas. | Equipo | 27 lotes: 14 pasan calidad y 13 aceptados excepcionalmente; FAIL y exclusiones conservados. [Excepciones finales](lightgbm-final-quality-exceptions-proposal.md). Cualquier nuevo incumplimiento requiere aprobación. |
| D-05 | PENDIENTE para reglas automáticas/futuras; T19 tiene aprobación humana puntual. 115 % en dos ventanas, PSI 0.20, mejora 2 % o no inferioridad son propuestas del PDF pp. 8–9. | Equipo | T32/T34: referencia, ventanas, volumen mínimo, bins/categorías, margen de no inferioridad y tolerancias por segmento aprobados. |
| D-06 | APROBADA el 2026-11-09: REST v1 con offset, origen del catálogo, pasajeros opcionales/null o entero 0–6; campos extra y coerciones rechazados. Destino deshabilitado. | Equipo | [Contrato y pruebas T20–T22](t20-t22-serving.md); versión cargada fija, 422/503/500 sin secretos. |
| D-07 | APROBADA, IMPLEMENTADA Y VERIFICADA. MLflow 3.16.1 aislado, SQLite/artefactos persistentes y loopback; cuatro versiones; LightGBM v4 champion por T19. | Equipo | [Registro real, carga, linaje y reinicio auditados](../reports/tracking/t18_completion.md). Compose T24/T25 verificado con copia aislada; promociones futuras requieren aprobación. |
| D-08 | T14–T28 con cierre técnico PASS; revisión humana independiente. T26 con PR verde y demostración roja/verde reales. | Equipo | [CI local/remoto: 601 pruebas y smoke HTTP](../reports/monitoring/t26_github_ci.md); G3/G4 verificados. G5 sigue pendiente de T29–T31; sin promoción futura automática. |

La arquitectura local está confirmada en el [ADR 0001](adr/0001-arquitectura-local.md). Las propuestas técnicas de persistencia, modelos y librerías no se consideran aprobadas por ese ADR.

## 4. Matriz de trazabilidad

Las páginas son las numeradas 1–14 del PDF. Las tareas y verificaciones de ejecución siguientes son futuras, no resultados obtenidos.

| Requisito / decisión | PDF | Intent | Spec | Plan y evidencia futura |
|---|---|---|---|---|
| Target único e inferencia al inicio | pp. 2, 4, 13 | §§2, 6 | §§1, 5 | T12/T20; whitelist y contrato causal. |
| Procedencia, hash, CLI e idempotencia | pp. 3, 6 | §5.1 | §4 | T06/T07/T11; manifiestos y reejecución. |
| Quality Gates y fallo crítico | pp. 6–7 | §§5.2, 7 | §6 | T08–T11; lote bloqueado y reporte. |
| Pipeline de features compartido | pp. 4, 6 | §§5.3, 6 | §5 | T12/T13; consistencia train/serving. |
| Baseline, dos candidatos y cortes temporales | pp. 6–8 | §5.4 | §§4.2, 7 | T14–T17; métricas, semillas y periodos. |
| MAE, RMSE, MedAE y P90 absoluto | p. 8 | §5.4 | §7 | T17; cálculos con valores conocidos. |
| Tracking y registro separados de promoción | pp. 6, 9–10 | §§5.5, 5.9 | §8 | T18/T19/T35; linaje y auditoría. |
| Predict, health, model-info y versión | p. 6 | §§5.6, 7 | §9 | T20–T22/T25; 200/422/503 y versión cargada. |
| Docker, Compose y persistencia | pp. 5–6, 9–10 | §§5.7, 6 | §10 | T23–T25; build y reinicio sin pérdida. |
| CI con pruebas y build | pp. 4–5, 10–11 | §§5.7, 7 | §12 | T26; runs en GitHub. |
| Calidad, drift, desempeño y servicio | pp. 6, 8 | §5.8 | §11 | T27–T31; reportes por ventana y etiquetas. |
| Triggers, comparación y rollback | pp. 7–10 | §§5.9, 7 | §§8, 11 | T32–T36; decisión, aprobación y restauración. |
| Reproducibilidad y exclusión de binarios/secretos | pp. 10–11 | §§5.10, 6 | §§13, 15 | T02/T03/T37; revisión en otro entorno. |
| Periodos propuestos y recursos | pp. 3, 13 | §8 | §§4.2, 17 | D-01/D-02; T05/T14. |
| Herramientas y umbrales por aprobar | pp. 8–9, 13 | §8 | §§11, 17 | D-03/D-04/D-05; aprobación explícita. |
| Arquitectura, entregables y sprints | pp. 5, 10–13 | §§3, 7 | §§2, 16 | T01 y D1; T02–T38 para ejecución. |

## 5. Hallazgos y tratamiento documental

| ID | Hallazgo | Tratamiento en T01 |
|---|---|---|
| H-01 | Intent §8 aún dejaba local/cloud y MLflow abiertos pese al acuerdo del equipo. | Actualizado el acuerdo local y las cuatro tecnologías; resto pendiente. |
| H-02 | Spec §11 rotulaba promoción 2 % como BASE y §17 como hipótesis. PDF §18 pide acordar umbrales. | Identificados como PROPUESTA pendiente, conservando separación de entrenamiento y promoción. |
| H-03 | Spec §5 y T12 podrían dar por aprobado destino conocido. PDF p. 4 lo lista como candidato, sin resolver su disponibilidad. | Aclaración de D-06; T12 no puede cerrar causalidad hasta resolverla. |
| H-04 | G0 confundía registro de pendientes con autorización para datos y entrenamiento. | Aclarado: requiere aprobación D-01/D-02/D-04 para esas ejecuciones; documentación no cierra G0. |
| H-05 | DoD general exigía código y tests para T01 documental. | Excepción documental explícita; D-08 general sigue pendiente y T01 requiere revisión humana. |
| H-06 | T02 confundía disponibilidad de Pytest con entorno reproducible; T04 omitía T03. | CORREGIDO documentalmente con aprobación: T02 valida estructura/importaciones/exclusiones; suite e instalación en T03. T04 depende de T03. |
| H-07 | T18 requiere reiniciar MLflow, pero Compose completo se entrega en T24. | Precondición D-07 explícita en T18. Elección y prueba local aún PENDIENTES; Compose completo sigue en T24. |
| H-08 | T34 exige smoke tests pero no declaraba T25; runner GitHub sin acceso directo a local. | Dependencia T25 añadida con aprobación. Orquestación local/Actions manual sigue PENDIENTE antes de T36. |
| H-09 | Referencia de entregables PDF omitía p. 10. | Spec §19 actualizado a pp. 10–12; comparación textual ahora disponible. |
| H-10 | T12 no declaraba D-06 pese al destino pendiente. | CORREGIDO: D-06 requerida antes de aprobar features de destino; hipótesis aún PENDIENTE. |
| H-11 | T14 no exigía en aceptación la disponibilidad de etiquetas al corte. | CORREGIDO: prueba de viajes que cruzan corte y declaración de replay/publicación añadidas; política concreta D-01/D-06 pendiente. |
| H-12 | T05 presuponía obtener datos aunque el equipo ya tiene Parquet. | CORREGIDO: acepta muestra local autorizada; procedencia desconocida se registra sin inventar metadatos. No se implementa incorporación a manifiestos ahora. |
| H-13 | Autorización escrita de T02 desactualizada y diagrama sin referencia ni observación de rechazos. | CORREGIDO: preparación T01/T02 autorizada; referencia y reportes de fallo conectados a monitoreo, sin habilitar datos rechazados para train. |

## 6. Riesgos y pruebas que deberán resolverlos

Todos los riesgos siguen ABIERTOS; no hay ejecución del sistema que los descarte. Prioridad alta significa resolver antes de la tarea afectada, no implementar ahora. Responsables: equipo, con revisión cruzada; asignación individual aún pendiente.

| ID / prioridad | Riesgo y efecto | Tratamiento propuesto y evidencia futura | Depende de / antes de |
|---|---|---|---|
| R-01 Alta | Destino observado puede no ser conocido al inicio; evaluación con información privilegiada. | Aprobar hipótesis de destino declarado y limitación del histórico o revisar features explícitamente; contrato para destino ausente/cambiado. | D-06; T12/T20. |
| R-02 Alta | Etiquetas de viajes o datos publicados después del corte contaminan simulación retrospectiva. | Definir disponibilidad de etiqueta y publicación; separar replay offline de operación real. Probar viajes que cruzan corte. | D-01; T14/T33. |
| R-03 Alta | Imputación, codificación, baseline o agregados ajustados con futuro. | Ajustar solo train; agregados con viajes completados/disponibles anteriores, sin propia etiqueta. Tests de corte y serialización. | T12–T15. |
| R-04 Alta | Test reutilizado para selección o promociones; comparación desigual. | Reservar test final; definir ventanas nuevas para retraining, mismo conjunto evaluable y etiquetas maduras para ambos modelos. | D-01/D-05; T17/T34. |
| R-05 Alta | Timestamps históricos y API no equivalentes por DST. | Aprobar interpretación de históricos, ambigüedad e inexistencia; tests de offsets, DST y viajes limítrofes. No suponer timestamps históricos con offset. | D-06; T09/T13. |
| R-06 Media | Filtros de duración eliminan casos difíciles y sesgan métricas. | Definir población válida con train/EDA; registrar tasas y motivos de exclusión; no calibrar filtros con test. | D-04; T05/T09/T17. |
| R-07 Alta | Duplicados, zonas especiales, revisiones o descargas parciales corrompen trazabilidad. | Definir clave de duplicados, catálogo versionado, revisión remota, concurrencia y escrituras seguras; pruebas de interrupción/conflicto/esquema. | D-04/D-06; T06–T11. |
| R-08 Alta | Copias de datos, codificación y candidatos exceden RAM/disco/CPU local. | Medir recursos host/Docker; evaluar perfiles pequeños y académicos, lectura por lotes y muestreo determinista. No asumir entrenamiento incremental de todos los estimadores. | D-02; T05/T14/T16. |
| R-09 Alta | Tracking accesible pero artefactos inaccesibles por rutas host/contenedor. | Elegir servicio de artefactos o montajes compatibles; probar carga desde host, pipeline y API tras reinicio. | D-07; T18/T24/T25. |
| R-10 Alta | Pérdida de SQLite/artefactos, permisos o escrituras concurrentes. | Definir volúmenes, usuario, concurrencia y backup coherente; probar restauración sin borrar evidencia. | D-07; T18/T24. |
| R-11 Alta | API arranca sin modelo, informa alias nuevo con modelo antiguo o falla recarga. | Bootstrap explícito; versión cargada en respuestas; ensayo de 503, recarga fallida y rollback con versión anterior recuperable. | T19/T21/T25/T35. |
| R-12 Alta | Entornos de entrenamiento y serving incompatibles; Windows difiere de contenedores. | Fijar versiones compatibles en T03; comprobar rutas con espacios/acentos, permisos, montajes y comandos PowerShell; prueba en entorno limpio. | D-03; T03/T23–T25/T37. |
| R-13 Alta | MAE sin etiquetas, uniones erróneas o drift sin referencia reproducible. | Definir ID/protocolo de replay, ventanas, tamaños mínimos y referencia; sin etiquetas NOT_AVAILABLE. Drift no implica pérdida de precisión. | D-05/D-06; T29–T32. |
| R-14 Media | Dependencias de tareas incompletas y CI sin acceso al entorno local. | Resolver H-06/H-07/H-08 antes de ejecutar tareas; CI con fixtures, sin entrenamiento masivo ni promoción por registro. | T02/T18/T26/T34/T36. |

## 7. Dependencias y alcance de la revisión

T01 no depende de otras tareas. El PDF ya está disponible, por lo que su comparación textual deja de estar NO VERIFICADA. No se extrapola esa lectura a validación docente ni a funcionamiento de herramientas.

Orden técnico propuesto: contrato causal/temporal → datos y calidad → recursos/modelado → registro persistente → champion aprobado y serving → monitoreo → comparación/promoción/rollback. Dependencias T04/T03, T12/D-06 y T34/T25 corregidas con aprobación; H-07 y orquestación H-08 continúan como precondiciones pendientes de tareas futuras.

Las decisiones D-01/D-02/D-04 de G0 quedaron aprobadas posteriormente para el protocolo local con todos los elegibles. No equivale a controles operativos implementados ni a entrenamiento autorizado/ejecutado. La documentación puede registrar decisiones abiertas; el siguiente trabajo exige aprobación de la tarea y sus dependencias. G1 requiere además entorno, fixtures y prueba ejecutada: no se declara por T01.

## 8. Aceptación y evidencia T01

| Verificación | Estado |
|---|---|
| Tres Markdown leídos completos y texto de las 14 páginas del PDF contrastado | VERIFICADO en auditoría T01. |
| Target, restricciones y alcance preservados | Revisados documentalmente; sin implementación. |
| D-01…D-08, responsables, pendientes, riesgos y matriz con referencias | Preparados en este archivo para revisión del equipo. |
| Arquitectura lógica y ADR de decisión local | Preparados; no acreditan servicios levantados. |
| Integridad del PDF | VERIFICADO: SHA-256 idéntico antes y después de las ediciones; archivo conservado en raíz. |
| Referencias locales, estados coherentes y límite de archivos afectados | VERIFICADO inicialmente: seis Markdown y 24 enlaces. Segunda revisión: ocho Markdown verificados, incluidos README y evidencia T02, bloques cerrados y sin caracteres de sustitución UTF-8 ni rutas Windows absolutas; D-01…D-08 presentes en spec/plan/registro. Referencias y recuento final en la evidencia T02. |
| Siete correcciones de la segunda revisión | VERIFICADAS: D-06 en T12, etiquetas al corte en T14, T03 en T04, T25 en T34 y precondición D-07 en T18, separación de criterios T02/T03, archivos locales en T05 y autorización/diagrama actualizados. |
| Revisión humana final de T01 | APROBADA por el usuario el 2026-11-03, junto al cierre T02 y solicitud T03. |
| Pytest, Ruff, Docker, modelos, métricas y CI | Suite funcional NO EJECUTADA. Solo disponibilidad de Pytest consultada: versión 9.2.0. Resto fuera de validación T01/T02. |

Comandos de auditoría: `Get-Content -Raw -Encoding UTF8`, `Get-ChildItem`, `rg --files`, `Get-FileHash -Algorithm SHA256` y comprobaciones locales de Markdown. Se leyó el texto PDF mediante Node y sus módulos integrados `fs`/`zlib`, decodificando streams y mapas ToUnicode sin instalar paquetes ni generar un extractor en el proyecto.

La comprobación de enlaces/estructura se ejecutó mediante `node -e` con `fs`/`path` integrados: seis Markdown, 24 enlaces locales y cero errores. La inspección de estados usó `rg -n` sobre los tres documentos rectores. Son comprobaciones documentales; no acreditan renderizado visual de Mermaid, compatibilidad de dependencias ni funcionamiento de servicios.

En la auditoría inicial la carpeta no tenía repositorio Git (`git status` no fue aplicable); su inicialización local está ahora autorizada en T02. El alias `python` de Windows no arrancó. Se pudo consultar un intérprete existente Python 3.14.7 por ruta explícita; no tenía pypdf, fitz ni pdfplumber. Esto no selecciona Python 3.14 para el proyecto ni certifica compatibilidad MLOps; la elección corresponde a T03. No se instaló nada.

Las siete correcciones de la segunda revisión están aplicadas y el usuario aprobó el cierre humano de T01/T02. T03 fue autorizada después; G0/G1 no se declaran cerrados por esas aprobaciones.

La preparación de T02 y su Git local se ejecutaron sin commits ni remotos; estructura, importaciones y exclusiones verificadas. Evidencia: [verificación T02](t02-verification.md). La aprobación humana posterior está registrada sin convertir las decisiones pendientes en acuerdos.

## 9. Continuación T03 y datos locales

Evidencia de entorno y alcance de reproducibilidad: [T03](t03-environment.md). Inventario de metadatos: [Parquet 2024/2025](../reports/raw_inventory.md). Los 24 archivos se organizaron por año/mes con hashes conservados; suman 1.418 GiB y 89,892,322 filas declaradas en footers. Se observaron dos esquemas: 19 columnas en 2024 y 20 en 2025, con `cbd_congestion_fee` adicional y sin cambios de tipo en columnas compartidas.

No se ejecutó EDA de todas las filas, no se aprobaron Quality Gates ni se asignaron particiones. Procedencia y fechas de descarga no verificadas. Las observaciones aportan evidencia a R-07/R-08, pero esos riesgos siguen abiertos; D-01/D-02/D-04/D-05/D-06/D-07 no se cierran por este inventario.

## 10. Continuación T04/T05

[Evidencia técnica](t04-t05-verification.md): diez fixtures sintéticas (103.906 bytes), semilla y anomalías conocidas; 32 tests aprobados. [EDA acotado](../reports/eda_schema.md): 90.112 filas de 2024, con 35 duraciones no positivas, 155 recogidas fuera de mes y 4.096 pasajeros nulos. No son tasas de todo el año ni hallazgos del test 2025. Hashes y estadísticas repetibles, sin modificar raw ni aprobar Quality Gates. D-02 aporta mediciones parciales y D-04 propuestas; G1 tiene evidencia técnica pero su cierre humano sigue pendiente.

## 11. Continuación T06/T07 y procedencia local

El registro local no inventa `source_url` ni `downloaded_at_utc`: quedan nulos. `expected_source_url` es una referencia canónica, no prueba de origen; `recorded_at_utc` sí registra la acción real. El manifiesto queda LOCAL_UNVERIFIED aunque luego la ejecución se salte por idempotencia. Esta política no relaja T08/T09 ni aprueba procedencia o calidad para entrenamiento.

[Contrato y evidencia](t06-t07-ingestion.md). No hay opción de reemplazo destructivo; se bloquean divergencias. El `SKIPPED` verifica el estado local, sin afirmar que el publicador remoto no haya revisado el archivo. Las escrituras de datos/manifiesto se publican por separado sin reemplazar destinos; fallos intermedios requieren revisión explícita. El estado DOWNLOADED solo acredita adquisición registrada por el pipeline, no Quality Gates ni escaneo de todas las páginas.

## 12. Cierre documental D-01/D-02 y ratificación D-04

El usuario aprobó train 2024, validación ene–mar 2025, test abr–jun y replay jul–dic. Rechazó submuestreo de modelado y aprobó después SGDRegressor/MLPRegressor pequeño incrementales con todos los elegibles y presupuesto 4 hilos/8 GiB/2 h por candidato, preflight 12 GiB RAM/50 GiB disco libres. Ratificó D-04 y autorizó uso académico de los 24 hashes existentes. [Protocolo completo](d01-d02-protocol.md) y [registro estructurado](d01-d02-execution-protocol.json). Solo enero sigue incorporado y validado; esta revisión no registra ni procesa los otros 23, no entrena ni implementa T14. Las evidencias anteriores describen su fecha y alcance originales.

## 13. Continuación T14

El usuario autorizó trabajar en T14. Se implementaron configuración de periodos/recursos, CLI de particionado completo por bloques y pruebas offline, sin resolver decisiones nuevas de modelado. [Contrato, verificación y límites](t14-temporal-splits.md). T14 no hace fit ni incorpora automáticamente los otros 23 archivos. Solo enero permanece registrado/validado; no hay features reales preparados. D-02 tiene preflight y supervisión cooperativa para particionado, pero temporizador/controles de candidatos y medición de entrenamiento corresponden a T16. T15 y siguientes requieren autorización.

## 14. Autorización de cierre real T14/T15

El usuario solicitó terminar ambas tareas y aprobó explícitamente: (1) mediana global exacta de todas las etiquetas elegibles train 2024, predicción solo en validación; (2) perfil específico de preparación/mediana con preflight 4 GiB RAM/50 GiB disco libres y máximo RSS 2 GiB, secuencial por bloques, sin reducir datos al fallar. El perfil de candidatos SGD/MLP conserva 12 GiB libres/8 GiB RSS. La incorporación/validación/features de los 24 archivos autorizados se ejecuta como prerrequisito del cierre real; no hay descargas ni promoción. [Contrato](t15-baseline.md). Resultados reales pendientes de verificación al terminar el flujo.

## 15. Rechazo real y decisión de conservar D-04

15 meses registrados LOCAL_UNVERIFIED; 14 completaron calidad/features REAL (2024 completo y enero–febrero de 2025). Marzo de 2025 rechazado: 22.280 duraciones no positivas/4.145.257 filas (0,537482 %), máximo 0,50 %. El usuario decidió mantener D-04. No hay particiones reales ni baseline real publicados. [Reporte](../reports/quality/t14_t15_preparation.md). El usuario eligió mantener D-04 y revisar la fuente: el tamaño y ETag multipart coinciden con el objeto oficial actual; no se encontró indicio de versión corregida en esa URL. Procedencia histórica y SHA-256 remoto sin verificar. [Diagnóstico y decisión](t14-t15-quality-blocker.md). Ninguna excepción ni cambio global aprobados. Las opciones previas de ejecución en curso ya no describen un trabajo activo.

## 16. Separación y ajuste independiente T15 aprobados

El usuario aprobó ajustar todo train 2024 disponible al corte dejando evaluación pendiente, sin consumir marzo/test/replay ni cerrar T14/T15. Ajuste exacto train 2024 completo y auditado: 41.119.495 etiquetas, mediana 12,983333 minutos; 561 filas apartadas por corte de etiqueta entre 41.120.056 elegibles DQ. Evaluación y cierre de T14/T15 pendientes de marzo 2025; D-04 permanece congelada. [Reporte](../reports/quality/t15_train_fit.md). 356 pruebas en desarrollo y wheel. Modelo provisional, sin registro, promoción ni candidatos T16. La aprobación modifica únicamente la dependencia del ajuste; el flujo completo conserva T14 completa como precondición.

## 17. Excepción puntual y cierre técnico de T15

El usuario autorizó «Hagamos una excepción y no rechacemos el lote solo sobre este mes y asi podemos cerrar T15». Se conserva la política global y se limita el override al mes/hash/reporte y único FAIL de duración no positiva. [Contrato](t15-march-exception.md). La evaluación del modelo congelado completa la separación de fases sin preparar test/replay ni declarar T14 integral completa. T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [Evidencia](../reports/quality/t15_baseline_validation.md).


## Cierre técnico T14 — 2026-11-05

T14 CIERRE TÉCNICO PASS: 24 meses registrados, validados/aceptados y con features; 89.892.322 raw, 627.221 exclusiones de calidad y 2.952 por disponibilidad de etiqueta. Particiones auditadas: train 41.119.495; validation 11.163.264; test 12.712.466; replay 24.266.924. Todas las identidades y valores publicados coinciden con las fuentes; train/validation coinciden con T15 congelada. D-04, 24 raw y diez FAIL originales intactos. Revisión humana de resultados independiente del cierre técnico. T16/T17 aprobadas para continuar; todavía sin entrenamiento ni métricas nuevas. [Evidencia completa](../reports/quality/t14_completion.md). El recibo local fija hashes del manifest de split, catálogo y configuración; los modelos T15 y sus etiquetas/contextos congelados permanecen intactos.


## Revisión de recursos T16/T17 — 2026-11-05

El preflight inicial de T16 midió 10,49 GiB libres frente a 12 requeridos y detuvo el fit. El usuario aprobó «Sí, aprobar el perfil incremental 8 GiB libres/4 GiB RSS». Se mantiene todo el dataset elegible, cuatro hilos, un candidato, dos horas, 50 GiB disco y parámetros/segmentos ya aprobados. [Registro](d02-t16-resource-review.md) y [configuración separada](../configs/candidates.yaml); D-01/D-04 y model.yaml congelados. La implementación pasó 423 pruebas de desarrollo; wheel en verificación y corrida real pendiente.

## Resultados posteriores y ampliación de candidatos — 2026-11-05

SGD Huber y MLP16 se ajustaron con las 41.119.495 filas train, una pasada por candidato. SGD fue elegido con validation antes de abrir test: MAE 6,876910 frente a 7,741890 del baseline. En test obtuvo MAE 7,965068 frente a 9,032999. MLP fue peor que el baseline; SGD empeoró ligeramente P90 en validation. Sin reajustes después de test ni promoción.

[Auditoría T17](../reports/evaluation/t17_model_comparison.md). El usuario aprobó el ajuste D-02 a 8 GiB libres/4 GiB RSS antes del fit; los dos candidatos y T17 respetaron ese presupuesto. Las referencias anteriores a 12/8 y tareas pendientes describen estados históricos.

Después de evaluar el test original, el usuario solicitó LightGBM y aprobó su [perfil concreto](t16-lightgbm-extension-proposal.md), incluyendo discretización train-only con hasta 200.000 filas y ajuste de árboles sobre todos los registros elegibles. Aprobó **solo validation** para su evaluación; una nueva evaluación final independiente queda pendiente. No se reutiliza test/replay ni se cambia la selección original. Estado: ajuste y validation auditados; nueva evaluación final independiente pendiente.

**Resultado LightGBM:** LightGBM 4.7.0 fue entrenado con las 41.119.495 filas train y 100 árboles. En las 11.163.264 filas validation: MAE 6.496404, RMSE 9.847425, MedAE 4.631360 y P90 13.478764 minutos. Ajuste y evaluación auditados; 447 pruebas por entorno. Solo validation: una nueva evaluación final independiente sigue pendiente. La selección SGD y el test de la primera comparación permanecen intactos; no hay promoción. [Evidencia](../reports/evaluation/lightgbm_validation.md). D-03 incorpora lightgbm 4.7.0 y lock de 24 paquetes; los 23 existentes no cambiaron de versión. No se resolvieron D-05/D-07 ni se aprobó un nuevo champion.


**Evaluación final independiente completada y auditada — 2026-11-05:**
enero–marzo de 2026, 10.937.087 viajes; MAE LightGBM **7,742891 min**, SGD
**8,352735** y baseline **9,141254**. Se excluyeron 139.305 filas DQ mediante
tres excepciones humanas exactas y 814 por corte de etiqueta; los 27 raw,
modelos y selección de 2025 permanecen intactos. Reinicio de recursos aprobado
6 GiB libres/2 GiB RSS solo para inferencia final; entrenamiento 8/4 y preparación
4/2 sin cambios. 474 pruebas por entorno y auditoría completa. Sin promoción.
[Reporte final y trazabilidad](../reports/evaluation/lightgbm_final_evaluation.md). Las referencias anteriores a evaluación
final pendiente describen la entrega histórica previa a esta aprobación. T18
requiere D-07 y dependencias; no hay Registry ni champion todavía.


**T18 verificada — 2026-11-05:** D-07 aprobada e implementada con MLflow 3.16.1
en entorno separado, SQLite y artefactos persistentes. Cuatro candidatos:
baseline v1, SGD v2, MLP v3 y LightGBM v4, sin alias. Reinicio real, carga,
idempotencia y auditoría independiente PASS; 488 pruebas nativas más una omisión
explícita y 489 sobre wheel MLflow. Los modelos y evaluaciones anteriores no
cambian. Champion/T19 y G3 permanecen pendientes de aprobación.
[Registro y evidencia](../reports/tracking/t18_completion.md). Las referencias previas a D-07 o Registry
pendientes describen la cronología anterior a esta aprobación y ejecución.


**T19 verificada — 2026-11-05:** el usuario aprobó LightGBM v4 como champion
inicial, después de conocer las limitaciones por rutas, y descartó optimización
de hiperparámetros. Alias `champion` aplicado a la versión fija 4, run
`be28c76c84c44efa8914c5950a2959bf`; paquete, aprobación y resolución auditados.
501 pruebas nativas PASS y dos omisiones explícitas; 503 PASS sobre wheel MLflow.
G3 cumple sus condiciones de Sprint 3. D-05 conserva pendientes sus reglas
automáticas de drift y promociones futuras; no se aprueban nuevos umbrales.
[Decisión, pruebas y evidencia](../reports/model_selection.md). Las menciones anteriores a champion
pendiente son históricas; API y despliegue siguen en sus tareas posteriores.


**T23–T25 verificadas — 2026-11-09:** build Docker Linux amd64, usuario
10001 y límites 2 GiB/2 CPU por API/MLflow verificados; smoke real 200/422/503,
reinicio y persistencia PASS. G4 cumple técnicamente su alcance. API en 8080
y MLflow Docker en 5001, solo loopback; originales conservados. El usuario
aprobó el perfil Linux, el cambio de puerto y la auditoría portable de
metadatos sin modificar datos. Volumen Linux aislado con champion v4;
sin reentrenamiento ni promoción nueva. [Guía y evidencia](t23-t25-docker.md).
Las menciones previas a Docker pendiente describen estados históricos;
T26–T38 y la revisión humana de resultados permanecen independientes.
