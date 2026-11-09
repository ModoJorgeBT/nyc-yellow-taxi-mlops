# T28 — Comparación retrospectiva de calidad

**Verificación técnica PASS, 2026-11-09.** Referencia aprobada: doce reportes
completos de train 2024; comparación con el mismo mes del replay 2025. Se
reutilizan reportes T10 enlazados por hashes al split T14; no se leen Parquet,
etiquetas ni predicciones. Los cambios de tasas/volumen son descriptivos.

| Mes | Filas raw del reporte | Duración no positiva | Unión de inválidos | Volumen / mismo mes 2024 | Calidad/aceptación |
|---|---:|---:|---:|---:|---|
| 2025-07 | 3,898,963 | 1.437921 % | 1.469339 % | 1.2672 | FAIL conservado / excepción previa |
| 2025-08 | 3,574,091 | 1.338326 % | 1.374671 % | 1.1997 | FAIL conservado / excepción previa |
| 2025-09 | 4,251,015 | 1.345067 % | 1.382046 % | 1.1701 | FAIL conservado / excepción previa |
| 2025-10 | 4,428,699 | 1.534717 % | 1.573058 % | 1.1552 | FAIL conservado / excepción previa |
| 2025-11 | 4,181,444 | 1.447275 % | 1.829966 % | 1.1467 | FAIL conservado / excepción previa |
| 2025-12 | 4,305,006 | 1.347757 % | 1.398140 % | 1.1735 | FAIL conservado / excepción previa |

Los seis FAIL son los incumplimientos D-04 ya medidos y autorizados por mes/
hash/reporte. No se conceden excepciones nuevas ni se reingieren lotes. Se
preservan los FAIL, exclusiones y aceptación excepcional originales. El cambio
de schema común es la columna opcional conocida cbd_congestion_fee, sin
autorizarla como predictor. No se midieron distribuciones por categoría ni
tasas de nulos por columna ausentes en el reporte agregado.

Referencia y reportes JSON locales ignorados en `reports/monitoring/quality/`.
Referencia congelada: `da9dc7a2b697cce15265509f5471bbd4987796ce2c6fb9469395de3755a7cc51`.

[Contrato, comandos y límites](../../docs/t26-t28.md). No acredita PSI,
desempeño predictivo, triggers, promociones ni G5 completo.
