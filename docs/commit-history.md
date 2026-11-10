# Historial de entregas en Git

Repositorio: [ModoJorgeBT/nyc-yellow-taxi-mlops](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops), rama `main`. El usuario autorizó cada publicación, incluida «Favor subir el tercer commit a github». Cada entrega conserva el estado y las aprobaciones de su momento; publicar no autoriza tareas, lotes ni promociones futuras.

## Resumen de las cinco entregas

La numeración identifica entregas funcionales. La cuarta contiene varios commits
y un merge; la quinta continúa ese historial sin reescribirlo.

| Entrega | Alcance | Identificación Git |
|---|---|---|
| 1 | T01–T11: arquitectura, entorno, ingesta y calidad | 164bf9e |
| 2 | T12–T15: features, políticas reales y baseline; bloqueo histórico T14 | 27b09d2 |
| 3 | T14 integral, candidatos, evaluación independiente, MLflow y champion v4 | 07f8729 |
| 4 | T20–T31: API, Docker, CI, métricas y monitoreo | PR #1 y merge 21a6abf; commits detallados más abajo |
| 5 | T32–T38: challenger/gate, operación reversible, reproducción y README renovado | Commit con mensaje `Complete T32-T38 retraining lifecycle and refresh project README` |

El SHA de la quinta entrega se obtiene con el comando incluido en su sección;
no se escribe un hash autorreferente dentro del propio commit.

## Primer commit — Base del proyecto y pipeline hasta T11

- Commit: [`164bf9e3f08fe5ae528d36fc0a2fa06f33a74943`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/164bf9e3f08fe5ae528d36fc0a2fa06f33a74943).
- Mensaje: `Initial project: MLOps data pipeline through T11`.
- Alcance registrado por Git: 74 archivos y 5.529 líneas añadidas.

Incluyó requisitos, especificación, plan, arquitectura, decisiones y ADR; estructura modular y exclusiones de Git; entorno Python reproducible con versiones y hashes; fixtures sintéticas pequeñas y perfilado acotado de 2024. Implementó ingesta con manifiestos, hash e idempotencia, registro local explícito, contrato de esquema, motor configurable de calidad y CLI raw→validated con integración offline (T01–T11).

La verificación previa a esa publicación aprobó **162 pruebas**, además de Ruff. D-04 y la aprobación operativa de datos reales seguían pendientes. El PDF académico quedó versionado como referencia; los Parquet reales, modelos, entornos y secretos quedaron excluidos. Evidencia: [T03](t03-environment.md), [T04/T05](t04-t05-verification.md), [T06/T07](t06-t07-ingestion.md), [T08/T09](t08-t09-validation.md) y [T10/T11](t10-t11-data-pipeline.md).

## Segundo commit — Features, calidad real y baseline temporal

- Mensaje: `Add T12-T15 features and baseline; document T14 quality blockers`.
- Padre: `164bf9e3f08fe5ae528d36fc0a2fa06f33a74943`.
- Commit: [`27b09d2d0a0344b88bd9dbfefabb8154f81a99ec`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/27b09d2d0a0344b88bd9dbfefabb8154f81a99ec).

| Área | Contenido incorporado y evidencia |
|---|---|
| T12/T13 | Target temporal UTC, convención America/New_York y cuarentena DST; origen, calendario y pasajeros opcionales; destino y variables posteriores excluidos. Pipeline de scikit-learn, artefactos con linaje, procesamiento por bloques y pruebas de serialización/causalidad. [Contrato](t12-t13-features.md). |
| D-01/D-02 | Train 2024, validación ene–mar 2025, test abr–jun y replay jul–dic 2025. Todas las filas elegibles y perfiles de recursos separados para preparación/baseline y candidatos incrementales futuros. [Protocolo](d01-d02-protocol.md). |
| D-04 | Perfilado acotado de 2024, política aprobada/congelada, catálogo de zonas con hash, validación real y piloto enero 2024. Autorización académica de los 24 archivos por mes/hash con procedencia LOCAL_UNVERIFIED. [Política](d04-quality-proposal.md) y [activación](d04-activation.md). |
| T14 | Lector y particionado temporal implementados y probados con fixtures; 24 archivos registrados y 15 versiones de features aceptadas. Abril–diciembre de 2025 escaneados completos y rechazados por D-04: sin features publicadas para esos nueve lotes, sin particionado integral ni auditoría final de los 24 meses. [Contrato](t14-full-preparation.md) y [resultados](../reports/quality/t14_full_preparation.md). |
| Excepción marzo 2025 | Única aceptación excepcional aprobada, ligada a mes/hash/reporte y conservando el FAIL original y la exclusión de filas inválidas. No cambia umbrales globales ni se extiende a otros meses. [Alcance](t15-march-exception.md) y [configuración](../configs/quality-exception-2025-03.json). |
| T15 | Mediana global exacta de todo train elegible anterior al corte, congelada antes de evaluar validación. Ajuste y evaluación reales auditados, separados del cierre integral de T14. [Ajuste](../reports/quality/t15_train_fit.md) y [evaluación](../reports/quality/t15_baseline_validation.md). |
| Reproducibilidad | Dependencias de features aprobadas, lock con hashes, controles de recursos, pruebas unitarias/integración y evidencias Markdown; README, arquitectura y documentos rectores alineados. |

Resultado real de T15: **41.119.495 etiquetas de train**, mediana **12,983333333333333 minutos**; **11.163.264 predicciones** en validación enero–marzo 2025; **MAE 7,741889667454489** y **RMSE 11,912961986266831 minutos**. Las exclusiones por corte se auditaron. Test y replay no se usaron para evaluar ni ajustar modelos; su lectura posterior solo midió calidad y preparación de fuentes.

Verificación del código incluido: **380 pruebas aprobadas en desarrollo y 380 desde wheel instalado**, imports aislados, Ruff y comprobación de dependencias en ambos entornos. El código de `src` coincide con el wheel auditado, SHA-256 `67e22465cfb33755e0d8ec49a0a7ceaf89f2388171d7a4692990f8d3e0a198ef`; el lock tiene SHA-256 `372c8949a3c4fbc62c3f334d8ddf565ff213e56a80deca8d00a007cde6673529`. La preparación posterior de T14 no modificó módulos ni dependencias. Los controles documentales y del contenido a publicar se verifican antes de crear el commit.

Control previo a publicación: 36 documentos Markdown y 311 referencias locales verificados, política/configuración/catálogo consistentes, PDF académico intacto y código contrastado con el wheel probado. La revisión de archivos públicos no detectó credenciales ni rutas personales; se comprobó la exclusión de datos reales, catálogos locales, cachés y entornos. También se revisa el índice Git antes del commit.

T15 tiene cierre técnico; la revisión humana sigue siendo independiente. **T14 permanece pendiente por nueve lotes rechazados.** No se iniciaron candidatos T16, API, MLflow, Docker, CI, monitoreo, promoción ni rollback. No se añaden excepciones nuevas en esta publicación.

## Tercer commit — Preparación integral, modelos, MLflow y champion inicial

- Mensaje: `Complete T14-T19 modeling, MLflow tracking and LightGBM champion`.
- Padre: `27b09d2d0a0344b88bd9dbfefabb8154f81a99ec`.
- Commit: [`07f8729d2ff94820631fe76fdf3e827d4e04f02d`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/07f8729d2ff94820631fe76fdf3e827d4e04f02d).

| Área | Cambios y evidencia |
|---|---|
| T14 | Cierre integral de los 24 meses de 2024/2025: registro, calidad, features, cuatro particiones completas y auditoría de identidades, valores, cobertura y cortes. Nueve excepciones exactas adicionales aprobadas para abril–diciembre de 2025, conservando FAIL y exclusiones. [Cierre T14](../reports/quality/t14_completion.md). |
| T16 | SGD Huber y MLP16 incrementales ajustados con las 41.119.495 filas train; preprocesamiento train-only, una pasada y límites de recursos. LightGBM 4.7.0 con 100 árboles y el mismo train completo; discretización train-only. Supervisor del proceso nativo real y cancelación probados. [Entrenamiento](../reports/quality/t16_training.md), [extensión LightGBM](t16-lightgbm-extension-proposal.md). |
| T17 | Comparación temporal con métricas y segmentos exactos; primera selección SGD congelada antes del test original. LightGBM comparado inicialmente solo en validation. [Comparación original](../reports/evaluation/t17_model_comparison.md), [validation LightGBM](../reports/evaluation/lightgbm_validation.md). |
| Evaluación independiente | Tres descargas oficiales limitadas enero–marzo de 2026, manifiestos y hashes; tres excepciones D-04 expresas, 139.305 exclusiones de calidad y 814 temporales. Evaluación de los modelos congelados sobre 10.937.087 filas, sin reajustes ni reutilización del test/replay de 2025. Reinicio de recursos trazado y auditoría independiente. [Informe final](../reports/evaluation/lightgbm_final_evaluation.md). |
| T18 / D-07 | MLflow 3.16.1 aislado del entorno de modelado, lock propio de 95 paquetes, SQLite/artefactos persistentes y servicio loopback. Cuatro candidatos registrados con parámetros, métricas, código, datos y dependencias trazables; carga, reinicio e idempotencia auditados. [Guía](t18-mlflow.md), [resultados](../reports/tracking/t18_completion.md). |
| T19 | Elección humana LightGBM v4; alias `champion`, aprobación ligada a versión/run/paquete, eventos preparados/aplicados y resolución de versión fija. Pruebas de ausencia/divergencia de aprobación, integridad y recuperación de operación parcial. [Decisión](../reports/model_selection.md), [contrato público](../configs/champion.yaml). |
| Documentación | README, intent, spec, plan, decisiones y arquitectura alineados; G3 satisface el alcance de Sprint 3. Se incorpora el PDF de avance aportado por el equipo, sin modificarlo. |

Resultado final independiente, MAE en minutos: **LightGBM 7,742891**, SGD 8,352735 y baseline 9,141254. El usuario aprobó el champion inicial después de conocer las regresiones frente a SGD en 14/20 rutas; no se definieron tolerancias generales ni se optimizaron hiperparámetros. D-05 conserva pendientes las reglas automáticas de drift y promociones futuras.

Verificación de la versión de código incluida: **501 pruebas aprobadas y dos integraciones MLflow omitidas** en el entorno histórico; **503 aprobadas** desde wheel instalado en el entorno MLflow, con copia sin `src` ni datos reales y 40 imports aislados. Ruff, formato y comprobación de dependencias aprobados. Wheel T19 SHA-256 `a605d7524611be4e72b7ebca66c6017d842a4191cd0a8642240d31b63abe821d`; código ejecutado SHA-256 `3875bfbd83f9db150eb66569e7147ce6583ff991514ef33a91554e98682f420c`. Las pruebas se ejecutaron antes de publicar y sus recibos locales se conservaron; esta publicación no repite entrenamiento ni evaluación del holdout.

El PDF [Informe_Proyecto_MLOps_NYC_Taxi.pdf](../Informe_Proyecto_MLOps_NYC_Taxi.pdf) es una fotografía académica anterior a la evaluación independiente y a T18/T19: describe LightGBM solo en validation. Se conserva como documento de avance, sin presentar sus pendientes históricos como el estado actual. El estado vigente está en `plan.md` y los informes enlazados arriba.

La publicación contiene código y evidencias públicas, no una copia de la instancia local de MLflow. Los pesos, SQLite, artefactos, aprobaciones aplicadas y recibos JSON permanecen locales conforme a las exclusiones del proyecto. El contrato versionado de champion expresa la aprobación y sus hashes; reconstruir el entorno requiere los artefactos y el linaje correspondientes. T20–T38, API, Docker/Compose, CI y monitoreo siguen pendientes.

## Cuarta entrega — Serving, Docker, CI y calidad T20–T28

Publicación aprobada el 2026-11-09 en `ci/t26-t28`, con PR en borrador contra
`main`, sin merge. Incluye FastAPI con champion verificado, Compose con copia
aislada del Registry, locks Linux/serving, observación operativa por ventanas
y comparación de calidad sobre evidencia congelada. No reentrena ni modifica
modelos, umbrales o excepciones. El PDF nuevo del equipo queda excluido.

Verificación previa: 601 pruebas Linux PASS, Ruff, dependencias, smoke HTTP
y build/inspección de producción; límites CI globales de 2 CPU/4 GiB probados.
T26/T27/T28 verificadas técnicamente. Código publicado en
[`f675188`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/f675188fa52d7d50fc6a61f181569975ff846ded),
[PR #1 en borrador](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/pull/1)
verde. Demostración roja `22396d9` y restauración verde `3d89195` en
`ci/t26-signal`, separada del PR. Un commit documental posterior conserva
[los resultados reales y enlaces](../reports/monitoring/t26_github_ci.md).
[Alcance aprobado](t26-publication-proposal.md) y [evidencia](t26-t28.md).
En ese checkpoint G5 y T29–T31 seguían pendientes; la ampliación siguiente documenta su cierre técnico posterior.

### Ampliación aprobada de la cuarta entrega — T29–T31

El usuario autorizó ampliar el PR #1 con T29–T31, conservando main y todos los
commits existentes. Se incorporan PSI sobre distribuciones completas de train,
replay con predicciones/etiquetas separadas y reportes mensuales versionados.
Evidently 0.7.23 requiere un renderer con pandas 2.3.3; las predicciones conservan
el runtime original. Locks y etapas CI separados, con hashes y supervisión.

Checkpoint inicial de publicación (histórico): implementación y pruebas enfocadas verificadas;
referencia completa de 41.119.495 filas congelada; replay real de julio/agosto
completado y septiembre–diciembre en ejecución. CI remoto y auditoría final
siguen pendientes; G5 no se cierra por publicar el código. Un seguimiento
documental registrará los SHA, resultados y enlaces observados.

Se registran explícitamente el intento fallido de generación de hashes y la
recuperación adicional autorizada: [incidente](t29-dependency-download-incident.md).
No se incluyen datasets, modelos ni el PDF nuevo del equipo. No hay merge.

Checkpoint de código: [`fe2b530`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/fe2b5308fc63550748eee07bea2e32e4516ac94b).
El primer CI de esta ampliación detectó un directorio de trabajo incorrecto
en la etapa Docker del renderer (`/workspace` en lugar de `/build`); no fue
un incumplimiento de calidad de datos. Se conserva la ejecución fallida
[42729494259](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/actions/runs/42729494259)
y se corrige en un commit posterior, junto con el auditor exhaustivo.

Corrección y auditor exhaustivo en
[`05e5358`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/05e5358aac72f273aba9b098549680d746525da3):
directorio Docker corregido, auditor público independiente y siete pruebas de
cuantiles mediante CDF. [CI del PR verde](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/actions/runs/42730725351):
**625 pruebas aprobadas y una omitida** en el runtime original; **17 aprobadas**
en el renderer aislado; builds e inspección de producción correctos. El fallo
anterior queda visible en el historial y no se reescribieron commits.

Cierre técnico T29–T31/G5: referencia sellada de **41.119.495 filas** y seis
meses de replay con **24.266.924 filas**, todas auditadas. PSI, predicciones,
métricas exactas, cobertura y segmentos verificados; las alertas solo solicitan
revisión. Pesos, alias champion v4, evaluaciones originales y locks históricos
conservados. [Resultados](../reports/monitoring/t29-t31_monthly_replay.md) y
[operación](t29-t31-monitoring.md). No se implementa T32.

Un seguimiento documental incorpora este cierre y sincroniza plan, spec,
intent, README, decisiones y arquitectura. La cuarta **entrega funcional**
contiene varios commits trazables: T20–T28, su evidencia CI, implementación
T29–T31, corrección/auditor y cierre documental. `main` conserva exactamente
los tres commits anteriores; el PR #1 permanece en borrador, sin merge.

## Contenido público y consulta del historial

**Integración posterior aprobada — 2026-11-09:** el usuario solicitó integrar
PR #1. Se cambió de borrador a listo y se realizó merge conservando todos
los commits: [`21a6abf`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/21a6abf69748d44cde762696dde56fb6fee83d0f).
README e historial verificados en main; rama local sincronizada y
[CI del merge aprobado](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/actions/runs/42739752670).
Las referencias anteriores a main con tres commits y PR en borrador describen
los checkpoints previos a esa autorización. T32–T34 corresponden a trabajo
local posterior, aún sin un nuevo commit/push solicitado.

Se versionan código, pruebas, fixtures sintéticas pequeñas, configuración pública, PDF de referencia/avance y reportes Markdown. Permanecen locales los 30 Parquet reales actuales y sus manifiestos generados, datasets procesados, modelos/predicciones, SQLite y artefactos MLflow, reportes JSON de ejecución, catálogos `*.local.json`, entornos, cachés y secretos. Los JSON de política/protocolo y las autorizaciones excepcionales son configuración pública; no contienen registros de viajes.

Los reportes históricos que indican «sin nuevo commit/push» describen el momento de su medición, anterior a la publicación correspondiente. Sus hashes, métricas y límites se conservan como evidencia; no son afirmaciones sobre el estado remoto posterior.

```powershell
git log --reverse --format="%h %s" main
git show --stat 164bf9e
git show --stat main
```

El [historial de main](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commits/main)
permite consultar las entregas y sus diferencias. La referencia main avanza con
las publicaciones; los SHA anteriores identifican sus checkpoints inmutables.

## Checkpoint previo a la quinta entrega — T32–T34 locales

Se implementaron triggers, cohortes nuevas y auditorías, LightGBM challenger
con escritura acotada, evaluación emparejada, registro sin alias y gate.
Nuevo ciclo 2025/Q1 2026 conocido/Q2 2026 independiente, con tres descargas
limitadas y excepciones D-04 aprobadas por separado. Fallo inicial de memoria
preservado, corrección sin elevar presupuesto ni reducir registros.

V5 se registra y el gate lo rechaza por mejora MAE 0,737317 % <2 %; v4 sigue
champion. 663 pruebas locales PASS/una omisión prevista, Ruff/pip check y
auditorías completas. [Evidencia](../reports/retraining/t34_comparison.md).
No se inventa un SHA para este trabajo no publicado ni se modifica el historial.
`main` remoto sigue en el merge 21a6abf; la rama local tiene cambios sin commit.

## Checkpoint previo a la quinta entrega — T35–T38 locales

Mecanismo operativo v2 compatible con T19, promoción/rollback con diario y API
por identidad; demo sintética MLflow/HTTP, rollback en otro proceso y caída
compensada. Workflow completo con fixtures y reanudación real sin repetir
fits/evaluaciones. Export aislado offline, runbook, guion y presentación.

V4 real se conserva, v5 rechazado. Revisión cruzada por otro integrante y defensa
oral NO VERIFICADAS; el cierre técnico separado fue aprobado por el usuario.
[Resultados y pruebas](../reports/final/completion.md). Estos cambios, junto con
T32–T34, no tienen commit/push nuevo; no se inventa un SHA ni se reescribe el historial.

Cierre técnico local 2026-11-10: 681 pruebas PASS/una omisión, Ruff/formato/pip
check PASS y export offline verificable. Timeout de arranque y repetición
conservados, sin ampliar límites. [Resumen G6](../reports/final/completion.md).
La última publicación verificada sigue siendo 21a6abf; este cierre no agrega
un commit ni afirma que los archivos remotos ya incorporen T32–T38.

## Quinta entrega — T32–T38 y presentación profesional del proyecto

Solicitada por el usuario el **2026-11-10**: «Necesito que hagas el 5to commit
y además cambies el readme principal o actualices para que se vea el trabajo
profesional de todo lo hecho», y ratificada con «Continuar ... Ya habías empezado».

- Mensaje: `Complete T32-T38 retraining lifecycle and refresh project README`.
- Padre: `21a6abf69748d44cde762696dde56fb6fee83d0f`.
- Identificación: commit que incorpora esta sección. Consultar su SHA sin
  modificar su contenido:

```powershell
git log -1 --format="%H %s" --grep="^Complete T32-T38 retraining lifecycle and refresh project README$" main
```

| Área | Contenido y evidencia |
|---|---|
| T32 | Triggers sobre evidencia congelada de PSI/desempeño; recomiendan revisión sin ejecutar entrenamiento. [Resultado](../reports/retraining/t32_trigger.md). |
| T33 | Cohortes nuevas, auditorías completas y LightGBM desde cero sobre 48.144.298 viajes elegibles de 2025; v5 registrado sin alias. Fallo inicial por memoria y corrección por bloques conservados. [Fit/registro](../reports/retraining/t33_challenger.md). |
| T34 | Comparación independiente Q2 2026, 11.603.243 filas: mejora MAE 0,737317 % <2 %; v5 rechazado y v4 intacto. Tres descargas oficiales limitadas y excepciones D-04 exactas aprobadas, sin cambiar umbrales. [Gate](../reports/retraining/t34_comparison.md). |
| T35 | Contrato operativo v2 compatible con T19; aprobación, gate, diario, API por identidad, promoción/rollback y compensación. Demo exclusivamente sintética con MLflow/FastAPI aislados. [Operación](runbook.md). |
| T36 | Workflow manual, registro de fixture sin alias y verificación/reutilización de la campaña real; sin nuevos fits ni holdout reales. No incorpora promoción automática ni workflow remoto de retraining. [Contrato](../spec.md). |
| T37 | Export aislado con manifiesto, venv limpio, wheels exactos de caché y cero descargas nuevas. Logs, JUnit, hashes y recuperación trazada. [Verificación final](../reports/final/completion.md). |
| T38 | Runbook, trazabilidad, guion ejecutable y presentación Markdown; resultados científicos separados de demos TEST_ONLY. [Material](../reports/final/presentation.md). |
| README | Portada con arquitectura Mermaid, resultados comparables, protocolos temporales, instalación, API, demos y documentación; elimina pendientes obsoletos de la página principal. |

Verificación funcional previa: **681 pruebas aprobadas y una omisión prevista**
en 682 casos distintos, Ruff/formato (146 archivos) y pip check PASS. El caso HTTP
se repitió tras un timeout inicial de 90 segundos; se conservan el FAIL y ambos
JUnit finales, sin cambiar código ni límites. La causa raíz del timeout no está
confirmada y se mantiene como riesgo de arranque local.

Las 71 fuentes del proyecto coinciden con el wheel probado
`c162da4c19391e1c65cfa63ea2b17ba1c433e3992ebc4ada73c219868785eac2`.
README e historial se renovaron después de esa verificación, sin cambiar lógica
ni dependencias. Los hashes de 30 raw y 28 archivos originales se conservaron.
Las comprobaciones de publicación verifican también referencias y contenido Git.
Los atributos Git conservan los bytes CRLF de las tres autorizaciones T34
ligadas por hash; reconocen ese fin de línea sin desactivar la revisión de
espacios sobrantes ni normalizar los documentos aprobados.

Se incorporan código, pruebas, configuración pública, ADR y reportes Markdown.
Permanecen fuera datasets reales, modelos, SQLite, recibos JSON de ejecución,
secretos, entornos, cachés y el PDF nuevo no solicitado para publicación.
**Champion v4 conservado; v5 rechazado.** G6 tiene cierre técnico; revisión
cruzada humana y defensa oral continúan NO VERIFICADAS. Los apartados previos
«sin commit/push» describen el checkpoint anterior a esta quinta entrega.
