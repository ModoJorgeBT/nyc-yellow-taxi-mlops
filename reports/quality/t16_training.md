# T16 — Dos candidatos incrementales sobre todo train

Fecha: 2026-11-05, America/Costa_Rica. **CIERRE TÉCNICO PASS; revisión humana independiente.** [Protocolo aprobado](../../docs/t16-t17-execution-proposal.md) y [perfil de recursos 8/4](../../docs/d02-t16-resource-review.md).

Entrenamiento `faf8ab304ffb447f8bff8c1372715352` sobre la partición train T14 auditada; no se abrieron validation, test ni replay durante fit. Todos los registros elegibles anteriores al corte: **41.119.495**, sin submuestreo. Una pasada por candidato, bloques de 4.096 y semilla 42.

| Candidato | Filas train | Bloques | Segundos incluyendo preprocesamiento compartido | Pico RSS MiB |
|---|---:|---:|---:|---:|
| sgd | 41,119,495 | 10,039 | 508.80 | 1038.51 |
| mlp | 41,119,495 | 10,039 | 538.52 | 1041.14 |

Preprocesamiento compartido: 322.38 s. Vocabulario observado exhaustivamente en las 41.119.495 filas: **263 zonas**, 268 columnas codificadas. El OHE se ajustó con un representante real por categoría tras observar todo train; no usa frecuencias ni etiquetas. StandardScaler(with_mean=False) se ajustó por bloques sobre todas las filas train y se congeló antes de validación. Los dos modelos incluyen ese preprocesador en un Pipeline serializable.

SGD Huber y MLP16 conservan los parámetros aprobados en [candidates.yaml](../../configs/candidates.yaml). La salida está acotada a [1/60,180] minutos; un no finito provoca fallo. El conteo completo de recortes corresponde a la evaluación T17, no a extrapolar el pequeño probe de auditoría.

## Verificación e integridad

Se comprobaron hashes de modelos/preprocesador, contadores internos t_ y rows_fitted_, 41.119.495 observaciones del escalador, vocabulario contra un barrido independiente de todas las zonas de train y parámetros exactos. Un probe real de 8.192 filas verificó igualdad entre transformación por tablas y Pipeline de inferencia, predicciones finitas y positivas; no se presenta como métrica de precisión. Los modelos T15 permanecen intactos.

Ambos candidatos consumieron etiquetas con SHA-256 lógico float64 little-endian `27795a7355a844ec2faf73034592f09c5b04725cb5a16a3cfa35e70c9e3a9c17`, igual a T14/T15. No hubo fit de preprocesador con 2025 ni reajustes posteriores.

- Manifest de entrenamiento SHA-256: `a610e5bf9ee96e773abe9cced6717ff61c6d5711cd034dca26c15bb40d67f308`.
- SGD SHA-256: `bfe284f297e7eb8d67261242ab1d4d35dc9639d181760dc923da128e52082541`.
- MLP SHA-256: `518a7e34ac0ff5c44d93ed6b767457daf8b3e604a51d080a0d2ad4471b9e53c8`.
- Manifest split T14: `c34f4712710a10181d2c04631e9cd05f550e7110c3142fb067a1bb5566fd592a`.
- Auditoría T14: `84810a4235db7fa108a6248875edd59f782dcefd33d5271d5341c9c66e040a09`.
- Wheel de software: `20287d5a6916f25a7ec02e2b79023ea1de0432102b003c885b5af4b78a379715`; fuente: `9c16fcfa400ec1028f155e9022ba09358b5cec87c5e37740e2768d22e174a6aa`.
- Lock: `372c8949a3c4fbc62c3f334d8ddf565ff213e56a80deca8d00a007cde6673529`.

**423 pruebas de desarrollo y 423 desde wheel instalado**, 30 imports aislados, Ruff en 63 archivos y pip check de ambos entornos PASS. Fixtures incluyen varios bloques, categorías futuras, serialización, límites/timeout y fallos sin publicación. La validación del wheel se hizo sin src ni datos reales en el checkout.

## Límites y siguiente etapa

Perfil aprobado: 8 GiB RAM libre, 4 GiB RSS máximo, cuatro hilos, un candidato, 50 GiB disco y dos horas por candidato, incluyendo preproceso compartido. Los mínimos y máximos se comprobaron; supervisión cooperativa, no certificación de límite duro OS/Docker. No hubo nuevas dependencias.

Artefactos locales en `models/candidates/faf8ab304ffb447f8bff8c1372715352`; recibo independiente `.cache/t16/audit.json`. Datos/modelos/JSON generados no se versionan en Git. T17 debe comparar con el baseline congelado y reservar test hasta fijar selección. Ningún modelo está registrado, promovido ni aprobado para serving; T18/T19 siguen pendientes.

Actualización posterior: T17 ya terminó y tiene [reporte auditado](../evaluation/t17_model_comparison.md). La extensión LightGBM aprobada después se ejecutará por separado y solo se evaluará en validation; no cambia los modelos ni hashes de esta primera ejecución.
