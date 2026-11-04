# Historial de las dos entregas en Git

Repositorio: [ModoJorgeBT/nyc-yellow-taxi-mlops](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops), rama `main`. El usuario autorizó el segundo commit y su push, junto con la documentación de ambas entregas. La publicación no cierra revisiones humanas ni aprueba nuevos lotes o excepciones.

## Primer commit — Base del proyecto y pipeline hasta T11

- Commit: [`164bf9e3f08fe5ae528d36fc0a2fa06f33a74943`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/164bf9e3f08fe5ae528d36fc0a2fa06f33a74943).
- Mensaje: `Initial project: MLOps data pipeline through T11`.
- Alcance registrado por Git: 74 archivos y 5.529 líneas añadidas.

Incluyó requisitos, especificación, plan, arquitectura, decisiones y ADR; estructura modular y exclusiones de Git; entorno Python reproducible con versiones y hashes; fixtures sintéticas pequeñas y perfilado acotado de 2024. Implementó ingesta con manifiestos, hash e idempotencia, registro local explícito, contrato de esquema, motor configurable de calidad y CLI raw→validated con integración offline (T01–T11).

La verificación previa a esa publicación aprobó **162 pruebas**, además de Ruff. D-04 y la aprobación operativa de datos reales seguían pendientes. El PDF académico quedó versionado como referencia; los Parquet reales, modelos, entornos y secretos quedaron excluidos. Evidencia: [T03](t03-environment.md), [T04/T05](t04-t05-verification.md), [T06/T07](t06-t07-ingestion.md), [T08/T09](t08-t09-validation.md) y [T10/T11](t10-t11-data-pipeline.md).

## Segundo commit — Features, calidad real y baseline temporal

- Mensaje: `Add T12-T15 features and baseline; document T14 quality blockers`.
- Padre: `164bf9e3f08fe5ae528d36fc0a2fa06f33a74943`.
- Identificación: es el commit que incorpora este archivo y los cambios siguientes. Su hash se consulta en Git; escribirlo dentro del propio commit cambiaría ese mismo hash.

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

## Contenido público y consulta del historial

Se versionan código, pruebas, fixtures sintéticas pequeñas, configuración pública, referencias documentales y reportes Markdown. Permanecen locales los 24 Parquet reales y sus manifiestos generados, datasets procesados, modelos/predicciones, reportes JSON de ejecución, catálogos `*.local.json`, entornos, cachés y secretos. Los JSON de política/protocolo y la autorización excepcional son configuración pública; no contienen registros de viajes.

Los reportes históricos que indican «sin nuevo commit/push» describen el momento de su medición, anterior a esta segunda publicación. Sus hashes, métricas y límites se conservan como evidencia; no son afirmaciones sobre el estado remoto posterior.

```powershell
git log --reverse --format="%h %s" main
git show --stat 164bf9e
git show --stat main
```

El [historial de main](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commits/main) permite consultar hashes y diferencias de ambas entregas. En esta publicación, `main` identifica el segundo commit; futuras entregas pueden avanzar esa referencia.
