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
