# Historial de entregas en Git

Repositorio: [ModoJorgeBT/nyc-yellow-taxi-mlops](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops), rama `main`. El usuario autorizó cada publicación, incluida «Favor subir el tercer commit a github». Cada entrega conserva el estado y las aprobaciones de su momento; publicar no autoriza tareas, lotes ni promociones futuras.

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
- Identificación: es el commit que incorpora esta sección; su hash definitivo se consulta en Git. No se escribe dentro de su propio contenido porque lo modificaría.

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
G5 y T29–T31 siguen pendientes.

### Ampliación aprobada de la cuarta entrega — T29–T31

El usuario autorizó ampliar el PR #1 con T29–T31, conservando main y todos los
commits existentes. Se incorporan PSI sobre distribuciones completas de train,
replay con predicciones/etiquetas separadas y reportes mensuales versionados.
Evidently 0.7.23 requiere un renderer con pandas 2.3.3; las predicciones conservan
el runtime original. Locks y etapas CI separados, con hashes y supervisión.

Estado inicial de publicación: implementación y pruebas enfocadas verificadas;
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

## Contenido público y consulta del historial

Se versionan código, pruebas, fixtures sintéticas pequeñas, configuración pública, PDF de referencia/avance y reportes Markdown. Permanecen locales los 27 Parquet reales actuales y sus manifiestos generados, datasets procesados, modelos/predicciones, SQLite y artefactos MLflow, reportes JSON de ejecución, catálogos `*.local.json`, entornos, cachés y secretos. Los JSON de política/protocolo y las autorizaciones excepcionales son configuración pública; no contienen registros de viajes.

Los reportes históricos que indican «sin nuevo commit/push» describen el momento de su medición, anterior a la publicación correspondiente. Sus hashes, métricas y límites se conservan como evidencia; no son afirmaciones sobre el estado remoto posterior.

```powershell
git log --reverse --format="%h %s" main
git show --stat 164bf9e
git show --stat main
```

El [historial de main](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commits/main) permite consultar hashes y diferencias de las tres entregas. En esta publicación, `main` identifica el tercer commit; futuras entregas pueden avanzar esa referencia.
