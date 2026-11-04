# D-04 — Política provisional de calidad aprobada

Fecha: 2026-11-03, America/Costa_Rica. **D-04 V1 RATIFICADA/CONGELADA, CON EXCEPCIÓN HUMANA PUNTUAL DE MARZO.** Los límites y reglas de esta política no cambian. Solo el hash/reporte autorizado de marzo se acepta como VALIDATED_REAL_EXCEPTION, manteniendo FAIL medido y todas las exclusiones. [Excepción](t15-march-exception.md), [evaluación T15 auditada](../reports/quality/t15_baseline_validation.md). El resto describe la política y su evidencia original.

La política candidata se identifica como `d04-real-v1-2026-11-03`. [Versión estructurada de la propuesta](d04-policy-proposal.json), deliberadamente distinta de una configuración ejecutable. [Informe de evidencia](../reports/d04_profile_2024.md), [perfilador reproducible](../scripts/profile_d04.py) y [pruebas del diseño](../tests/unit/test_profile_d04.py).

## 1. Evidencia utilizada

Se seleccionaron **240.000 filas: 20.000 por cada mes de 2024**, de 41.169.720 filas de footer. Muestreo aleatorio sin reemplazo dentro de los 44 grupos Parquet, con cuotas proporcionales, semilla 20241104 y pesos de diseño. La tasa anual estimada pondera grupos/meses por su tamaño; no es conteo completo ni promedio simple de porcentajes mensuales. Las posiciones/hashes están en el JSON local `reports/d04_profile_2024.json`, excluido de Git.

La extracción necesitó decodificar **41.169.471 filas** por la organización de Parquet, manteniendo solo bloques de hasta 65.536 y las filas muestreadas. El límite fue de análisis/memoria, no de decodificación física. Los archivos de 2025 no se abrieron. La primera ejecución tardó 25,55 s; la segunda, con desglose adicional de nulos, 18,47 s y pico RSS **169,17 MiB**; Arrow observó 34,14 MiB de pico en su propio asignador. No deben sumarse esas memorias ni extrapolarse a entrenamiento/Docker. Se repitieron exactamente selección, hashes, métricas comunes y cuantiles.

| Hallazgo | Conteo en muestra | Estimación anual ponderada |
|---|---:|---:|
| Pasajeros nulos | 23.427 | 9,9192 % |
| Metadatos opcionales categóricos nulos | 23.427 | 9,9192 % |
| Horarios ambiguos, pickup o dropoff | 74 | 0,0328 % |
| Duración UTC no positiva | 69 | 0,0285 % |
| Pickup fuera de mes nominal | 5 | 0,0019 % |
| Origen especial 264/265 | 865 | 0,3600 % |
| Destino especial 264/265 | 2.169 | 0,9017 % |
| Pasajeros fuera de 0–6 | 1, con valor 8 | 0,00036 % |
| Timestamps nulos, origen nulo o fuera del catálogo | 0 observados | Sin evidencia de ausencia anual |
| Repeticiones exactas dentro de la muestra | 0 observadas | Tasa del lote no estimable con este muestreo |

Los pasajeros nulos coinciden en la muestra con los nulos de RatecodeID/store_and_fwd_flag. Excluir por esas categorías no predictoras eliminaría muchas filas con origen y etiqueta utilizables. El modelo actual usa pasajeros opcionales, por lo que su ausencia debe conservarse.

La coocurrencia también indica que la ausencia puede depender del proceso de captura y no ser aleatoria. En T17 habrá que evaluar por segmento de pasajeros presentes/ausentes y comprobar su correspondencia con serving; conservar estas filas no demuestra por sí solo que ese patrón se repita en la API.

El esquema de los doce archivos satisface T08. Al preparar esta propuesta ninguno de los 24 archivos tenía manifiesto; el perfilado no los incorporó. Tras la aprobación se registró solamente enero de 2024 como LOCAL_UNVERIFIED. Los 24 hashes originales siguen intactos.

## 2. Comparación del máximo de duración

Se parte de filas con ambos eventos temporales interpretables/sin ambigüedad, duración positiva, pickup en el mes nominal y origen perteneciente al catálogo. No se excluye por destino, categoría opcional nula ni pasajero ausente. No se aplicaron estos filtros a raw: se simularon sobre la muestra.

| Máximo candidato | Exclusiones observadas en muestra | Exclusión anual estimada |
|---|---:|---:|
| Sin máximo | 148 | 0,0632 % |
| 60 minutos | 4.872 | 2,0622 % |
| 120 minutos | 372 | 0,1576 % |
| **180 minutos, recomendado para el MVP** | **278** | **0,1175 %** |
| 240 minutos | 273 | 0,1154 % |
| 360 minutos | 266 | 0,1126 % |
| 1.440 minutos | 150 | 0,0641 % |

El corte de 180 minutos elimina solo cinco filas muestreadas adicionales frente a 240, mientras 60 elimina muchos más casos. No se afirma que los viajes de más de tres horas sean imposibles ni que el corte sea óptimo: es una definición provisional de población de modelado que debe aprobar el equipo. Las métricas futuras deberán declarar las exclusiones y no presentarse como desempeño sobre todos los viajes originales.

Noviembre presenta la mayor exclusión estimada con el candidato de 180: **0,4450 %**, de la cual **0,3700 %** corresponde a ambigüedad DST. Es el comportamiento esperado de la convención temporal ya aprobada: no se adivinan offsets históricos. El máximo mensual de las otras exclusiones conjuntas es 0,1200 % en junio. No se usaron datos de 2025 para escoger estos candidatos.

## 3. Umbrales propuestos de rechazo de lote

Todos los porcentajes de esta tabla usan como denominador **todas las filas raw escaneadas**, antes de excluir o normalizar. Se rechaza al superar el límite; igualdad se tolera. Una fila con varios motivos se cuenta una sola vez en la unión, aunque figure en varios controles individuales. Cada exclusión se reporta incluso si su tasa es inferior al umbral de alerta.

| Control crítico | Acción por fila | FAIL del lote cuando |
|---|---|---:|
| Columnas esenciales ausentes, tipos incompatibles, nombres duplicados | No se procesa | Cualquier caso |
| Hash/manifiesto divergente, lectura/escritura incompleta | No se publica | Cualquier caso |
| Timestamp nulo o no interpretable | Apartar | > 0,10 % |
| Hora local ambigua o inexistente, en cualquier evento | Apartar | > 1,00 % |
| Duración UTC ≤ 0 | Apartar | > 0,50 % |
| Duración UTC > 180 minutos | Apartar | > 1,00 % |
| Pickup fuera del año/mes nominal | Apartar; llegada puede cruzar mes/año | > 0,10 % |
| Origen nulo o fuera del catálogo | Apartar | > 0,10 % |
| **Unión de todas las filas apartadas** | Reportar elegibles y excluidas | **> 1,00 %** |
| Volumen raw mensual | No se publica lote insuficiente | < 1.000.000 filas |
| Volumen mensual elegible | No se publica lote insuficiente | < 990.000 filas |

Alerta global adicional si la unión de excluidas supera **0,50 %**, aunque no llegue a FAIL. Las filas anomalas toleradas siguen generando evidencia de calidad. PASS/WARN del lote requiere además integridad, política aprobada y publicación completa; una muestra compatible con estos límites no demuestra que un lote los supere.

Los límites de tasas son **márgenes operativos propuestos**, no umbrales publicados por TLC ni límites estadísticos derivados automáticamente de cuantiles. El peor mes muestreado con este perfil queda por debajo de 0,50 %, pero ese margen deberá comprobarse con conteos completos del piloto. Los mínimos de volumen son guardas provisionales amplias frente al rango observado de 2.964.624–3.833.771 filas mensuales de 2024; no son el tamaño de train ni autorizan entrenar millones de filas.

Se propone además WARN si el volumen de un lote está fuera de **0,5–2,0 veces** el footer del mismo mes de 2024. No se fija máximo crítico de volumen: crecimiento no acredita corrupción. El presupuesto de procesamiento/modelado se resuelve aparte con D-02.

## 4. Zonas, pasajeros, categorías y duplicados

| Control | Propuesta de tratamiento | Umbral de alerta |
|---|---|---:|
| Origen 264/265 | Conservar como categorías especiales distintas y reportar segmentos | > 1,00 % del lote |
| Destino nulo o fuera de catálogo | Medir; no excluir filas por un predictor deshabilitado | Cualquier caso |
| Pasajero ausente | Conservar; relleno 0 + indicador de ausencia en features | > 20,00 % después de normalizar |
| Pasajero cero | Conservar como cero informado, distinto de ausente | Conteo informativo |
| Pasajero negativo o > 6 | Normalizar a ausente, conservando motivo y conteo | > 0,10 % normalizado |
| Categorías opcionales nulas/no documentadas | Medir; no usarlas como predictors ni excluir | Cualquier caso |
| Repeticiones exactas | Medir el lote completo, conservar filas | Cualquier coincidencia |

Estas alertas aisladas **no rechazan el lote**. El rango 0–6 de pasajeros es una convención operativa candidata, no una afirmación de capacidad legal ni prueba de que el valor 8 observado sea erróneo. La alternativa 0–8 normalizaría cero filas de esta muestra; se presenta 0–6 con normalización, sin eliminar el viaje, para mantener la entrada opcional y documentar la incertidumbre.

Conservar zonas especiales evita añadir exclusiones por una categoría que ya figura en el catálogo. Excluir ambas aumentaría la exclusión conjunta anual estimada de **0,1175 % a 0,4740 %**. Aceptarlas como categorías gruesas no implica disponer de una zona geográfica precisa; T17 deberá reportar esos segmentos cuando haya soporte. La presencia de DOLocationID como columna estructural sigue requerida por T08, aunque sus valores no deciden elegibilidad del modelo v1.

No se propone deduplicación automática: igualdad de las diecinueve columnas no establece una identidad única de viaje. Cero duplicados entre 240.000 filas seleccionadas no permite fijar una tolerancia anual ni afirmar que el lote completo carece de ellos. La medición exacta completa requerirá disco temporal y deberá dimensionarse en el piloto.

Catálogo candidato: [CSV guardado](reference/taxi_zone_lookup_candidate.csv), [origen/hash de descarga](reference/taxi_zone_lookup_candidate.source.json), enlazado por [TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Son 265 registros; 264 está identificado como desconocido y 265 como fuera de NYC. Snapshot descargado el 2026-11-03, SHA-256 `1a99e105092230f8620f301edcca7f80d3080642ff404d28ed957d3fa222c8ed`. Este snapshot fue aprobado como referencia operativa dentro de la política; no se afirma que su vigencia exacta en 2024 haya sido probada independientemente. El nombre de archivo candidate se conserva para mantener la referencia original.

Las categorías no predictoras contrastadas con el [diccionario TLC](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf) son VendorID 1/2/6/7, RatecodeID 1–6/99, payment_type 0–6 y store_and_fwd_flag Y/N. Un null no se confunde con un código no nulo fuera del diccionario; se observó lo primero, sin ejemplos de lo segundo en esta muestra.

## 5. Procedencia y activación

La autorización inicial de enero fue ampliada explícitamente por el usuario a los 24 archivos actuales, con mes/SHA individual en la configuración. La preparación posterior registró 15 lotes, aprobó calidad/features de 14 y rechazó marzo de 2025; nueve lotes siguen sin incorporar. LOCAL_UNVERIFIED, UNVERIFIED_LOCAL y URL/fecha de descarga nulas se conservan. La autorización de uso no anula un rechazo de calidad ni acredita la descarga histórica. [Estado vigente](t14-t15-quality-blocker.md).

El perfil real implementado calcula duración UTC, aparta horarios ambiguos/inexistentes, normaliza pasajeros y comprueba procedencia, integridad y exhaustividad. Solo publica el marcador final tras superar los controles. data_quality_approved y approved_for_training son campos independientes: el primero es true en el piloto y el segundo sigue false. No se han construido features reales ni entrenado modelos.

## 6. Verificación

La preparación inicial pasó 237 pruebas, incluidas diez del perfilador. La implementación aprobada pasó **255 pruebas** tanto en desarrollo como desde wheel instalado en el segundo entorno, sin src/data en la copia de pruebas. Ruff y comprobaciones de integridad sin errores. Enero se recorrió completo: 2.964.624 filas, 2.871 excluidas, 2.961.753 elegibles y 60 normalizaciones. El detalle de severidades, recursos y auditoría está en [activación](d04-activation.md) y [reporte del piloto](../reports/quality/pilot_2024_01.md).

La configuración efectiva está en [data.yaml](../configs/data.yaml). D-04 ratificada/congelada y D-01/D-02 aprobadas según el [protocolo](d01-d02-protocol.md). La implementación de controles de entrenamiento y autorización de tareas posteriores siguen pendientes. No se instalaron dependencias nuevas durante la activación.
