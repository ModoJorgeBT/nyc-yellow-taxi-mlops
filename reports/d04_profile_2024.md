# D-04 — Perfilado aleatorio acotado de 2024

Estado: PROPOSAL_EVIDENCE_NOT_APPLIED. Ejecución UTC: 2026-11-03T20:56:20.393043+00:00.

Muestra: 240,000 filas; 20.000 por mes de 2024. Población declarada en footers: 41,169,720. Semilla: 20241104. Bloques de hasta 65,536 filas.

## Diseño y límites

Muestreo aleatorio sin reemplazo dentro de cada row group. Las cuotas mensuales se reparten proporcionalmente al número de filas del grupo con redondeo por restos mayores. Cada fila seleccionada tiene peso N_grupo/n_muestra_grupo. Las tasas estimadas anuales ponderan los grupos y meses por sus filas de footer; no son la media simple de meses.

Para extraer la muestra se decodificaron 41,169,471 filas por las restricciones de lectura de Parquet. El límite aplica a filas analizadas y memoria; no se presenta como lectura física de solo 240.000 filas. No se abrieron archivos de 2025.

Los índices seleccionados, hashes de muestra/archivos, frecuencias y métricas completas están en d04_profile_2024.json, excluido de Git. Se comprobaron los hashes antes/después. Las tasas de filas inválidas son estimaciones, no conteos completos ni decisiones sobre lotes.

Las repeticiones exactas se miden solo entre filas muestreadas: cero coincidencias no permite estimar la tasa de duplicados del lote. Tampoco cero nulos/códigos nuevos demuestra ausencia anual. No se publican datasets aprobados ni se modifica raw.

Tiempo: nyc-local-unambiguous-utc-elapsed-v1; tzdata 2026.6. Se apartan horas locales ambiguas/inexistentes y se compara duración en UTC.

Catálogo candidato: 265 registros, SHA-256 `1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed`. Su uso operativo sigue pendiente de aprobación.

## Métricas anuales de muestra

| Regla | Conteo observado en muestra | Tasa estimada ponderada (%) |
|---|---:|---:|
| timestamp_null | 0 | 0.00000 |
| invalid_historical_time | 0 | 0.00000 |
| ambiguous_local_time | 74 | 0.03277 |
| nonexistent_local_time | 0 | 0.00000 |
| duration_nonpositive | 69 | 0.02849 |
| pickup_outside_month | 5 | 0.00192 |
| PU_null | 0 | 0.00000 |
| PU_outside_catalog | 0 | 0.00000 |
| PU_special | 865 | 0.35995 |
| DO_null | 0 | 0.00000 |
| DO_outside_catalog | 0 | 0.00000 |
| DO_special | 2169 | 0.90167 |
| passenger_null | 23427 | 9.91916 |
| passenger_zero | 2292 | 0.95126 |
| passenger_negative | 0 | 0.00000 |
| passenger_above_6 | 1 | 0.00036 |
| passenger_above_8 | 0 | 0.00000 |
| passenger_adjustment_0_6 | 1 | 0.00036 |
| category_unknown | 23427 | 9.91916 |
| category_null | 23427 | 9.91916 |
| category_outside_dictionary | 0 | 0.00000 |
| passenger_null_and_metadata_null | 23427 | 9.91916 |
| duplicate_in_sample | 0 | No estimable con esta muestra |

## Comparación de población elegible candidata

Unión sin doble conteo: fechas interpretables, duración positiva, pickup en el mes nominal y origen perteneciente al catálogo. Destino y categorías no predictoras solo se miden. Pasajeros ausentes se conservan; valores fuera del rango candidato podrían normalizarse a ausencia, sujeto a aprobación.

| Alternativa | Exclusiones observadas | Tasa anual estimada (%) |
|---|---:|---:|
| no_duration_cap | 148 | 0.06317 |
| cap_60 | 4872 | 2.06222 |
| cap_120 | 372 | 0.15757 |
| cap_180 | 278 | 0.11748 |
| cap_240 | 273 | 0.11542 |
| cap_360 | 266 | 0.11256 |
| cap_1440 | 150 | 0.06406 |
| cap_180_exclude_special_origin | 1135 | 0.47398 |
| cap_180_exclude_invalid_passengers | 279 | 0.11784 |

## Comparación mensual

Los conteos de footer son exactos para estos archivos; las tasas son estimaciones de 20.000 filas por mes. Ninguna fila fue descartada del archivo original.

| Mes | Filas footer | Sin máximo (%) | Máximo 120 (%) | Máximo 180 (%) | Máximo 240 (%) | Pasajeros nulos (%) | p99 duración (min) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-01 | 2,964,624 | 0.0250 | 0.0750 | 0.0600 | 0.0600 | 4.7251 | 59.65 |
| 2024-02 | 3,007,526 | 0.0250 | 0.1150 | 0.0900 | 0.0900 | 6.0350 | 62.42 |
| 2024-03 | 3,582,628 | 0.0400 | 0.1300 | 0.0900 | 0.0850 | 11.9150 | 66.48 |
| 2024-04 | 3,514,289 | 0.0250 | 0.1150 | 0.0800 | 0.0800 | 11.4826 | 68.27 |
| 2024-05 | 3,723,833 | 0.0100 | 0.1050 | 0.0650 | 0.0650 | 10.9096 | 75.15 |
| 2024-06 | 3,539,193 | 0.0550 | 0.1650 | 0.1200 | 0.1200 | 11.6524 | 73.15 |
| 2024-07 | 3,076,903 | 0.0600 | 0.1450 | 0.1050 | 0.1000 | 8.8706 | 68.97 |
| 2024-08 | 2,979,183 | 0.0350 | 0.1100 | 0.0900 | 0.0850 | 8.8154 | 69.57 |
| 2024-09 | 3,633,030 | 0.0250 | 0.1500 | 0.0850 | 0.0850 | 13.3281 | 76.70 |
| 2024-10 | 3,833,771 | 0.0200 | 0.0900 | 0.0500 | 0.0500 | 10.2082 | 71.08 |
| 2024-11 | 3,646,369 | 0.3900 | 0.4900 | 0.4450 | 0.4400 | 10.3849 | 72.78 |
| 2024-12 | 3,668,371 | 0.0300 | 0.1700 | 0.1100 | 0.1050 | 8.8114 | 81.22 |

## Recursos y reproducción

| Medida | Observación |
|---|---:|
| ram_total_bytes | 33970917376 |
| process_peak_rss_bytes | 177385472 |
| arrow_allocated_at_finish_bytes | 0 |
| arrow_pool_peak_bytes | 35793856 |
| elapsed_seconds | 18.465260799974203 |

El tiempo incluye muestreo y hashes; RSS y memoria Arrow son mediciones distintas y no se suman. No es presupuesto de entrenamiento/Docker ni benchmark.

```powershell
.\.venv\Scripts\python.exe -m scripts.profile_d04 --catalog docs/reference/taxi_zone_lookup_candidate.csv --output reports/d04_profile_2024.json
```

Se repitió la extracción con la misma semilla: índices, hashes, métricas comunes y cuantiles idénticos. La segunda ejecución añadió desglose de categorías nulas frente a códigos no nulos fuera del diccionario. Recursos/fecha varían entre ejecuciones.

[Propuesta pendiente de aprobación](../docs/d04-quality-proposal.md).
