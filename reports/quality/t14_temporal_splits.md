# Evidencia T14 — particiones temporales

Fecha: 2026-11-03. Ejecución exclusivamente sintética: **SPLIT_TEST_ONLY**. [Contrato y límites](../../docs/t14-temporal-splits.md). No es entrenamiento ni procesamiento de los datos TLC reales.

Intento `99520bb8d2124cd7ab2cd8a65f9308f2`, catálogo y artefactos bajo `.cache/t14-evidence/6844294b59d842f49b4ae91df46bb6b9`. Registro local de observaciones: `.cache/t14/evidence.json`.

| Resultado | Filas |
|---|---:|
| Entradas de 24 meses sintéticos | 288 |
| Excluidas por etiqueta al corte o posterior | 4 |
| train | 143 |
| validation | 35 |
| test | 35 |
| monitoring_replay | 71 |

Se conservaron 284 de 288 filas: no se muestreó. Las cuatro exclusiones están identificadas en el manifiesto por feature_id/índice/motivo. Las tres tablas de cada partición conservan alineación. El reporte declara cobertura de los 24 meses, ámbito TEST_ONLY y ninguna aprobación de entrenamiento.

## Integridad y recursos observados

- Los 24 raw originales mantienen tamaño/SHA; solo enero de 2024 tiene manifiesto y validación. No se registraron ni validaron los otros 23.
- Cero lotes reales de features y cero filas reales decodificadas durante T14. No hay modelos ni entrenamiento nuevos.
- RAM libre observada: 10,689,441,792 bytes (9.96 GiB), inferior a 12 GiB. Disco libre: 320.17 GiB, superior a 50 GiB. Son medidas volátiles.
- La ejecución REAL está pendiente de entradas completas y recursos; no se presenta como realizada.

## Verificación ejecutada

- Desarrollo: **287 pruebas aprobadas**, incluidas 32 nuevas de T14. Ruff check/format y pip check sin errores.
- Repeticiones con catálogo invertido y diferentes tamaños de bloque producen los mismos SHA lógicos y conteos, para versiones de entrada fijas.
- Fallos por datos alterados, mutación durante escaneo, RAM/disco insuficientes, exceso de RSS y publicación fallida no producen marcador completo.
- Wheel construido sin red/dependencias nuevas e instalado en .venv-verify. Copia de tests/scripts/configs/pyproject sin src/data: **287 pruebas aprobadas** desde el paquete instalado; imports aislados de 19 módulos y CLI/help incluidos. pip check sin conflictos en ambos entornos. Wheel local: .cache/t14-dist/nyc_yellow_taxi_mlops-0.1.0-py3-none-any.whl.

No se midió tiempo/RAM de aprendizaje incremental ni se implementaron controles de candidatos T16. Los ejemplos no certifican Docker ni rendimiento sobre 89,89 millones de filas reales.
