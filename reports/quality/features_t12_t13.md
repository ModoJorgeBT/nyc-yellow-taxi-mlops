# T12/T13 — Ejemplos ejecutados con fixtures

Cada caso pasó por registro local explícito de una fixture, validación TEST_ONLY de T10 y construcción de features. Ningún archivo TLC real se procesó ni se entrenó un modelo real. La procedencia local desconocida de esas fixtures no se convierte en procedencia remota verificada.

| Caso sintético | Filas validadas leídas | Filas emitidas | Exclusión adicional | Target UTC mínimo/máximo (min) |
|---|---:|---:|---|---|
| Válido | 12 | 12 | Ninguna | 10 / 60 |
| Pasajeros ausentes | 12 | 12 | Ninguna; relleno 0 e indicador 1 | 10 / 60 |
| Adelanto DST | 12 | 11 | 1 nonexistent_local_time | 10 / 10 |
| Retraso DST | 12 | 11 | 1 ambiguous_local_time | 130 / 130 |

Todas las salidas: features, target y contexto separados, preprocessor_fitted=false, approved_for_training=false. La whitelist es origen, hora, día de semana, mes, pasajeros e indicador de ausencia; destino deshabilitado. La política sintética de T09 usa resta de reloj local y no se presenta como un gate real calibrado para el target UTC nuevo.

Se comprobó además igualdad de predicciones después de serializar y cargar un Pipeline con DummyRegressor y las doce filas de la fixture válida. Ese ajuste prueba serialización conjunta; no implementa el baseline T15 ni estima desempeño del proyecto.

Artefactos y modelo de juguete únicamente en `.cache/t12-t13-demo`; resumen completo en `.cache/t12-t13-examples.json`, excluidos de Git. Los 24 Parquet reales conservan sus hashes y no se generaron datasets bajo data/validated o data/processed reales.

[Contrato y evidencia T12/T13](../../docs/t12-t13-features.md).
