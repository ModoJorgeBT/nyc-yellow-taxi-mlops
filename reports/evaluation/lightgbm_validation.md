# LightGBM — Extensión de T16/T17, solo validación

Fecha: 2026-11-05, America/Costa_Rica. **CIERRE TÉCNICO PASS del alcance aprobado: ajuste completo y evaluación solo con validation. Nueva evaluación final independiente PENDIENTE; revisión humana independiente.**

[Protocolo aprobado](../../docs/t16-lightgbm-extension-proposal.md), [configuración](../../configs/lightgbm.yaml) y [primera comparación congelada](t17_model_comparison.md).

## Comparación de validación

11.163.264 filas de enero–marzo de 2025; métricas exactas en minutos. Baseline/SGD/MLP se reutilizan exclusivamente como resultados congelados de la primera comparación, sin reajustarlos.

| Modelo | MAE | RMSE | MedAE | P90 absoluto |
|---|---:|---:|---:|---:|
| baseline | 7.741890 | 11.912962 | 5.583333 | 15.250000 |
| sgd | 6.876910 | 10.559177 | 4.515139 | 15.485330 |
| mlp | 11.856108 | 15.946811 | 9.250000 | 24.458932 |
| lightgbm | 6.496404 | 9.847425 | 4.631360 | 13.478764 |

Variación de MAE de LightGBM frente a SGD: 5.53 % de reducción (un valor negativo indicaría empeoramiento). No se ha evaluado LightGBM en test ni replay, ni se ha elegido un nuevo champion. SGD continúa siendo la selección de la primera comparación; el nuevo experimento no reescribe esa decisión.

El error mediano de LightGBM es 4.631360 min, frente a 4.515139 de SGD: empeora en esa métrica. Las diferencias por segmento y el estado pendiente de evaluación final deben acompañar cualquier decisión posterior de promoción.

El test abril–junio de 2025 ya era conocido cuando se pidió incorporar LightGBM. El usuario eligió expresamente evaluar esta extensión **solo en validation**. Para confirmar su desempeño final hace falta una evaluación independiente todavía no definida/aprobada; no se sustituye por replay ni por repetir el test observado.

## Entrenamiento y recursos

- Train completo: **41,119,495** filas elegibles de 2024, 10,039 bloques de conversión; sin submuestreo de las filas de ajuste.
- Seis features causales: origen, hora/día/mes de recogida, pasajeros imputados e indicador de ausencia. Vocabulario observado en todo train: 263 zonas; origen categórico nativo, desconocidos -1.
- GBDT, objetivo L1, 100 árboles, learning_rate 0,05, máximo 31 hojas, min_data_in_leaf 1.000, max_bin 63, CPU/cuatro hilos y semilla 42. Sin búsqueda, bagging, GOSS, selección de columnas ni early stopping.
- Hasta 200.000 filas train solo para calcular cortes de discretización; Dataset y árboles usan todas las filas. El Dataset se construye por bloques desde archivos compactos. No hay escalado ni OHE para este candidato.
- Ajuste incluyendo preparación y verificaciones: 184.15 s. Pico RSS nativo observado: 2.213 GiB; pico del proceso coordinador: 2.224 GiB.
- Preflight: 9.210 GiB RAM libre y 313.702 GiB disco. Límites aprobados: mínimo 8/50 GiB, máximo 4 GiB RSS y dos horas. No se ampliaron ni se redujeron datos.
- Evaluación: 72.75 s, pico RSS 0.481 GiB. Recortes a [1/60,180] minutos: 74 (0.000663 %). Filas con origen desconocido: 0.

Un proceso externo vigiló el entrenamiento nativo cada 0,1 s, con pruebas de cancelación ante exceso de RSS/timeout; esto no constituye un límite duro de memoria del sistema operativo. Los mapas de entrada se liberan después de construir el Dataset para no retener páginas durante boosting.

LightGBM emitió la advertencia de que max_bin puede ignorarse en features categóricas con muchas categorías. El límite de 63 bins no recorta el vocabulario de origen a 63 zonas; se conserva la codificación categórica observada en train. No es un fallo D-04 ni una autorización nueva.

## Pruebas y auditoría

**447 pruebas PASS en desarrollo y 447 desde wheel instalado**, en checkout sin src ni datos reales; 35 imports aislados. Ruff lint/formato sobre 70 archivos y pip check en ambos entornos PASS. Se añadió únicamente LightGBM 4.7.0; las 23 versiones previas permanecieron iguales y el lock contiene ahora 24 paquetes.

Un primer intento terminó los árboles, pero fue invalidado por la auditoría de recursos: el supervisor medía el redirector de Python del venv Windows. Se conservó como intento rechazado, sin evaluar validation. La corrección exige handshake de PID/parentesco antes de importar librerías nativas y mide/cancela el proceso real. Dos pruebas adicionales verifican RSS/timeout sobre el hijo real; el ajuste completo se repitió con los mismos datos, parámetros y presupuesto.

La integración real detectó el fallo de save_model en rutas Unicode de Windows; la solución escribe model_to_string con Python/UTF-8 y carga el Booster desde texto. Las fixtures prueban rutas con acentos, categorías desconocidas, varias tandas, serialización, matrices alteradas, guardas del proceso nativo y bloqueo de test/replay. Los logs del hijo usan UTF-8 explícito.

La auditoría de ajuste barrió independientemente todo train para reconstruir vocabulario, matriz compacta y hashes de etiquetas; contrastó Dataset de 41.119.495 filas, 100 árboles y configuración. Un probe de 8.192 filas contrastó Pipeline de inferencia y representación numérica; no se presenta como estimación de precisión.

La auditoría de evaluación volvió a predecir **las 11,163,264 filas** desde el texto del Booster, codificando categorías independientemente; diferencia máxima 0 minutos. Recalculó todos los errores, cuantiles exactos y 28 segmentos; verificó el catálogo de rutas solo por frecuencia de validation. Los 24 raw, ambos modelos T15 y artefactos/selección originales permanecen intactos.

Las métricas corresponden a filas elegibles, con normalizaciones/exclusiones D-04 y cortes de etiqueta ya auditados en T14. Procedencia LOCAL_UNVERIFIED y diez excepciones humanas de calidad siguen registradas; no se inventa origen de descarga ni se aceptan fallos nuevos.

## Identidades

- Entrenamiento LightGBM: `a36932872f8e49989a52bb76186ca88a`; manifest SHA-256 `95c132ccdbd034370dd20268a1fce10bfa30796fc0442715a7fdbf56ef3e77a6`.
- Evaluación LightGBM: `e80728e5140a4bbd936fc7b740c73544`; manifest SHA-256 `4d81c5e387439f55a4f3f6195eb86ab7e9b0768ed3139c125a612eb55f863f4b`.
- Modelo joblib SHA-256: `8bd17196b3a5c1974036c11456f61083d2a5f601236d55d56f884802b477cff6`; Booster texto: `daaa5d3d98530529695ea98749a00f9cca999b10126c592525a5a289cc4714eb`.
- Auditoría de ajuste SHA-256: `74db79b7dbccd36dbcf5a3be3eac997fa69a0e2c84bcbc2166da05f722d0f8e3`; evaluación: `3503e1df7210df21b17a802bef70022489162fe70a5c95ab797171d8d6c658fa`.
- Wheel SHA-256: `45cc15946b71a506b6846edf583fba153ff8ef503b302b7d6ff258d19ee29e67`; código: `a5a4a0657968f0672bdfb7e40d31d32bad3c0e1be24c47d95495ead49aef4524`.
- Lock SHA-256: `0a91f93e814050fe7171cbd91bdc12ae0693468c34267192cfbdffc28c61b079`.
- Selección original conservada SHA-256: `e863c7c74c93a6a7478bd0b831b8b29848e42c7fc16bff04762a35c3df94c61d`.

Artefactos locales: `models/lightgbm/a36932872f8e49989a52bb76186ca88a`, `data/processed/lightgbm-evaluations/e80728e5140a4bbd936fc7b740c73544` y recibos `.cache/lightgbm/`. Se excluyen de Git; el reporte Markdown sí se puede versionar. T18/MLflow, promoción, API y Docker siguen pendientes.

## Segmentos completos de validación

Franjas de seis horas locales de Nueva York; rutas observadas solo para análisis posterior, sin destino en las features.

| Segmento | Filas | MAE | RMSE | MedAE | P90 absoluto |
|---|---:|---:|---:|---:|---:|
| band_0 | 959,967 | 5.670109 | 8.085055 | 4.216525 | 12.031539 |
| band_1 | 2,323,884 | 6.912280 | 10.587398 | 4.753174 | 14.911670 |
| band_2 | 3,811,570 | 7.279312 | 11.380637 | 4.998871 | 15.108056 |
| band_3 | 4,067,843 | 5.720235 | 8.080516 | 4.355787 | 11.742014 |
| month_2025_01 | 3,471,776 | 6.310568 | 9.534778 | 4.519363 | 13.092309 |
| month_2025_02 | 3,571,047 | 6.434926 | 9.691716 | 4.628139 | 13.312164 |
| month_2025_03 | 4,120,441 | 6.706267 | 10.233002 | 4.732229 | 13.934428 |
| route_132_132 | 22,166 | 37.940407 | 39.433946 | 38.524385 | 50.148085 |
| route_141_236 | 25,012 | 3.344420 | 4.160610 | 3.051661 | 6.307555 |
| route_142_239 | 26,721 | 4.408909 | 4.999485 | 4.428067 | 7.252657 |
| route_161_161 | 21,666 | 7.413739 | 8.430595 | 7.314260 | 11.746118 |
| route_161_236 | 28,625 | 3.287082 | 4.504151 | 2.583620 | 6.635964 |
| route_161_237 | 33,387 | 4.386791 | 5.172255 | 4.268451 | 7.798852 |
| route_186_230 | 24,870 | 4.524702 | 5.667518 | 4.095995 | 8.481710 |
| route_236_141 | 23,455 | 2.942216 | 3.751407 | 2.554283 | 5.758076 |
| route_236_161 | 23,625 | 5.035031 | 6.665274 | 3.838297 | 10.938891 |
| route_236_236 | 50,911 | 5.514918 | 6.177514 | 5.439548 | 8.123854 |
| route_236_237 | 62,100 | 3.174328 | 3.934628 | 2.882739 | 5.984939 |
| route_236_239 | 21,717 | 2.711336 | 3.674106 | 2.194388 | 5.473107 |
| route_237_141 | 22,645 | 3.779417 | 4.488071 | 3.642614 | 6.466809 |
| route_237_161 | 29,630 | 3.329401 | 4.416627 | 2.738605 | 6.573212 |
| route_237_162 | 23,964 | 3.522326 | 4.515444 | 3.113425 | 6.664810 |
| route_237_236 | 71,372 | 3.365381 | 4.074263 | 3.165115 | 6.134527 |
| route_237_237 | 49,425 | 4.986949 | 5.846936 | 4.841663 | 7.867264 |
| route_238_239 | 23,055 | 4.840841 | 5.392023 | 4.825104 | 7.606633 |
| route_239_142 | 25,950 | 4.259735 | 4.874838 | 4.191388 | 7.239105 |
| route_239_238 | 27,789 | 4.852047 | 5.372402 | 4.877311 | 7.418118 |
| route_other | 10,525,179 | 6.567858 | 9.902413 | 4.689325 | 13.730109 |


## Evaluación independiente posterior

La entrega anterior fue exclusivamente validation. Posteriormente se aprobaron
y evaluaron enero–marzo de 2026 sin reajustar este modelo: [reporte final
auditado](lightgbm_final_evaluation.md). Los números, alcance y artefactos de
validation descritos arriba no cambian.
