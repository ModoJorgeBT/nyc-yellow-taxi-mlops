# Fixtures sintéticas T04

Diez Parquet de 12 filas cada uno, generados sin leer datos TLC reales. Son necesarios aunque existan archivos raw: fijan resultados conocidos y anomalías que una muestra real no garantiza, y permiten ejecutar CI sin red ni datasets grandes.

```powershell
.\.venv\Scripts\python.exe -m tests.fixtures.factory --seed 42 --output-dir tests/fixtures
```

La factoría conserva timestamps `us`, tipos históricos y 19 columnas base como las observadas en 2024. Es un contrato de prueba; el contrato productivo y los Quality Gates T08/T09 siguen pendientes. Las etiquetas de caso y la semilla están en metadata Parquet. No contiene una columna target ni una whitelist de inferencia; los importes finales solo simulan el esquema histórico.

| Archivo | Propósito y resultado conocido |
|---|---|
| `valid.parquet` | 12 viajes positivos, recogida enero 2024, sin nulos ni duplicados. |
| `null_zone.parquet` | Un origen nulo. |
| `null_timestamp.parquet` | Una llegada nula. |
| `nonpositive_duration.parquet` | Una duración cero y una negativa. |
| `pickup_outside_month.parquet` | Una recogida en febrero, manteniendo duración positiva. |
| `duplicate.parquet` | Una fila repetida exactamente en todas las columnas. |
| `invalid_passengers.parquet` | Un conteo negativo de pasajeros. |
| `missing_column.parquet` | Falta PULocationID. |
| `incompatible_type.parquet` | PULocationID de texto en lugar de entero. |
| `extra_column.parquet` | Añade cbd_congestion_fee para representar evolución de esquema. |

Las zonas 161/236 son valores canario sintéticos, no un catálogo aprobado. Tampoco se da por probada la disponibilidad del destino al inicio por usarlo en una fixture histórica. No se mezclan estas filas con entrenamiento o EDA real.

Se versionan únicamente estos pequeños archivos sintéticos. Los Parquet de `data/raw` permanecen excluidos de Git. La regeneración rechaza sobrescribir Parquet sin el marcador de origen sintético.
