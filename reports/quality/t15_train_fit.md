# T15 — Ajuste real de train; evaluación pendiente

Fecha: 2026-11-03, America/Costa_Rica. **AJUSTE COMPLETO / EVALUACIÓN PENDIENTE.** El usuario aprobó separar estas fases; no es cierre de T14/T15 ni aprobación de marzo rechazado. [Contrato](../../docs/t15-baseline.md), [rechazo D-04 conservado](../../docs/t14-t15-quality-blocker.md).

## Resultado observado

| Dato | Resultado |
|---|---:|
| Meses train aprobados | 12 (2024 completo) |
| Raw train | 41.169.720 |
| Elegibles DQ/features antes del corte | 41.120.056 |
| Apartadas por llegada igual/posterior al corte | 561 |
| Etiquetas usadas para el ajuste | 41.119.495 |
| Mediana global exacta, minutos (redondeada) | 12,983333 |
| MAE/RMSE validación | PENDIENTES; no calculados |

Todas las etiquetas restantes de los doce meses entraron al ordenamiento exacto SQLite. No se muestreó, no se aproximaron cuantiles ni se combinaron medianas mensuales. El float usado está en model.json; la tabla solo redondea su presentación. El corte es 2025-01-01 00:00 America/New_York (05:00 UTC), estricto para el evento final de etiqueta. No se trasladaron viajes a otras particiones. Es replay retrospectivo por evento: este corte no acredita que los archivos estuvieran publicados o descargados en ese instante.

| Mes 2024 | Raw | Elegibles DQ/features | Apartadas por corte | Usadas |
|---|---:|---:|---:|---:|
| 01 | 2.964.624 | 2.961.753 | 0 | 2.961.753 |
| 02 | 3.007.526 | 3.004.760 | 0 | 3.004.760 |
| 03 | 3.582.628 | 3.579.306 | 0 | 3.579.306 |
| 04 | 3.514.289 | 3.510.931 | 0 | 3.510.931 |
| 05 | 3.723.833 | 3.720.354 | 0 | 3.720.354 |
| 06 | 3.539.193 | 3.535.780 | 0 | 3.535.780 |
| 07 | 3.076.903 | 3.073.739 | 0 | 3.073.739 |
| 08 | 2.979.183 | 2.976.025 | 0 | 2.976.025 |
| 09 | 3.633.030 | 3.629.857 | 0 | 3.629.857 |
| 10 | 3.833.771 | 3.830.685 | 0 | 3.830.685 |
| 11 | 3.646.369 | 3.631.916 | 0 | 3.631.916 |
| 12 | 3.668.371 | 3.664.950 | 561 | 3.664.389 |

## Verificación independiente

Una segunda lectura por bloques de los doce orígenes comprobó índices/cobertura, duración UTC, máscara del corte y secuencia completa de etiquetas. El hash lógico resultante coincide con todas las etiquetas publicadas. Orden estadístico: 20.538.312 por debajo, 28.324 iguales y 20.552.859 por encima de la mediana; la observación central de orden 20.559.748 (base 1) confirma la mediana publicada.

Se volvieron a verificar marcadores, hashes, conteos, calidad y autorizaciones de las doce fuentes; tamaños/SHA-256 originales de 2024 intactos. El ajuste no abrió fuentes de 2025. Tampoco generó predicciones ni métricas de validación. Los valores desconocidos de procedencia/fecha siguen nulos: LOCAL_UNVERIFIED no se convirtió en descarga verificada.

Hash lógico de etiquetas (IEEE754 float64 little-endian): `27795a7355a844ec2faf73034592f09c5b04725cb5a16a3cfa35e70c9e3a9c17`. SHA-256 físico del Parquet: `0fd9225fb1cdc0bd0d1be5509e451c6a5f58d2babcb580f99ab097d63b74e101`. SHA-256 de model.json: `221df1e9ec3bfd737f33aa61df20eb26b4ae65df7ce4755d13d5a6310b31012c`.

## Recursos y artefactos

Tiempo observado de ajuste: 2105.16 segundos. Pico RSS: 389.90 MiB. Archivo SQLite tras indexación: 1.422.454.784 bytes; esta última cifra no incluye necesariamente todos los temporales del ordenamiento. Es una medición de este host, no un benchmark Docker.

Perfil aplicado: preflight 4 GiB RAM libre/50 GiB disco, RSS supervisado ≤2 GiB, cuatro hilos y dos horas como máximo. Supervisión cooperativa entre bloques y durante el ordenamiento SQLite; no límite duro del SO. Bases temporales, staging y locks propios quedaron limpios. No se redujeron filas ni ampliaron límites.

- Directorio local: `data/processed/baseline_fits/22b6d36bab9842368099b7bb5c050aed`.
- Archivos: model.json, train_target.parquet y fit_manifest.json publicado al final.
- Estado: `BASELINE_FIT_REAL_PENDING_VALIDATION`; fit_complete=true; evaluation_status=PENDING_VALIDATION.
- t14_complete=false, t15_complete=false, approved_for_serving=false y model_registered=false.
- Catálogo explícito local: configs/train-feature-batches.local.json (solo los doce meses train).
- Evidencia local: .cache/t15-fit/fit-result.json, audit.json, fit.log y software-verification.json.

Estos datos/modelos/JSON locales están excluidos de Git. No hay split_manifest.json ni baseline_manifest.json completo en este directorio; el CLI de baseline completo lo rechaza como entrada T14. La futura evaluación debe comprobar equivalencia de fuentes/cortes antes de reutilizar este modelo provisional.

## Pruebas y pendientes

**356 pruebas aprobadas en desarrollo y 356 desde el wheel instalado**, con checkout sin src/data, 22 imports aislados, CLI y pruebas de error. Ruff check/format y pip check correctos en ambos entornos. Wheel y módulos Python contrastados byte por byte; no se añadieron dependencias.

Wheel probado SHA-256: `7f8049cfe1b734b44588a35fcac104319be989c85cf343ad1b9261987ca7942c`. Lock: `372c8949a3c4fbc62c3f334d8ddf565ff213e56a80deca8d00a007cde6673529`. Los hashes de fuentes están en audit.json; los cambios permanecen locales, sin nuevo commit/push.

Siguen pendientes: resolver marzo 2025 bajo la política conservada, completar T14 y evaluar sobre enero–marzo de 2025. No se sustituyó validación por enero–febrero, no se consumieron test/replay ni se entrenaron SGD/MLP, MLflow, serving o promoción. El ajuste provisional no cierra T15 ni los gates generales.

## Evaluación posterior del ajuste congelado

El artefacto de ajuste descrito aquí sigue intacto. Su evaluación se completó después de autorizar la excepción puntual de marzo. [Resultado técnico de T15](t15_baseline_validation.md). El estado pendiente anterior describe exclusivamente la publicación original de fit.
