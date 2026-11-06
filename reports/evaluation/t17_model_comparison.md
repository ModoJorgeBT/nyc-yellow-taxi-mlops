# T17 — Comparación temporal auditada

Fecha: 2026-11-05, America/Costa_Rica. **CIERRE TÉCNICO PASS de la primera comparación; revisión humana independiente.**

**SGD Huber fue elegido por MAE de validación antes de abrir test.** No hubo ajuste ni nueva selección después de ver test. Baseline y ambos candidatos permanecen congelados; no existe promoción ni registro MLflow.

[Preparación T14](../quality/t14_completion.md), [entrenamiento T16](../quality/t16_training.md), [protocolo aprobado](../../docs/t16-t17-execution-proposal.md) y [verificación del software](../../docs/t16-t17-validation.md).

## Resultados globales

Todas las métricas están expresadas en minutos. Se evaluaron todas las filas elegibles: **11.163.264 de enero–marzo de 2025** y **12.712.466 de abril–junio de 2025**. MAE/RMSE ponderados por registro; MedAE y P90 exactos con interpolación lineal, sin promediar percentiles por bloque.

| Periodo | Modelo | MAE | RMSE | MedAE | P90 absoluto |
|---|---|---:|---:|---:|---:|
| validation | Mediana T15 | 7.741890 | 11.912962 | 5.583333 | 15.250000 |
| validation | SGD Huber | 6.876910 | 10.559177 | 4.515139 | 15.485330 |
| validation | MLP16 | 11.856108 | 15.946811 | 9.250000 | 24.458932 |
| test | Mediana T15 | 9.032999 | 14.286623 | 5.983333 | 19.766667 |
| test | SGD Huber | 7.965068 | 12.160194 | 5.249660 | 18.014991 |
| test | MLP16 | 10.717683 | 15.503207 | 7.324315 | 23.985737 |

SGD reduce el MAE respecto al baseline un **11,17 % en validación** y **11,82 % en test**. Esto no garantiza mejora en cada segmento: el P90 de validación empeora de 15,250 a 15,485 minutos. MLP es peor que el baseline bajo el perfil aprobado de una pasada; no se reentrena ni se cambian parámetros para ocultar ese resultado.

## Recortes y alcance

Las predicciones se acotan a [1/60, 180] minutos; se conservan y cuentan los recortes. Un resultado no finito abortaría la ejecución.

| Periodo | Modelo | Predicciones recortadas | Porcentaje |
|---|---|---:|---:|
| validation | Mediana T15 | 0 | 0.000000 % |
| validation | SGD Huber | 6,279 | 0.056247 % |
| validation | MLP16 | 3,823,878 | 34.254121 % |
| test | Mediana T15 | 0 | 0.000000 % |
| test | SGD Huber | 1,699 | 0.013365 % |
| test | MLP16 | 817,714 | 6.432379 % |

La elevada frecuencia de recortes de MLP es una limitación del candidato y debe revisarse en un experimento posterior. Estas métricas describen viajes elegibles después de calidad y cortes de disponibilidad de etiqueta, no todos los viajes raw. Los 24 archivos conservan procedencia LOCAL_UNVERIFIED, con fuente/fecha de descarga desconocidas. Diez lotes tienen aceptación humana excepcional; sus FAIL y exclusiones permanecen. No se incorporó destino como predictor.

## Cobertura y exclusiones de los meses evaluados

| Mes | Periodo | Raw | Excluidos DQ | Excluidos por corte | Evaluados | Excepción humana |
|---|---|---:|---:|---:|---:|---|
| 2025-01 | validation | 3,475,226 | 3,450 | 0 | 3,471,776 | No |
| 2025-02 | validation | 3,577,543 | 6,496 | 0 | 3,571,047 | No |
| 2025-03 | validation | 4,145,257 | 23,886 | 930 | 4,120,441 | Sí |
| 2025-04 | test | 3,970,553 | 36,369 | 0 | 3,934,184 | Sí |
| 2025-05 | test | 4,591,845 | 65,826 | 0 | 4,526,019 | Sí |
| 2025-06 | test | 4,322,960 | 69,983 | 714 | 4,252,263 | Sí |

Replay julio–diciembre fue preparado/auditado en T14, pero no se utilizó para ajustar candidatos, elegir ni calcular métricas predictivas T17.

## Auditoría independiente

Se contrastaron las 23.875.730 etiquetas y las seis salidas completas de predicción, índices continuos, hashes de archivos y conteos. Se reconstruyeron las predicciones directamente con pesos SGD y capas ReLU de MLP, sin usar la función de predicción del evaluador. Diferencias máximas por disposición float32/BLAS: SGD 0,00000763 y MLP 0,00001526 minutos. Se recomputaron errores y todos los segmentos; los percentiles se contrastaron sobre arrays completos mediante numpy.quantile(method="linear").

El catálogo de veinte rutas se verificó solo con frecuencias de validación, soporte mínimo 1.000 y desempate por IDs. Destino se leyó por identidad de fila únicamente para segmentación posterior. Cada agrupación por mes, franja y rutas más «otras» cubre todas las filas; las agrupaciones se superponen entre sí y no deben sumarse juntas.

Se verificaron los 24 raw intactos, modelos T15 intactos, código/lock congelados y selección inmutable. La selección fue observada independientemente mientras test aún estaba en ejecución. El consumo máximo de la evaluación fue de 576.29 MiB RSS y 808.85 s; la auditoría adicional consumió 916.00 MiB y 175.68 s.

## Identidades y reproducción

- Split: `e02156de2ac5477bafc4657774e31673`.
- Entrenamiento: `faf8ab304ffb447f8bff8c1372715352`.
- Evaluación: `0834219fa03e4eae965c67db282e0bb7`.
- Manifest de evaluación SHA-256: `e1df7547dbb9cd7d766dd12a462b61c6c2753a71566e5cda796cd45e6ac3f943`.
- Selección previa al test SHA-256: `e863c7c74c93a6a7478bd0b831b8b29848e42c7fc16bff04762a35c3df94c61d`.
- Auditoría independiente SHA-256: `75f9c0aab1e8edf2267e7f3975e7cda957cde3466c9780cf41fa06e6cbffdc2e`.
- Wheel SHA-256: `20287d5a6916f25a7ec02e2b79023ea1de0432102b003c885b5af4b78a379715`.
- Lock SHA-256: `372c8949a3c4fbc62c3f334d8ddf565ff213e56a80deca8d00a007cde6673529`.

Artefactos locales: `data/processed/evaluations/0834219fa03e4eae965c67db282e0bb7` y `.cache/t17/audit.json`; no se versionan datos/modelos/reportes JSON generados. Los CLI y requisitos de reproducción están en [la guía de verificación](../../docs/t16-t17-validation.md). No repetir la evaluación para ajustar modelos con test.

## Extensión posterior

El usuario solicitó y aprobó incorporar LightGBM después de terminar esta comparación, con evaluación **solo en validación**. Su nueva evaluación final independiente queda pendiente. La [extensión aprobada](../../docs/t16-lightgbm-extension-proposal.md) no sustituye estos artefactos ni convierte el test ya observado en un test nuevo.

## Resultados completos por segmento

Franjas en hora local de Nueva York: band_0 00:00–05:59, band_1 06:00–11:59, band_2 12:00–17:59 y band_3 18:00–23:59. route_O_D usa zonas observadas para análisis posterior, sin disponibilidad de destino supuesta para inferencia.

### validation

| Segmento | Modelo | Filas | MAE | RMSE | MedAE | P90 absoluto |
|---|---|---:|---:|---:|---:|---:|
| band_0 | Mediana T15 | 959,967 | 6.507327 | 8.899683 | 5.350000 | 12.450000 |
| band_0 | SGD Huber | 959,967 | 6.250829 | 8.955561 | 4.493035 | 13.628407 |
| band_0 | MLP16 | 959,967 | 10.675940 | 13.457707 | 8.933333 | 21.000000 |
| band_1 | Mediana T15 | 2,323,884 | 8.246787 | 12.905487 | 5.850000 | 16.650000 |
| band_1 | SGD Huber | 2,323,884 | 7.314527 | 11.289011 | 4.682842 | 16.877241 |
| band_1 | MLP16 | 2,323,884 | 9.240122 | 14.343799 | 5.646647 | 21.514299 |
| band_2 | Mediana T15 | 3,811,570 | 8.806121 | 14.021275 | 5.866667 | 18.816667 |
| band_2 | SGD Huber | 3,811,570 | 7.684885 | 12.188174 | 4.716616 | 17.644225 |
| band_2 | MLP16 | 3,811,570 | 12.111912 | 17.244905 | 8.617978 | 26.662594 |
| band_3 | Mediana T15 | 4,067,843 | 6.747610 | 9.561036 | 5.266667 | 12.883333 |
| band_3 | SGD Huber | 4,067,843 | 6.017583 | 8.663200 | 4.269601 | 13.257637 |
| band_3 | MLP16 | 4,067,843 | 13.389392 | 16.091635 | 11.500000 | 24.778653 |
| month_2025_01 | Mediana T15 | 3,471,776 | 7.558051 | 11.438895 | 5.600000 | 14.533333 |
| month_2025_01 | SGD Huber | 3,471,776 | 6.636137 | 10.195092 | 4.320767 | 15.040350 |
| month_2025_01 | MLP16 | 3,471,776 | 12.203542 | 16.156310 | 9.633333 | 24.771848 |
| month_2025_02 | Mediana T15 | 3,571,047 | 7.588563 | 11.596233 | 5.533333 | 14.850000 |
| month_2025_02 | SGD Huber | 3,571,047 | 6.816417 | 10.415198 | 4.504845 | 15.329032 |
| month_2025_02 | MLP16 | 3,571,047 | 11.884250 | 15.878272 | 9.368484 | 24.416667 |
| month_2025_03 | Mediana T15 | 4,120,441 | 8.029670 | 12.557845 | 5.616667 | 16.233333 |
| month_2025_03 | SGD Huber | 4,120,441 | 7.132206 | 10.976347 | 4.692542 | 15.998930 |
| month_2025_03 | MLP16 | 4,120,441 | 11.538981 | 15.827962 | 8.795026 | 24.222735 |
| route_132_132 | Mediana T15 | 22,166 | 11.510348 | 13.795888 | 12.666667 | 12.900000 |
| route_132_132 | SGD Huber | 22,166 | 36.111913 | 36.826535 | 38.718439 | 40.161874 |
| route_132_132 | MLP16 | 22,166 | 11.916086 | 14.931790 | 11.581511 | 19.592326 |
| route_141_236 | Mediana T15 | 25,012 | 5.851933 | 6.494681 | 6.083333 | 9.183333 |
| route_141_236 | SGD Huber | 25,012 | 2.674524 | 3.583736 | 2.255422 | 5.185468 |
| route_141_236 | MLP16 | 25,012 | 3.675770 | 4.760121 | 3.093422 | 7.405428 |
| route_142_239 | Mediana T15 | 26,721 | 7.005622 | 7.411782 | 7.233333 | 9.850000 |
| route_142_239 | SGD Huber | 26,721 | 3.223282 | 3.841160 | 3.118089 | 5.793840 |
| route_142_239 | MLP16 | 26,721 | 4.699145 | 5.589960 | 4.471590 | 8.400000 |
| route_161_161 | Mediana T15 | 21,666 | 7.988242 | 8.943533 | 8.116667 | 12.616667 |
| route_161_161 | SGD Huber | 21,666 | 6.324713 | 7.488402 | 6.202631 | 10.514550 |
| route_161_161 | MLP16 | 21,666 | 4.752239 | 6.769525 | 3.886703 | 9.198573 |
| route_161_236 | Mediana T15 | 28,625 | 3.729420 | 4.889530 | 3.100000 | 7.300000 |
| route_161_236 | SGD Huber | 28,625 | 3.835110 | 5.287496 | 2.846156 | 8.313678 |
| route_161_236 | MLP16 | 28,625 | 10.813538 | 11.850527 | 10.533333 | 16.739819 |
| route_161_237 | Mediana T15 | 33,387 | 4.895908 | 5.684148 | 4.866667 | 8.500000 |
| route_161_237 | SGD Huber | 33,387 | 3.683221 | 4.546576 | 3.378815 | 6.855056 |
| route_161_237 | MLP16 | 33,387 | 6.798411 | 8.025097 | 6.444223 | 12.083333 |
| route_186_230 | Mediana T15 | 24,870 | 4.618336 | 5.959014 | 4.000000 | 8.750000 |
| route_186_230 | SGD Huber | 24,870 | 4.672645 | 6.000172 | 4.059478 | 8.911017 |
| route_186_230 | MLP16 | 24,870 | 8.871472 | 10.590597 | 8.111217 | 16.313807 |
| route_236_141 | Mediana T15 | 23,455 | 5.067822 | 5.770164 | 5.150000 | 8.533333 |
| route_236_141 | SGD Huber | 23,455 | 2.706095 | 3.680056 | 2.161239 | 5.504657 |
| route_236_141 | MLP16 | 23,455 | 5.512476 | 6.649185 | 5.138535 | 10.246445 |
| route_236_161 | Mediana T15 | 23,625 | 4.264257 | 5.576780 | 3.466667 | 8.600000 |
| route_236_161 | SGD Huber | 23,625 | 6.563650 | 8.267396 | 5.582525 | 13.390382 |
| route_236_161 | MLP16 | 23,625 | 9.800483 | 11.303857 | 9.088540 | 17.298201 |
| route_236_236 | Mediana T15 | 50,911 | 8.690811 | 9.081788 | 8.933333 | 11.150000 |
| route_236_236 | SGD Huber | 50,911 | 3.863144 | 4.766260 | 3.710860 | 6.244719 |
| route_236_236 | MLP16 | 50,911 | 2.933888 | 4.423608 | 2.350000 | 5.417930 |
| route_236_237 | Mediana T15 | 62,100 | 5.654407 | 6.309706 | 5.833333 | 9.116667 |
| route_236_237 | SGD Huber | 62,100 | 2.601207 | 3.480203 | 2.156801 | 5.109550 |
| route_236_237 | MLP16 | 62,100 | 4.492316 | 5.694404 | 3.829730 | 9.036672 |
| route_236_239 | Mediana T15 | 21,717 | 4.765487 | 5.478472 | 4.733333 | 8.100000 |
| route_236_239 | SGD Huber | 21,717 | 2.598662 | 3.724383 | 1.970498 | 5.284994 |
| route_236_239 | MLP16 | 21,717 | 5.936998 | 7.102049 | 5.657871 | 10.638381 |
| route_237_141 | Mediana T15 | 22,645 | 7.008634 | 7.479532 | 7.316667 | 9.866667 |
| route_237_141 | SGD Huber | 22,645 | 2.679711 | 3.498885 | 2.390923 | 4.953170 |
| route_237_141 | MLP16 | 22,645 | 3.828524 | 4.929689 | 3.350000 | 7.333333 |
| route_237_161 | Mediana T15 | 29,630 | 4.771171 | 5.639202 | 4.616667 | 8.600000 |
| route_237_161 | SGD Huber | 29,630 | 3.580481 | 4.968108 | 2.645937 | 7.864593 |
| route_237_161 | MLP16 | 29,630 | 5.939466 | 7.444441 | 5.156752 | 11.733333 |
| route_237_162 | Mediana T15 | 23,964 | 5.809199 | 6.593303 | 5.933333 | 9.533333 |
| route_237_162 | SGD Huber | 23,964 | 3.097263 | 4.310972 | 2.472941 | 6.003174 |
| route_237_162 | MLP16 | 23,964 | 4.863398 | 6.365438 | 3.967441 | 10.083752 |
| route_237_236 | Mediana T15 | 71,372 | 6.234158 | 6.831252 | 6.533333 | 9.566667 |
| route_237_236 | SGD Huber | 71,372 | 2.652285 | 3.433131 | 2.311082 | 5.067103 |
| route_237_236 | MLP16 | 71,372 | 4.141577 | 5.218703 | 3.629326 | 8.133333 |
| route_237_237 | Mediana T15 | 49,425 | 8.226528 | 8.742724 | 8.433333 | 11.083333 |
| route_237_237 | SGD Huber | 49,425 | 3.534192 | 4.656516 | 3.255232 | 6.134333 |
| route_237_237 | MLP16 | 49,425 | 3.142871 | 4.714425 | 2.490728 | 5.983333 |
| route_238_239 | Mediana T15 | 23,055 | 7.914316 | 8.211699 | 8.133333 | 10.350000 |
| route_238_239 | SGD Huber | 23,055 | 3.233692 | 3.835211 | 3.169061 | 5.547848 |
| route_238_239 | MLP16 | 23,055 | 3.080131 | 3.893273 | 2.762418 | 5.783333 |
| route_239_142 | Mediana T15 | 25,950 | 7.156604 | 7.549754 | 7.350000 | 10.066667 |
| route_239_142 | SGD Huber | 25,950 | 2.905061 | 3.525764 | 2.701495 | 5.453165 |
| route_239_142 | MLP16 | 25,950 | 4.031369 | 4.982778 | 3.581239 | 7.814782 |
| route_239_238 | Mediana T15 | 27,789 | 7.919049 | 8.222161 | 8.166667 | 10.316667 |
| route_239_238 | SGD Huber | 27,789 | 3.380822 | 3.973248 | 3.373589 | 5.683840 |
| route_239_238 | MLP16 | 27,789 | 3.600731 | 4.475037 | 3.333333 | 6.583333 |
| route_other | Mediana T15 | 10,525,179 | 7.817647 | 12.131573 | 5.500000 | 15.916667 |
| route_other | SGD Huber | 10,525,179 | 7.016246 | 10.685103 | 4.657621 | 15.775399 |
| route_other | MLP16 | 10,525,179 | 12.255105 | 16.329638 | 9.685763 | 24.994862 |

### test

| Segmento | Modelo | Filas | MAE | RMSE | MedAE | P90 absoluto |
|---|---|---:|---:|---:|---:|---:|
| band_0 | Mediana T15 | 1,178,498 | 6.927491 | 9.598016 | 5.483333 | 13.433333 |
| band_0 | SGD Huber | 1,178,498 | 6.823098 | 9.543405 | 5.111927 | 14.487889 |
| band_0 | MLP16 | 1,178,498 | 10.222923 | 13.266227 | 8.281682 | 21.033333 |
| band_1 | Mediana T15 | 2,677,051 | 9.180810 | 14.487341 | 6.083333 | 20.216667 |
| band_1 | SGD Huber | 2,677,051 | 8.088408 | 12.186788 | 5.346790 | 18.611564 |
| band_1 | MLP16 | 2,677,051 | 9.130966 | 14.182588 | 5.525369 | 21.419904 |
| band_2 | Mediana T15 | 4,409,398 | 10.839605 | 17.540810 | 6.483333 | 25.783333 |
| band_2 | SGD Huber | 4,409,398 | 9.367854 | 14.691974 | 5.669709 | 21.964907 |
| band_2 | MLP16 | 4,409,398 | 11.031620 | 17.239045 | 6.335971 | 26.831111 |
| band_3 | Mediana T15 | 4,447,519 | 7.710822 | 11.296921 | 5.600000 | 16.250000 |
| band_3 | SGD Huber | 4,447,519 | 6.802663 | 9.753391 | 4.886439 | 14.901899 |
| band_3 | MLP16 | 4,447,519 | 11.492615 | 14.988392 | 9.278740 | 23.966667 |
| month_2025_04 | Mediana T15 | 3,934,184 | 8.480977 | 13.292311 | 5.800000 | 17.866667 |
| month_2025_04 | SGD Huber | 3,934,184 | 7.500604 | 11.444515 | 4.951776 | 16.921256 |
| month_2025_04 | MLP16 | 3,934,184 | 10.952090 | 15.463971 | 7.861240 | 23.983333 |
| month_2025_05 | Mediana T15 | 4,526,019 | 9.424459 | 15.010259 | 6.083333 | 21.050000 |
| month_2025_05 | SGD Huber | 4,526,019 | 8.354282 | 12.812300 | 5.397549 | 19.148429 |
| month_2025_05 | MLP16 | 4,526,019 | 11.274285 | 16.310929 | 7.715682 | 25.221006 |
| month_2025_06 | Mediana T15 | 4,252,263 | 9.127067 | 14.384482 | 6.016667 | 20.066667 |
| month_2025_06 | SGD Huber | 4,252,263 | 7.980518 | 12.089952 | 5.382000 | 17.813145 |
| month_2025_06 | MLP16 | 4,252,263 | 9.908376 | 14.632915 | 6.493597 | 22.557758 |
| route_132_132 | Mediana T15 | 29,105 | 11.631060 | 13.988884 | 12.733333 | 12.916667 |
| route_132_132 | SGD Huber | 29,105 | 37.563477 | 38.297971 | 40.212898 | 41.583740 |
| route_132_132 | MLP16 | 29,105 | 19.209238 | 21.247845 | 19.773492 | 27.968688 |
| route_141_236 | Mediana T15 | 24,504 | 5.652418 | 6.331531 | 5.866667 | 9.133333 |
| route_141_236 | SGD Huber | 24,504 | 3.270073 | 4.071397 | 2.978726 | 6.035088 |
| route_141_236 | MLP16 | 24,504 | 2.938065 | 3.918971 | 2.405004 | 5.890359 |
| route_142_239 | Mediana T15 | 26,893 | 6.872326 | 7.299252 | 7.116667 | 9.733333 |
| route_142_239 | SGD Huber | 26,893 | 4.237445 | 4.828691 | 4.285757 | 7.007578 |
| route_142_239 | MLP16 | 26,893 | 3.331537 | 4.212495 | 2.935758 | 6.482133 |
| route_161_161 | Mediana T15 | 23,838 | 7.788499 | 8.990991 | 7.850000 | 12.733333 |
| route_161_161 | SGD Huber | 23,838 | 7.309122 | 8.588809 | 7.248515 | 12.010878 |
| route_161_161 | MLP16 | 23,838 | 5.155470 | 7.025177 | 4.320720 | 10.007974 |
| route_161_236 | Mediana T15 | 31,299 | 4.472980 | 6.065072 | 3.466667 | 9.400000 |
| route_161_236 | SGD Huber | 31,299 | 4.520715 | 6.202241 | 3.379090 | 9.910166 |
| route_161_236 | MLP16 | 31,299 | 8.080608 | 9.612879 | 7.700000 | 14.647230 |
| route_161_237 | Mediana T15 | 38,764 | 4.739679 | 5.714581 | 4.500000 | 8.516667 |
| route_161_237 | SGD Huber | 38,764 | 4.393050 | 5.405911 | 4.051801 | 8.066452 |
| route_161_237 | MLP16 | 38,764 | 4.835958 | 6.207722 | 4.086354 | 9.631887 |
| route_186_230 | Mediana T15 | 23,569 | 5.572175 | 7.464482 | 4.483333 | 10.816667 |
| route_186_230 | SGD Huber | 23,569 | 5.760691 | 7.413716 | 4.936333 | 10.858178 |
| route_186_230 | MLP16 | 23,569 | 6.535399 | 8.738758 | 4.998194 | 14.120340 |
| route_236_141 | Mediana T15 | 23,044 | 4.969045 | 5.680703 | 5.000000 | 8.466667 |
| route_236_141 | SGD Huber | 23,044 | 2.902241 | 3.776806 | 2.462419 | 5.633725 |
| route_236_141 | MLP16 | 23,044 | 3.461989 | 4.628843 | 2.691954 | 7.416162 |
| route_236_161 | Mediana T15 | 26,963 | 4.701206 | 6.280711 | 3.733333 | 9.666667 |
| route_236_161 | SGD Huber | 26,963 | 6.131305 | 8.072323 | 4.765482 | 13.229818 |
| route_236_161 | MLP16 | 26,963 | 8.083856 | 9.847428 | 7.207530 | 15.480187 |
| route_236_236 | Mediana T15 | 51,512 | 8.660866 | 9.085224 | 8.900000 | 11.233333 |
| route_236_236 | SGD Huber | 51,512 | 5.059035 | 5.806706 | 5.025593 | 7.662873 |
| route_236_236 | MLP16 | 51,512 | 3.067587 | 4.381437 | 2.581275 | 5.679440 |
| route_236_237 | Mediana T15 | 68,026 | 5.528064 | 6.221432 | 5.683333 | 9.066667 |
| route_236_237 | SGD Huber | 68,026 | 3.063114 | 3.892171 | 2.704162 | 5.840074 |
| route_236_237 | MLP16 | 68,026 | 2.986834 | 4.096573 | 2.290699 | 6.332168 |
| route_236_239 | Mediana T15 | 22,007 | 4.573274 | 5.454481 | 4.450000 | 8.016667 |
| route_236_239 | SGD Huber | 22,007 | 2.876230 | 4.104871 | 2.272584 | 5.655290 |
| route_236_239 | MLP16 | 22,007 | 4.107098 | 5.499054 | 3.331724 | 8.408851 |
| route_237_141 | Mediana T15 | 23,179 | 6.761907 | 7.356229 | 7.083333 | 9.816667 |
| route_237_141 | SGD Huber | 23,179 | 3.528395 | 4.377299 | 3.390321 | 6.124368 |
| route_237_141 | MLP16 | 23,179 | 2.769751 | 3.951710 | 2.219832 | 5.529905 |
| route_237_161 | Mediana T15 | 35,840 | 4.860652 | 5.796555 | 4.633333 | 8.766667 |
| route_237_161 | SGD Huber | 35,840 | 3.685147 | 5.042960 | 2.886295 | 7.436960 |
| route_237_161 | MLP16 | 35,840 | 4.296393 | 5.901909 | 3.166603 | 9.431332 |
| route_237_162 | Mediana T15 | 27,917 | 5.609826 | 6.486209 | 5.650000 | 9.483333 |
| route_237_162 | SGD Huber | 27,917 | 3.596357 | 4.781564 | 3.084432 | 6.762191 |
| route_237_162 | MLP16 | 27,917 | 3.711848 | 5.219934 | 2.779302 | 8.052542 |
| route_237_236 | Mediana T15 | 79,848 | 5.993860 | 6.668889 | 6.250000 | 9.483333 |
| route_237_236 | SGD Huber | 79,848 | 3.297671 | 4.111361 | 3.024659 | 6.053672 |
| route_237_236 | MLP16 | 79,848 | 2.965820 | 4.075204 | 2.317521 | 6.135798 |
| route_237_237 | Mediana T15 | 56,314 | 7.972787 | 8.615416 | 8.266667 | 11.066667 |
| route_237_237 | SGD Huber | 56,314 | 4.541636 | 5.579509 | 4.419596 | 7.476213 |
| route_237_237 | MLP16 | 56,314 | 3.090616 | 4.600188 | 2.518691 | 5.842837 |
| route_238_239 | Mediana T15 | 22,383 | 7.871714 | 8.156526 | 8.100000 | 10.333333 |
| route_238_239 | SGD Huber | 22,383 | 4.458996 | 4.914772 | 4.547562 | 6.922541 |
| route_238_239 | MLP16 | 22,383 | 3.404335 | 4.078947 | 3.188820 | 6.191049 |
| route_239_142 | Mediana T15 | 25,937 | 6.997047 | 7.435180 | 7.166667 | 9.933333 |
| route_239_142 | SGD Huber | 25,937 | 3.896400 | 4.538100 | 3.835620 | 6.697926 |
| route_239_142 | MLP16 | 25,937 | 2.946024 | 3.817934 | 2.508354 | 5.793487 |
| route_239_238 | Mediana T15 | 25,577 | 7.866798 | 8.180941 | 8.133333 | 10.316667 |
| route_239_238 | SGD Huber | 25,577 | 4.612436 | 5.107838 | 4.724220 | 7.054130 |
| route_239_238 | MLP16 | 25,577 | 2.982449 | 3.772065 | 2.691692 | 5.580437 |
| route_other | Mediana T15 | 12,025,947 | 9.179403 | 14.577617 | 5.933333 | 20.500000 |
| route_other | SGD Huber | 12,025,947 | 8.101637 | 12.297346 | 5.376403 | 18.309566 |
| route_other | MLP16 | 12,025,947 | 11.067679 | 15.852575 | 7.722826 | 24.495446 |
