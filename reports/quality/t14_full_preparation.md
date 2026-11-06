# T14 — Preparación abril–diciembre de 2025 bajo D-04 congelada

Fecha: 2026-11-03, America/Costa_Rica. **Registro/validación autorizados; ninguna excepción nueva aplicada.** [Contrato de ejecución](../../docs/t14-full-preparation.md). Este informe mide calidad y disponibilidad de fuentes; no evalúa modelos ni selecciona parámetros con test/replay.

**Nota histórica:** las mediciones siguientes son los rechazos originales del 2026-11-03 y se conservan intactas. El 2026-11-05 se aprobaron y aplicaron nueve autorizaciones acotadas; T14 terminó su auditoría integral. [Resultado actual](t14_completion.md). La aceptación humana no modifica los FAIL medidos ni conserva filas inválidas.

Estado local: `WAITING_FOR_REJECTED_LOT_DECISIONS`; 24 meses registrados, 15 con features aceptadas (incluye las 15 versiones previas) y 9 rechazos nuevos. El catálogo de 24 meses y su particionado requieren todas las entradas aceptadas.

Los 24 originales conservaron tamaño/SHA-256 en el preflight. Se reutilizan las versiones explícitas train/validation ya verificadas, con la única excepción existente de marzo. Cada archivo nuevo se registra LOCAL_UNVERIFIED, sin inventar fuente/fecha de descarga. No se descargan datos ni se reemplazan originales.

| Mes 2025 | Estado de esta etapa | Raw | Potencialmente elegibles DQ | Excluidas por fila | Reglas críticas |
|---|---|---:|---:|---:|---|
| 04 | FAIL; sin publicación | 3.970.553 | 3.934.184 | 36.369 | rows.duration_nonpositive: 0,875671 % > 0,500000 % |
| 05 | FAIL; sin publicación | 4.591.845 | 4.526.019 | 65.826 | rows.duration_nonpositive: 1,399699 % > 0,500000 %; rows.union_invalid_rows: 1,433541 % > 1,000000 % |
| 06 | FAIL; sin publicación | 4.322.960 | 4.252.977 | 69.983 | rows.duration_nonpositive: 1,586482 % > 0,500000 %; rows.union_invalid_rows: 1,618868 % > 1,000000 % |
| 07 | FAIL; sin publicación | 3.898.963 | 3.841.674 | 57.289 | rows.duration_nonpositive: 1,437921 % > 0,500000 %; rows.union_invalid_rows: 1,469339 % > 1,000000 % |
| 08 | FAIL; sin publicación | 3.574.091 | 3.524.959 | 49.132 | rows.duration_nonpositive: 1,338326 % > 0,500000 %; rows.union_invalid_rows: 1,374671 % > 1,000000 % |
| 09 | FAIL; sin publicación | 4.251.015 | 4.192.264 | 58.751 | rows.duration_nonpositive: 1,345067 % > 0,500000 %; rows.union_invalid_rows: 1,382046 % > 1,000000 % |
| 10 | FAIL; sin publicación | 4.428.699 | 4.359.033 | 69.666 | rows.duration_nonpositive: 1,534717 % > 0,500000 %; rows.union_invalid_rows: 1,573058 % > 1,000000 % |
| 11 | FAIL; sin publicación | 4.181.444 | 4.104.925 | 76.519 | rows.duration_nonpositive: 1,447275 % > 0,500000 %; rows.union_invalid_rows: 1,829966 % > 1,000000 % |
| 12 | FAIL; sin publicación | 4.305.006 | 4.244.816 | 60.190 | rows.duration_nonpositive: 1,347757 % > 0,500000 %; rows.union_invalid_rows: 1,398140 % > 1,000000 % |

## Interpretación y decisiones pendientes

Las cantidades potencialmente elegibles de un lote rechazado no son datasets aprobados: no se publican validated/features ni entran en el particionado. Las exclusiones se miden sobre raw completo. Superar el límite específico de duración no positiva o el global de inválidos bloquea aunque el resto pase.

D-04 conserva sus límites: duración no positiva >0,50 % y unión de inválidos >1,00 %, además de las otras reglas vigentes. La excepción de marzo no se extiende a ninguno de estos archivos. Cualquier aceptación excepcional debe aprobarse expresamente por mes/hash/reporte y conjunto exacto de fallos, conservando todas las exclusiones y el FAIL original. También puede conservarse el rechazo y solicitar una versión distinta aceptable de la fuente. No se propone una modificación automática de los umbrales.

La revisión de los nueve meses terminó: los nueve lotes están rechazados y requieren decisión antes de consumirlos. Solo después de contar con 24 entradas aceptadas se publicará configs/real-feature-batches.local.json y se ejecutará el particionado. No se declara cierre técnico de T14 con entradas faltantes o rechazadas.

El código ejecutado coincide con el wheel que aprobó 380 pruebas en desarrollo y wheel instalado, sin nueva modificación de módulos ni dependencias. Perfil de preparación: preflight 4 GiB libres/50 GiB disco, máximo RSS supervisado 2 GiB, cuatro hilos y meses secuenciales. Las mediciones son supervisión cooperativa de este host, no certificación Docker.

## Evidencia exacta de los rechazos

### 04 — Rechazo conservado

- Raw SHA-256: `6f98938de9380a3f85600533816f0dc0e6d9b5b210e485d623952bac599bbe28`.
- Reporte local: `reports/quality/2025/04/f6db7d68beab46ca9aa951f62667e76f.json`.
- Reporte SHA-256: `78f6b435ce53e436597f67d56b07c7862dcbe2aef43ffdb23a47e30ff777abdf`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 34769, "rate": 0.008756714744772328}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

### 05 — Rechazo conservado

- Raw SHA-256: `7ef46bcd0fceee7f8c0bb38a532be05bceefabb512d4bb0b32a7727dd862b15c`.
- Reporte local: `reports/quality/2025/05/f7956c2877e840bb9e28d2a9b4938c5c.json`.
- Reporte SHA-256: `ad6d83d714fa1286a02c75102b79a00937745a4c84f52195f715a168e0bed631`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 64272, "rate": 0.013996988138754683}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 65826, "rate": 0.014335414196254446}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.

### 06 — Rechazo conservado

- Raw SHA-256: `1bea7f5b09c744414451fa7fef09fbc5a393ffb1621c859be6ba0df23a14e1b6`.
- Reporte local: `reports/quality/2025/06/94921c20320247cf991ae6155c131163.json`.
- Reporte SHA-256: `d368f7906e68fd38d871d3b18e21c8d946f0ba87cf4816a0e6a8477632eb73b6`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 68583, "rate": 0.015864824102004182}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 69983, "rate": 0.016188676277365508}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.

### 07 — Rechazo conservado

- Raw SHA-256: `1efa6a0458dc60341f7f81dcbb5015af731f42d1a109f4e0d594dd46970fd4ef`.
- Reporte local: `reports/quality/2025/07/7834cea702854e6c8d1858f932f2337f.json`.
- Reporte SHA-256: `4109785b7a4c64ac52d637616f4b02a3f0a2cf669c4a53af92f00507b482eba5`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 56064, "rate": 0.01437920800992469}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 57289, "rate": 0.01469339411530707}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.

### 08 — Rechazo conservado

- Raw SHA-256: `b982ace703e3564d92e94edae5ec93515f4f1fb07a5b95e7404c32464c1a6a89`.
- Reporte local: `reports/quality/2025/08/14f5cdd15127480faa7fa8d30931e533.json`.
- Reporte SHA-256: `0d5c769f7092337a6265e6394b822c775f381c0070ceb5160148110b8bfde658`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 47833, "rate": 0.013383263045065165}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 49132, "rate": 0.013746712101062899}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.

### 09 — Rechazo conservado

- Raw SHA-256: `cd39b9901f01d1fd752d45cbaec91ee5f68c4dddf9e261e938c1dbab404644c7`.
- Reporte local: `reports/quality/2025/09/4ba53192c22548a78abf4062b76cc09a.json`.
- Reporte SHA-256: `6d27942f7d6648b56b03b636fe32750ca7dc9b07b65f17474826433fdc124901`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 57179, "rate": 0.013450670016454894}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 58751, "rate": 0.013820464053878897}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.

### 10 — Rechazo conservado

- Raw SHA-256: `e1f63caf331bc6230d9c6f757cb88e55fdc2bddde185fb414d2c947abdc773c3`.
- Reporte local: `reports/quality/2025/10/8b9d19977ce84aebb05cd9e961d9f970.json`.
- Reporte SHA-256: `79332c7a07be4826b4bcc5698406f7ff65177a1ca20e4b52136d72c421131a67`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 67968, "rate": 0.015347170805692598}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 69666, "rate": 0.015730579115898372}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.

### 11 — Rechazo conservado

- Raw SHA-256: `2cf2f3127f96d4d5dea30f8afe05119cf8e4ba57bd9e60b789d3f296fc8459ab`.
- Reporte local: `reports/quality/2025/11/518df25e97944bcea14b0887b0630f64.json`.
- Reporte SHA-256: `92d98e4c3f54213c7a1c826723af54ddce39c23681f23f9ea86955a3c464bb2b`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 60517, "rate": 0.014472751518374991}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 76519, "rate": 0.01829965916080665}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.

### 12 — Rechazo conservado

- Raw SHA-256: `eaba7ff61ebb6453fc6f673fda43d621380307f869b768b124992e8486c785e1`.
- Reporte local: `reports/quality/2025/12/33b48efbe94f4ddf9e767789c5aea7da.json`.
- Reporte SHA-256: `ad20196b63f0d20f7410088fcfead257746c5eabb0b0e6aeeaf3ee7c12309286`.
- Configuración SHA-256: `555f4b943b12884639369caeae348a37d97b7efb2918e72818fa8f1cd9a5dc48`.
- Política: `d04-real-v1-2026-11-03`; calidad aprobada=false; output=null.

Regla `rows.duration_nonpositive`: observado `{"count": 58021, "rate": 0.013477565420350168}`; límite `{"fail_above": 0.005, "warn_above": null, "denominator": "all_raw_rows"}`.

Regla `rows.union_invalid_rows`: observado `{"count": 60190, "rate": 0.013981397470758461}`; límite `{"fail_above": 0.01, "warn_above": 0.005, "denominator": "all_raw_rows"}`.
