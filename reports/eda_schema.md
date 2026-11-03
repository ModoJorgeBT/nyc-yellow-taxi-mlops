# T05 — Perfilado tecnico acotado de 2024

Ejecucion UTC: 2026-11-03T18:49:14.620283+00:00. Python 3.14.7; PyArrow 26.0.1.

Muestra: 90,112 filas; footers 2024: 41,169,720. Primeras 2048 filas de cada row group; rangos exactos y hashes en el JSON local.

La muestra es posicional determinista y sesgada, no representativa del anio. Tasas, extremos y cuantiles describen solo las filas leidas. No se perfilaron filas de 2025 ni se eligieron particiones o entrenaron modelos. Para SHA-256 se leyeron los bytes comprimidos por bloques; solo se decodificaron las filas seleccionadas.

Los timestamps se restaron tal como estan almacenados, sin convertir zona horaria. La interpretacion historica/DST sigue pendiente; estas duraciones son exploratorias.

## Observaciones por mes

| Mes | Filas | Fuera mes | Duracion <=0 | Positiva p50/p95/p99/max (min) | Duplicados |
|---|---:|---:|---:|---|---:|
| 2024-01 | 6144 | 3 | 2 | 12.28/44.45/71.96/1438.53 | 0 |
| 2024-02 | 6144 | 11 | 5 | 10.87/37.90/51.37/1436.57 | 0 |
| 2024-03 | 8192 | 16 | 1 | 12.10/40.54/56.82/1429.33 | 0 |
| 2024-04 | 8192 | 4 | 2 | 14.77/40.05/55.73/1439.42 | 0 |
| 2024-05 | 8192 | 13 | 2 | 13.60/50.89/73.29/1436.73 | 0 |
| 2024-06 | 8192 | 19 | 5 | 12.93/36.48/50.96/1432.23 | 0 |
| 2024-07 | 6144 | 15 | 6 | 13.87/40.23/63.73/1437.87 | 0 |
| 2024-08 | 6144 | 17 | 2 | 12.33/43.83/64.91/1437.52 | 0 |
| 2024-09 | 8192 | 20 | 0 | 10.97/33.70/49.62/1424.88 | 0 |
| 2024-10 | 8192 | 12 | 2 | 12.54/38.70/70.69/1370.95 | 0 |
| 2024-11 | 8192 | 13 | 2 | 13.03/38.60/53.89/1437.23 | 0 |
| 2024-12 | 8192 | 12 | 6 | 12.65/42.85/66.57/1438.95 | 0 |

## Nulos y pasajeros en la muestra

| Mes | Origen nulo | Destino nulo | Pickup/dropoff nulos | Pasajeros nulos/cero/neg. |
|---|---:|---:|---|---|
| 2024-01 | 0 | 0 | 0/0 | 0/52/0 |
| 2024-02 | 0 | 0 | 0/0 | 0/78/0 |
| 2024-03 | 0 | 0 | 0/0 | 0/107/0 |
| 2024-04 | 0 | 0 | 0/0 | 2048/65/0 |
| 2024-05 | 0 | 0 | 0/0 | 0/102/0 |
| 2024-06 | 0 | 0 | 0/0 | 2048/46/0 |
| 2024-07 | 0 | 0 | 0/0 | 0/69/0 |
| 2024-08 | 0 | 0 | 0/0 | 0/50/0 |
| 2024-09 | 0 | 0 | 0/0 | 0/79/0 |
| 2024-10 | 0 | 0 | 0/0 | 0/68/0 |
| 2024-11 | 0 | 0 | 0/0 | 0/58/0 |
| 2024-12 | 0 | 0 | 0/0 | 0/100/0 |

## Zonas observadas (sin validacion contra catalogo)

| Mes | Origen min/max/unicos | Destino min/max/unicos |
|---|---|---|
| 2024-01 | 4/265/121 | 1/265/194 |
| 2024-02 | 4/265/93 | 1/265/183 |
| 2024-03 | 1/265/131 | 1/265/199 |
| 2024-04 | 1/265/149 | 1/265/213 |
| 2024-05 | 4/265/111 | 1/265/209 |
| 2024-06 | 4/265/172 | 1/265/206 |
| 2024-07 | 1/265/112 | 1/265/203 |
| 2024-08 | 1/265/115 | 1/265/205 |
| 2024-09 | 1/265/121 | 1/265/199 |
| 2024-10 | 4/265/119 | 1/265/204 |
| 2024-11 | 4/265/120 | 1/265/199 |
| 2024-12 | 1/265/155 | 1/265/200 |

## Recursos observados

| Medida | Valor |
|---|---:|
| logical_cpus | 12 |
| disk_free_bytes | 348560023552 |
| ram_total_bytes | 33970917376 |
| process_peak_rss_bytes | 129622016 |
| python_tracemalloc_peak_bytes | 9462440 |
| arrow_pool_peak_bytes | 31951680 |
| elapsed_seconds | 6.588085599942133 |
| docker_limits | NOT_MEASURED |

RSS es el pico del proceso completo; Arrow y tracemalloc cubren asignadores distintos y no deben sumarse para estimar RAM total. El tiempo incluye hashes y perfilado. RAM total y disco libre son observaciones de esta máquina, no presupuesto aprobado. No se extrapola este consumo a entrenamiento, codificación, RandomForest o Docker.

## Esquema y diccionario

El [inventario T03](../reports/raw_inventory.md) encontró 19 columnas en 2024 y 20 en 2025 por `cbd_congestion_fee`, sin cambios de tipo en las compartidas. El esquema usa `Airport_fee` mientras el diccionario escribe `airport_fee`: decidir normalización explícita en T08. Los timestamps `us` no declaran zona. `RatecodeID` es código final según el diccionario y sigue deshabilitado; el destino histórico no demuestra destino conocido al inicio.

Fuentes contrastadas: [diccionario TLC de marzo 2025](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf), [página TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), [lectura por batches de PyArrow](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html). La procedencia remota y fecha de descarga de los archivos aportados no están verificadas.

## Propuesta para revisión D-02/D-04

Estos candidatos documentan la discusión; no son configuración ejecutable ni autorización de descarte:

| Control | Propuesta de frontera | Pendiente de aprobación/calibración |
|---|---|---|
| Esquema esencial | 0 columnas esenciales ausentes y 0 tipos incompatibles | Lista y compatibilidad exacta en T08. |
| Etiqueta histórica | Duración estrictamente > 0, con ambos timestamps presentes | Tolerancia de filas descartadas para rechazar el lote. |
| Coherencia mensual | Recogida en el mes nominal; llegada puede cruzar de mes | Tolerancia de excepciones y política de cuarentena. |
| Duración máxima | Comparar alternativas con muestreo representativo e investigar extremos cercanos a 24 h | Ningún máximo numérico aprobado con esta muestra. |
| Zonas, pasajeros, duplicados y volumen | Medición observada como referencia exploratoria | Catálogo, clave de viaje y tasas mínimas/máximas de lote pendientes. |

- Mantener lectura por batches y evitar concatenar 24 meses en RAM. Presupuesto de entrenamiento y muestreo se aprueba por separado; límites Docker no medidos.
- Columnas esenciales ausentes o tipos incompatibles: fallo estructural propuesto, sin tolerancia de columnas faltantes.
- Duración no positiva o timestamp esencial ausente: fila no utilizable para etiqueta; tolerancia para rechazar lote completo pendiente. No fijar duración máxima a partir de esta muestra sesgada.
- Volumen: calibrar por mes comparable y fuente, sin imponer a 2025 el volumen de 2024; mínimo de lote pendiente.
- Nulos de zonas, categorías y duplicados: umbrales de lote pendientes. Ceros observados en una muestra no prueban ausencia anual. Igualdad de filas no sustituye la definición de clave de viaje.
- Catálogo de zonas y rangos aprobados: no evaluados. No clasificar automáticamente códigos especiales como inválidos.
- No asignar PASS/FAIL de calidad, aprobar D-01/D-02/D-04 ni filtrar raw con este reporte.

## Reproducción

```powershell
.\.venv\Scripts\python.exe -m scripts.profile_sample --rows-per-group 2048
```

La salida JSON detallada queda en `reports/eda_schema.json`, excluida de Git. El Markdown resume la evidencia; las fixtures sintéticas se prueban aparte y no entran en esta muestra.
