# LightGBM — Evaluación final independiente auditada

**CIERRE TÉCNICO PASS — 2026-11-05, America/Costa_Rica.**
Evaluación `ce0c3b7426dc43dfb76d366c22d73a31`; revisión humana de resultados pendiente.
No hay promoción ni nuevo champion. T18 requiere [D-07](../../docs/d07-mlflow-proposal.md).

## Resultado global

Todas las métricas están en minutos y se calcularon sobre las mismas
**10.937.087 filas** de enero–marzo de 2026. MedAE y P90 son exactos, con
interpolación lineal; no se estimaron mediante una muestra.

| Segmento | Modelo | Filas | MAE | RMSE | MedAE | P90 absoluto |
|---|---|---:|---:|---:|---:|---:|
| all | baseline | 10.937.087 | 9.141254 | 14.698776 | 6.000000 | 19.950000 |
| all | sgd | 10.937.087 | 8.352735 | 13.249356 | 5.117139 | 19.234904 |
| all | lightgbm | 10.937.087 | 7.742891 | 12.368333 | 5.048365 | 16.815384 |

LightGBM reduce el MAE observado un 15.297 % frente al baseline y
un 7.301 % frente a SGD. El resultado describe este trimestre
filtrado con excepciones autorizadas; no demuestra estabilidad futura ni resuelve
los gates de promoción D-05/T19. No se ajustaron modelos después de medirlo.

La mejora global no es uniforme: LightGBM tiene mayor MAE que SGD en **14 de
las 20 rutas congeladas** y mayor MAE que el baseline en 132→132 y 236→161.
En la franja [00,06), su P90 también empeora frente al baseline (13,879320
frente a 13,516667 minutos). Estos resultados quedan disponibles para la revisión
de promoción; no se definieron tolerancias retrospectivas para declararlos aceptables.

## Reserva, cobertura y calidad

El periodo y los tres modelos se congelaron antes de abrir métricas de 2026 en
el [protocolo aprobado](../../docs/lightgbm-final-evaluation-proposal.md) y su
[configuración inmutable](../../configs/lightgbm-final-evaluation.yaml).
La selección SGD de 2025 no cambia; el test abril–junio y el replay
julio–diciembre de 2025 no se reutilizaron. MLP no se evaluó en 2026.
Es una evaluación retrospectiva con un holdout reservado dentro del proyecto,
no una prueba de que el modelo estuviera desplegado ni de que los archivos
estuvieran disponibles al comienzo de 2026. Los timestamps operativos de los
recibos se conservan en UTC; la fecha del informe se expresa en Costa Rica.

| Mes | Raw | Exclusiones DQ | Elegibles antes del corte | Exclusiones por corte | Evaluados |
|---|---:|---:|---:|---:|---:|
| Enero 2026 | 3.724.889 | 46.832 | 3.678.057 | 0 | 3.678.057 |
| Febrero 2026 | 3.399.866 | 42.141 | 3.357.725 | 0 | 3.357.725 |
| Marzo 2026 | 3.952.451 | 50.332 | 3.902.119 | 814 | 3.901.305 |
| Total | 11.077.206 | 139.305 | 10.937.901 | 814 | 10.937.087 |

Recogidas `[2026-01-01 00:00, 2026-04-01 00:00)` en America/New_York;
etiquetas estrictamente anteriores a `2026-04-01T04:00:00Z`.
La auditoría contrastó todas las identidades, valores, duración UTC y calendario
con validated; no hay fit, actualización de vocabulario, escalado ni bins.
Destino interviene exclusivamente en la segmentación posterior.

Los tres meses incumplieron duración no positiva y unión de inválidos.
Las [tres excepciones exactas](../../docs/lightgbm-final-quality-exceptions-proposal.md)
fueron aprobadas antes de consumirlos: se preservaron FAIL, checks, hashes y
D-04 global; las 139.305 filas inválidas quedaron excluidas. No se eligieron
filtros después de conocer errores predictivos ni se autorizaron futuros lotes.

## Procedencia e integridad

Se descargaron únicamente tres Yellow Taxi oficiales, **190.739.682 bytes** en
total, dentro de 512 MiB por archivo/1 GiB total. Cada manifiesto registra URL y
fecha UTC reales; DOWNLOADED acredita adquisición, no ausencia de problemas DQ.

| Mes | Fuente oficial | SHA-256 raw |
|---|---|---|
| 2026-01 | [Yellow Taxi 01/2026](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-01.parquet) | `8b3933fe6f0d7b6d8826613c0dd724edc680ff7c49e2bd4c7635c05102728637` |
| 2026-02 | [Yellow Taxi 02/2026](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-02.parquet) | `5352ca800f29c40a221ed5b0c6392c451fde7fcd236a73651bd5aea74713a26c` |
| 2026-03 | [Yellow Taxi 03/2026](https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-03.parquet) | `d7af794a7ac06cbbb5afb4d1df9e86d84f2e878584de708ff2ffca4bd7d234d9` |

Los 24 raw anteriores conservan sus bytes y condición LOCAL_UNVERIFIED; el origen
registrado de estos tres archivos nuevos no subsana la procedencia histórica
del entrenamiento. Auditoría: 27 raw intactos y modelos congelados intactos.

## Meses y franjas locales

| Segmento | Modelo | Filas | MAE | RMSE | MedAE | P90 absoluto |
|---|---|---:|---:|---:|---:|---:|
| month_2026_01 | baseline | 3.678.057 | 8.948258 | 14.350182 | 5.933333 | 19.383333 |
| month_2026_01 | sgd | 3.678.057 | 8.276660 | 13.143279 | 5.020416 | 19.159035 |
| month_2026_01 | lightgbm | 3.678.057 | 7.628975 | 12.230979 | 4.959919 | 16.573196 |
| month_2026_02 | baseline | 3.357.725 | 9.288912 | 14.759278 | 6.083333 | 20.500000 |
| month_2026_02 | sgd | 3.357.725 | 8.595040 | 13.402128 | 5.317423 | 19.866052 |
| month_2026_02 | lightgbm | 3.357.725 | 7.921554 | 12.451057 | 5.195641 | 17.385583 |
| month_2026_03 | baseline | 3.901.305 | 9.196121 | 14.968864 | 5.983333 | 19.966667 |
| month_2026_03 | sgd | 3.901.305 | 8.215914 | 13.216679 | 5.045624 | 18.714676 |
| month_2026_03 | lightgbm | 3.901.305 | 7.696520 | 12.425540 | 5.010721 | 16.517658 |
| band_0 | baseline | 1.006.968 | 7.103429 | 10.453782 | 5.483333 | 13.516667 |
| band_0 | sgd | 1.006.968 | 6.982695 | 10.233269 | 4.867327 | 15.443058 |
| band_0 | lightgbm | 1.006.968 | 6.410291 | 9.549842 | 4.538010 | 13.879320 |
| band_1 | baseline | 2.390.680 | 10.282397 | 16.946640 | 6.333333 | 23.483333 |
| band_1 | sgd | 2.390.680 | 9.246985 | 14.733870 | 5.428752 | 21.829113 |
| band_1 | lightgbm | 2.390.680 | 8.570629 | 13.830410 | 5.286294 | 19.398102 |
| band_2 | baseline | 3.691.619 | 10.632037 | 17.311829 | 6.416667 | 25.316667 |
| band_2 | sgd | 3.691.619 | 9.604310 | 15.556472 | 5.519375 | 22.421367 |
| band_2 | lightgbm | 3.691.619 | 8.854836 | 14.470165 | 5.500057 | 19.608373 |
| band_3 | baseline | 3.847.820 | 7.535283 | 10.933888 | 5.583333 | 15.816667 |
| band_3 | sgd | 3.847.820 | 6.954901 | 10.223003 | 4.703765 | 15.827171 |
| band_3 | lightgbm | 3.847.820 | 6.510544 | 9.551094 | 4.668256 | 13.990700 |

Las franjas 0–3 corresponden a [00,06), [06,12), [12,18), [18,24) horas locales.
Cada familia de segmentos cubre exactamente todas las filas del trimestre.

## Rutas congeladas

Las veinte rutas se seleccionaron exclusivamente por frecuencia de validation
2025, con soporte mínimo 1.000 en aquella ventana; no se reeligieron usando
frecuencias ni errores de 2026. `route_other` completa la cobertura.

| Segmento | Modelo | Filas | MAE | RMSE | MedAE | P90 absoluto |
|---|---|---:|---:|---:|---:|---:|
| route_237_236 | baseline | 69.351 | 5.982177 | 6.678864 | 6.216667 | 9.500000 |
| route_237_236 | sgd | 69.351 | 2.935303 | 4.020457 | 2.391981 | 5.634306 |
| route_237_236 | lightgbm | 69.351 | 3.417211 | 4.291056 | 3.094929 | 6.298730 |
| route_236_237 | baseline | 59.869 | 5.400246 | 6.148419 | 5.483333 | 9.066667 |
| route_236_237 | sgd | 59.869 | 3.093852 | 4.337540 | 2.362032 | 6.327441 |
| route_236_237 | lightgbm | 59.869 | 3.328560 | 4.269282 | 2.890521 | 6.325088 |
| route_236_236 | baseline | 48.590 | 8.475682 | 8.964688 | 8.733333 | 11.150000 |
| route_236_236 | sgd | 48.590 | 3.834835 | 4.938621 | 3.582566 | 6.375398 |
| route_236_236 | lightgbm | 48.590 | 5.413277 | 6.225525 | 5.283570 | 8.212591 |
| route_237_237 | baseline | 47.063 | 7.847504 | 8.466991 | 8.166667 | 11.000000 |
| route_237_237 | sgd | 47.063 | 3.543328 | 4.732387 | 3.186610 | 6.300415 |
| route_237_237 | lightgbm | 47.063 | 4.792325 | 5.734869 | 4.610001 | 7.872514 |
| route_161_237 | baseline | 30.463 | 5.015396 | 6.099375 | 4.800000 | 8.766667 |
| route_161_237 | sgd | 30.463 | 4.076111 | 5.424799 | 3.502608 | 7.544682 |
| route_161_237 | lightgbm | 30.463 | 4.487791 | 5.596569 | 4.163438 | 7.993961 |
| route_237_161 | baseline | 27.531 | 5.050273 | 6.043656 | 4.833333 | 8.900000 |
| route_237_161 | sgd | 27.531 | 3.870876 | 5.621645 | 2.741660 | 8.710261 |
| route_237_161 | lightgbm | 27.531 | 3.640539 | 5.036366 | 2.893166 | 7.213355 |
| route_161_236 | baseline | 25.442 | 4.430238 | 6.250262 | 3.350000 | 9.181667 |
| route_161_236 | sgd | 25.442 | 4.754239 | 6.907403 | 3.209005 | 10.986812 |
| route_161_236 | lightgbm | 25.442 | 4.064696 | 5.967682 | 2.845908 | 8.969225 |
| route_239_238 | baseline | 25.657 | 7.685961 | 8.025401 | 7.983333 | 10.200000 |
| route_239_238 | sgd | 25.657 | 3.326102 | 3.922867 | 3.272927 | 5.640976 |
| route_239_238 | lightgbm | 25.657 | 4.809999 | 5.356410 | 4.811218 | 7.538413 |
| route_142_239 | baseline | 25.078 | 6.761803 | 7.245434 | 7.033333 | 9.766667 |
| route_142_239 | sgd | 25.078 | 3.193107 | 3.903562 | 3.024532 | 5.773779 |
| route_142_239 | lightgbm | 25.078 | 4.327178 | 4.989945 | 4.295592 | 7.257800 |
| route_239_142 | baseline | 24.149 | 6.876106 | 7.353244 | 7.100000 | 9.933333 |
| route_239_142 | sgd | 24.149 | 2.903974 | 3.623850 | 2.661312 | 5.427618 |
| route_239_142 | lightgbm | 24.149 | 4.167023 | 4.848387 | 4.083266 | 7.147493 |
| route_141_236 | baseline | 24.038 | 5.604987 | 6.324410 | 5.766667 | 9.083333 |
| route_141_236 | sgd | 24.038 | 3.022799 | 4.227494 | 2.345268 | 5.970972 |
| route_141_236 | lightgbm | 24.038 | 3.456791 | 4.416728 | 2.999515 | 6.676230 |
| route_186_230 | baseline | 20.661 | 5.185443 | 6.879863 | 4.283333 | 10.000000 |
| route_186_230 | sgd | 20.661 | 5.227723 | 6.909965 | 4.322747 | 10.068303 |
| route_186_230 | lightgbm | 20.661 | 4.885299 | 6.260601 | 4.193709 | 9.201811 |
| route_237_162 | baseline | 21.968 | 5.630856 | 6.488483 | 5.650000 | 9.533333 |
| route_237_162 | sgd | 21.968 | 3.496819 | 4.942537 | 2.656627 | 7.111673 |
| route_237_162 | lightgbm | 21.968 | 3.687911 | 4.802093 | 3.153033 | 7.006331 |
| route_236_161 | baseline | 21.873 | 4.942415 | 6.827922 | 3.800000 | 10.463333 |
| route_236_161 | sgd | 21.873 | 7.399145 | 9.601041 | 6.075494 | 15.375007 |
| route_236_161 | lightgbm | 21.873 | 5.779159 | 7.957357 | 4.192812 | 12.865057 |
| route_236_141 | baseline | 22.861 | 5.000490 | 5.892891 | 4.933333 | 8.516667 |
| route_236_141 | sgd | 22.861 | 3.317369 | 4.926401 | 2.356606 | 7.073137 |
| route_236_141 | lightgbm | 22.861 | 3.296562 | 4.557434 | 2.650903 | 6.520400 |
| route_238_239 | baseline | 21.853 | 7.711397 | 8.054621 | 7.950000 | 10.283333 |
| route_238_239 | sgd | 21.853 | 3.193445 | 3.832469 | 3.103720 | 5.538125 |
| route_238_239 | lightgbm | 21.853 | 4.853827 | 5.452090 | 4.824018 | 7.772894 |
| route_237_141 | baseline | 21.994 | 6.661314 | 7.233078 | 6.983333 | 9.750000 |
| route_237_141 | sgd | 21.994 | 2.853945 | 3.881693 | 2.423262 | 5.280357 |
| route_237_141 | lightgbm | 21.994 | 3.735433 | 4.559151 | 3.514926 | 6.542039 |
| route_132_132 | baseline | 19.620 | 11.481476 | 13.632759 | 12.750000 | 12.916667 |
| route_132_132 | sgd | 19.620 | 35.993661 | 36.754006 | 38.758831 | 40.193526 |
| route_132_132 | lightgbm | 19.620 | 37.984031 | 39.543651 | 38.918045 | 50.202139 |
| route_236_239 | baseline | 20.922 | 4.599409 | 5.419796 | 4.466667 | 8.033333 |
| route_236_239 | sgd | 20.922 | 3.000190 | 4.348281 | 2.180693 | 6.334057 |
| route_236_239 | lightgbm | 20.922 | 2.910768 | 4.010621 | 2.330210 | 5.815651 |
| route_161_161 | baseline | 17.870 | 7.822485 | 9.003898 | 8.000000 | 12.650000 |
| route_161_161 | sgd | 17.870 | 6.291875 | 7.699348 | 6.103668 | 10.561213 |
| route_161_161 | lightgbm | 17.870 | 7.286528 | 8.529689 | 7.182017 | 11.822143 |
| route_other | baseline | 10.340.234 | 9.299373 | 15.011117 | 5.966667 | 20.716667 |
| route_other | sgd | 10.340.234 | 8.560381 | 13.477602 | 5.315447 | 19.593919 |
| route_other | lightgbm | 10.340.234 | 7.881401 | 12.538980 | 5.149871 | 17.148492 |

## Recursos, interrupción y reinicio autorizado

El primer intento `f913cf2217fb4c58b8da47895f42b463` completó baseline y SGD,
pero el preflight antes de LightGBM midió 7,873 GiB libres frente a 8 exigidos.
Se conserva ese FAIL y la reserva original; no se publicó una evaluación final
completa ni se cambió ningún modelo a partir de resultados parciales.

El usuario aprobó el [perfil específico de inferencia final](../../docs/d02-final-evaluation-resource-review.md)
y el reinicio trazado: 6 GiB libres/2 GiB RSS, 50 GiB disco, cuatro hilos,
un modelo a la vez y 7.200 segundos por candidato. El contrato separado
[lightgbm-final-resources.yaml](../../configs/lightgbm-final-resources.yaml)
preserva el perfil original del protocolo. Entrenamiento mantiene 8/4 y
preparación 4/2. La nueva reserva enlaza el primer FAIL y sus hashes.
Los límites se supervisan cooperativamente, sin afirmar un límite duro del SO.

| Modelo | Segundos, incluida verificación compartida | Pico RSS acumulado del proceso (GiB) | Recortes | Orígenes desconocidos |
|---|---:|---:|---:|---:|
| baseline | 56.915 | 0.4784 | 0 | No aplica |
| sgd | 95.723 | 0.4826 | 6976 | No aplica |
| lightgbm | 56.475 | 0.4826 | 62 | 0 |

Los recortes a [1 segundo, 180 minutos] pertenecen al contrato ya congelado.
No hubo destinos desconocidos en esta cohorte. El reinicio no reeligió modelos,
no redujo datos y no cambió umbrales, métricas ni el holdout.

## Auditoría y reproducción

474 pruebas en desarrollo y 474 sobre wheel instalado, incluidos casos de
recurso/reinicio, corte temporal, DST, integridad y ausencia de fit; 37 imports
aislados. Ruff y `pip check` de ambos entornos PASS. Las dos advertencias de
Pytest corresponden al tamaño de batch MLP en fixtures pequeñas. Sin nuevas
dependencias para esta evaluación.

Una auditoría independiente recorrió las tres predicciones completas, reconstruyó
SGD mediante sus coeficientes y LightGBM desde `booster.txt`, recalculó las cuatro
métricas y los 28 segmentos más el global, y verificó hashes de raw/modelos,
linaje, reservas y selección anterior. No volvió a entrenar ni reajustó el protocolo.

- baseline: diferencia máxima de predicción independiente `0.0` minutos; 29 grupos verificados.
- sgd: diferencia máxima de predicción independiente `7.62939453125e-06` minutos; 29 grupos verificados.
- lightgbm: diferencia máxima de predicción independiente `0.0` minutos; 29 grupos verificados.

Identidades conservadas:

- Evaluación final: `ce0c3b7426dc43dfb76d366c22d73a31`.
- Holdout: `be5aef1e584949b897ccfd7b25d478fc`.
- Manifest holdout: `ba441be034bc0b4b8f33ec9876d6fc2cf6e02f51b2f62974ff95d28e6260b29b`.
- Manifest evaluación: `b8db6bd31643a1eba1a5822b42ceeb7636ca8da9c70ae939e8e3ed6298e20175`.
- Protocolo canónico: `740eabe6aebbad1608dde981e022c57051c7617691039c64a599ab61ae59268a`.
- Código evaluado: `fd70de9148614195c3beabb71325e88d7b6ec1d7210ebf6d30f6ccf38e741de7`.
- Lock entrenamiento/inferencia: `0a91f93e814050fe7171cbd91bdc12ae0693468c34267192cfbdffc28c61b079`.
- Wheel evaluado: `94dfd6aaa280210351e2f98854a5c91a2e3cbd0642cf25eac167ddb53cb49a83`.
- Reserva original: `5bed2be562adb42d83bf535681a3fb66b02288b685544e86bffde9e3c788c37b`.
- FAIL original: `9bf679476bd0eae423b4814302b94641f1f2e9a67e756183fb0008bc67dbd19f`.
- Reserva reinicio: `65a3fce4f886d582e8ffe2fa51366f0ba6e8f432e7c3725d1d268d644d22d57d`.
- Modelo lightgbm: `8bd17196b3a5c1974036c11456f61083d2a5f601236d55d56f884802b477cff6`.
- Modelo sgd: `bfe284f297e7eb8d67261242ab1d4d35dc9639d181760dc923da128e52082541`.
- Modelo baseline: `7d6e3eefd040f04f46e7a8f6ef6068fd65dcf86c56bb0e97cde5ecb8f0c8abf9`.

Recibos locales, excluidos de Git: `.cache/lightgbm-final/holdout-audit.json`,
`evaluation-audit.json`, `resource-software.json`; manifest y tres predicciones
en `data/processed/independent-final-evaluations/` bajo el ID anterior.
Los reportes JSON y reservas están en `reports/independent-final-evaluations/`.
Son artefactos de ejecución; el repositorio conserva el código, las configuraciones
y este informe pequeño. No se ejecutará de nuevo el protocolo para buscar otro
resultado. Para inspeccionar los CLI: `python -m src.evaluation.final_data --help`
y `python -m src.evaluation.final_run --help`.

Siguiente paso solicitado: T18 con revisión/aprobación de D-07 y dependencias.
Esta evaluación no implementa MLflow, API, Docker, CI ni monitoreo.
