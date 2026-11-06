# T14 — Continuación aprobada y preparación integral

Fecha: 2026-11-05, America/Costa_Rica. **CIERRE TÉCNICO PASS; revisión humana de resultados independiente.** Estado de ejecución: `VERIFIED_T14_FULL_24_MONTH_PROTOCOL`. [Contrato](../../docs/t14-full-preparation.md) y [aprobación concreta](../../docs/t14-quality-exceptions-proposal.md).

Los 24 raw están registrados LOCAL_UNVERIFIED; su presencia no acredita procedencia. Se conservaron fuente/fecha de descarga nulas. Las quince versiones train/validation previamente verificadas se reutilizan sin reajustar T15. Se agregan únicamente las nueve versiones explícitamente aprobadas; los FAIL originales y D-04 global permanecen vigentes.

## Aplicación de las nueve autorizaciones

| Mes | Estado de esta continuación | Filas raw | Excluidas por calidad | Filas con features |
|---|---|---:|---:|---:|
| 04/2025 | Features verificadas / aceptación excepcional | 3.970.553 | 36.369 | 3.934.184 |
| 05/2025 | Features verificadas / aceptación excepcional | 4.591.845 | 65.826 | 4.526.019 |
| 06/2025 | Features verificadas / aceptación excepcional | 4.322.960 | 69.983 | 4.252.977 |
| 07/2025 | Features verificadas / aceptación excepcional | 3.898.963 | 57.289 | 3.841.674 |
| 08/2025 | Features verificadas / aceptación excepcional | 3.574.091 | 49.132 | 3.524.959 |
| 09/2025 | Features verificadas / aceptación excepcional | 4.251.015 | 58.751 | 4.192.264 |
| 10/2025 | Features verificadas / aceptación excepcional | 4.428.699 | 69.666 | 4.359.033 |
| 11/2025 | Features verificadas / aceptación excepcional | 4.181.444 | 76.519 | 4.104.925 |
| 12/2025 | Features verificadas / aceptación excepcional | 4.305.006 | 60.190 | 4.244.816 |

Hay **24 versiones de features aceptadas** de 24 requeridas. Las nueve autorizaciones excluyen 543.725 filas inválidas en total. No son umbrales nuevos ni aceptación genérica de otros fallos/archivos.

## Recursos y software

Perfil de preparación aprobado: mínimo inicial 4 GiB RAM/50 GiB disco libres, máximo RSS supervisado 2 GiB, cuatro hilos y meses secuenciales. Supervisión cooperativa entre bloques; no certifica límites de Docker/OS. [391 pruebas en desarrollo y wheel instalado](../../docs/t14-quality-exceptions-proposal.md); Ruff y pip check correctos, sin dependencias nuevas. Wheel SHA-256: `3212e7215e0edb6059080accd1496f966fd3d79aedee4ee4a398d82f2cf69f9a`.

Las mediciones originales completas se conservan en [el reporte histórico](t14_full_preparation.md). La aceptación excepcional es una decisión humana separada del resultado de calidad; no conserva filas inválidas.

## Auditoría integral

| Partición | Filas publicadas | Excluidas por corte de etiqueta |
|---|---:|---:|
| train | 41.119.495 | 561 |
| validation | 11.163.264 | 930 |
| test | 12.712.466 | 714 |
| monitoring_replay | 24.266.924 | 747 |

Split `e02156de2ac5477bafc4657774e31673`. Se auditaron todas las identidades y valores de features, target y contexto frente a las fuentes filtradas por corte, con bloques distintos y firma canónica estructurada; también hashes físicos, conteos, calendario Nueva York, duración UTC y no solapamiento. Los 24 raw y diez FAIL originales conservan sus hashes; D-04 global no cambió.

Train y validation coinciden con T15 congelada en conteos y hashes lógicos/etiquetas; validation también en contexto. El modelo ajustado y el evaluado permanecen intactos. Test/replay solo se usaron para preparación y auditoría, sin métricas predictivas ni selección. No se demuestra disponibilidad histórica de publicación TLC: es replay por eventos.

El test representa únicamente filas elegibles con las exclusiones documentadas; no mide desempeño sobre viajes descartados. T16/T17 continúan después de este cierre técnico según sus decisiones aprobadas; no se afirma aquí entrenamiento, selección, champion, MLflow, API ni Docker.

Firmas canónicas de todas las filas publicadas (SHA-256; estructura NumPy little-endian con seis int64 de features, float64 de target, índices/eventos int64 y fuente ASCII de 32 bytes):

- train: `ad646be94f823269323c8d93920c354fb1549cb10a731b20cffd746ca535add4`.
- validation: `50850298aa8ce8a1b6bafe17dce4e0dda084dbede00457fa8f78042f14470752`.
- test: `5d8d582ae2ee78fb88d027ed070951f542a6ee168d671e499d444833e21e81ab`.
- monitoring_replay: `a6ed34168b169aeac60541958062748822acb7703ce5e74888ac25baf4778033`.

Conteos mensuales y auditoría detallada local: `.cache/t14-approved/audit.json`; manifest final: `data/processed/splits/<split_id>/split_manifest.json`. Datos, modelos, catálogos y JSON generados siguen excluidos de Git.

## Identidades y evidencia de las versiones nuevas

### 04/2025

Validación `2a0e83ce9f6e4730a1d8baa5c307c190`; features `a2d13c5f346f42448c66c2a9401eeaa3`.

Manifest features SHA-256: `19c89675c7d2dd9d288660b4a8c7136a99dc3abd74ae17fde833daa8d95d261a`.

Autorización SHA-256: `ef3b0f47b3d6e47b194c9228bbd4f33e647b5b02725c7a359214d617d4e47740`; raw SHA-256: `6f98938de9380a3f85600533816f0dc0e6d9b5b210e485d623952bac599bbe28`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 05/2025

Validación `f972e69ac96445adb7c01491afc27c98`; features `24d85026a58942dcb6d9f500f1f44d2a`.

Manifest features SHA-256: `69651dd93e5e269c6405b09c8d42148778ef1bd5d582bae2913126d50ce5e160`.

Autorización SHA-256: `31721d37f861449b0a24c5030cf15267b9c98d497684bdf9ea63b1228e1a0414`; raw SHA-256: `7ef46bcd0fceee7f8c0bb38a532be05bceefabb512d4bb0b32a7727dd862b15c`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 06/2025

Validación `0192866e42024e7f9c8347e262876487`; features `ac333fca27854c78a4804c8b8614bdad`.

Manifest features SHA-256: `d60f3a9dd31a6ccf4f3fe4d568241eb7efadf4dced99fbeaa4f464870e47d92e`.

Autorización SHA-256: `93a49798c53ba78bd3a66bf30e78d83388eba79771a34227c03df131cbe07400`; raw SHA-256: `1bea7f5b09c744414451fa7fef09fbc5a393ffb1621c859be6ba0df23a14e1b6`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 07/2025

Validación `9421a962474e463dadb8a5eeca8dc2de`; features `ee92d14246354ed594889d77532143c7`.

Manifest features SHA-256: `2f13fbaaa0a8bd07e0b182993787bc8fe3638106ae2ab3d50d9d8e595776a945`.

Autorización SHA-256: `f317666c0c48e3501cecb24ff691772867475cab9d749af26741c00145a449af`; raw SHA-256: `1efa6a0458dc60341f7f81dcbb5015af731f42d1a109f4e0d594dd46970fd4ef`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 08/2025

Validación `15c5f65072bb4db8b1c4df7704add576`; features `493b431cfa0142198b40d85d9532af5c`.

Manifest features SHA-256: `4728ebd315a061dc152de4cd6a562e49720d6bfe5c6a30e56b42a37f076f79a5`.

Autorización SHA-256: `f5e8422b0980bf29cffb8cf1d9961768c981df53cf3aa71d4364019d4c72e21b`; raw SHA-256: `b982ace703e3564d92e94edae5ec93515f4f1fb07a5b95e7404c32464c1a6a89`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 09/2025

Validación `b80c89deb4324dd7b3f5c14694c34b3e`; features `edea037cf5444843a7d5eed463f4fee8`.

Manifest features SHA-256: `5c468612b1752ecc81a24fc100c9000d3b60d4a92cb982c1681752c7bb07b898`.

Autorización SHA-256: `9c19d7be885c3433483c4b8d347ff9f9982b5def236ffc5281d7759c51cb3597`; raw SHA-256: `cd39b9901f01d1fd752d45cbaec91ee5f68c4dddf9e261e938c1dbab404644c7`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 10/2025

Validación `0228a7a2975044a38aac36a8b51bc4c2`; features `5b3f19caeb834a3b929dc1e802d81c42`.

Manifest features SHA-256: `541484c11812f43bd9e470351945b5c1e735b2477095d746eb06b6847f544fce`.

Autorización SHA-256: `3b090e054453c550feb27f6971d483688de3794039d27846ecedec82b19ee42f`; raw SHA-256: `e1f63caf331bc6230d9c6f757cb88e55fdc2bddde185fb414d2c947abdc773c3`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 11/2025

Validación `fae1ecfa1c4e454f849cc89fdfcab20a`; features `b539ccfaafa949f0a2782fe8498983c6`.

Manifest features SHA-256: `16373026b56a5067fbb3d3f1c19e60da799d980334c6d6724bf09f9dae3ee989`.

Autorización SHA-256: `18ed7b860d6bcbd102fe5c107aab6c39f0e86052fcbb992ed9aa0a12177f9dab`; raw SHA-256: `2cf2f3127f96d4d5dea30f8afe05119cf8e4ba57bd9e60b789d3f296fc8459ab`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

### 12/2025

Validación `829bffcf8efe40898e5eda33061e2188`; features `8de4a94628cf4ce8a4170c49d6974784`.

Manifest features SHA-256: `ff8ec732597dd9851dc004e46e58217a82db961e5f5997f6f178b5333cde0428`.

Autorización SHA-256: `fd04be436a9bf4b58c175b2076b3b57a4ead5382f57dfcca40bbb6145893aeef`; raw SHA-256: `eaba7ff61ebb6453fc6f673fda43d621380307f869b768b124992e8486c785e1`.

Se conserva raw_quality_status=FAIL, quality_passed=false y data_quality_approved=true; filas inválidas excluidas.

Actualización posterior: la primera comparación T16/T17 ya terminó con [entrenamiento auditado](t16_training.md) y [evaluación auditada](../evaluation/t17_model_comparison.md). No altera esta evidencia T14 ni sus hashes históricos.
