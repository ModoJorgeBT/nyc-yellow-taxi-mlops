# T14 — Particiones temporales completas por bloques

Fecha inicial: 2026-11-03; actualización: 2026-11-05, America/Costa_Rica. T14 tiene cierre técnico auditado sobre los 24 meses y cuatro particiones. T15 permanece congelada y coincide con el nuevo train/validation. [Evidencia integral](../reports/quality/t14_completion.md). Test/replay se leyeron para calidad, preparación y auditoría; aún no se usaron para métricas predictivas.

## Contrato y decisiones

Se consumen las decisiones [D-01/D-02/D-04 aprobadas](d01-d02-protocol.md). [model.yaml](../configs/model.yaml) es JSON compatible con YAML, sin dependencias adicionales. Contiene periodos, modo de replay, presupuesto y fingerprint de las reglas congeladas de calidad; excluye autorizaciones variables y fecha/responsable de aprobación de ese fingerprint. La whitelist efectiva de archivos sigue en [data.yaml](../configs/data.yaml).

| Partición | Recogida en America/New_York, intervalo [inicio, fin) |
|---|---|
| train | 2024-01-01 a 2025-01-01 |
| validation | 2025-01-01 a 2025-04-01 |
| test | 2025-04-01 a 2025-07-01 |
| monitoring_replay | 2025-07-01 a 2026-01-01 |

Cada etiqueta debe tener evento de llegada UTC estrictamente anterior al fin de su partición. Igualdad o cruce del corte se aparta como label_not_available_at_cutoff, sin trasladar la fila a otra partición. Se contabilizan todas las entradas, conservadas y excluidas, con hasta diez ejemplos de identidad/motivo. No se realiza submuestreo ni split aleatorio. Es replay retrospectivo por evento, no prueba de disponibilidad histórica de publicación TLC.

El código no ajusta transformaciones ni modelos. No calcula métricas predictivas ni utiliza test/replay para seleccionar parámetros. Leer estos lotes para integridad y partición no autoriza explorarlos para ajustar el modelo.

## Entradas explícitas y linaje

El [CLI](../src/training/split.py) recibe un catálogo JSON versionado, sin glob ni selección automática de la versión más reciente. Cada entrada declara año/mes, directorio de features T13 y directorio validated T10 asociado. Rutas relativas se resuelven respecto del catálogo, no del directorio de trabajo.

```json
{
  "format_version": 1,
  "batches": [
    {
      "year": 2024,
      "month": 1,
      "features_directory": "RUTA_LOTE_FEATURES",
      "validated_directory": "RUTA_LOTE_VALIDATED"
    }
  ]
}
```

El ejemplo muestra la estructura; **REAL requiere exactamente los 24 meses**, sin repetir mes ni validación. Un catálogo parcial falla antes de leer filas. No se aceptan raw, lotes sin marcador, mezcla de ámbitos, artefactos alterados o features ajustadas. TEST_ONLY admite un subconjunto explícito con hasta 65.536 filas totales y metadata sintética; nunca representa aprobación de datos reales, aunque cubra los 24 meses con fixtures.

Se verifican marcadores/hash/esquema/conteo de las tres tablas T13 y la validación de origen. REAL exige perfil D-04 congelado y autorización vigente del mes/hash raw. Se vuelven a verificar las entradas después del escaneo. Los índices validated deben ser únicos, crecientes y dentro de rango; REAL exige cobertura contigua. Se contrasta target con eventos UTC y calendario con contexto. Ante discrepancia se rechaza el intento.

## Salidas, cobertura y reproducibilidad

Se publican tres Parquet por partición: features conserva solo la whitelist de X, target solo duración y context conserva índices/eventos más source_feature_id. El manifiesto enlaza cada feature_id con validación y SHA raw. El orden es mes ascendente y posición de origen; no se presupone que las recogidas estén ordenadas dentro de cada archivo.

Las tablas se escriben alineadas por bloques, sin concatenar el histórico completo ni construir la matriz one-hot de todos los años. Se informa rango temporal por partición, conteos exhaustivos y SHA lógico independiente del tamaño de bloque, para las mismas versiones explícitas de entrada. El SHA físico puede cambiar al variar row groups; el identificador del intento también cambia.

Destino normal: data/processed/splits/id; sintético: data/processed/splits/_test_only/id. split_manifest.json se publica al final, con publication_complete=true. Los archivos aislados no son una partición completa. Cada intento deja reporte en reports/splits, aislado bajo _test_only cuando corresponde; fallo devuelve código 1. No se reemplazan intentos previos; una interrupción durante publicación puede dejar archivos huérfanos sin marcador final.

SPLIT_REAL significa particionado real terminado; no concede aprobación de fit. Todos los marcadores/Parquet conservan approved_for_training=false y preprocessor_fitted=false en el reporte. T15/T16 deberán comprobar artefactos y autorización de su ejecución. El código no promueve modelos.

## Recursos e interrupciones

[resources.py](../src/training/resources.py) mide memoria libre, pico RSS y disco sin psutil ni dependencias nuevas. Tras la aprobación específica para preparación/T15, REAL usa preflight de 4 GiB RAM libre y 50 GiB disco libre; supervisa pico RSS ≤2 GiB y reserva de disco entre bloques. El perfil original de candidatos T16 conserva 12 GiB libres/8 GiB RSS. Lectura Arrow secuencial y threadpool limitado a cuatro hilos; un lote a la vez. Los escritores/temporales propios se cierran y limpian ante error controlado.

Esta supervisión es cooperativa entre bloques, no un límite duro del SO. Una interrupción no recuperable puede dejar temporales que requieren inspección. La lectura Linux contempla /proc y memoria disponible de cgroup v2; Docker/Linux no se certificó con estas pruebas Windows. T24 deberá verificar la adaptación operativa de los perfiles antes de ejecutarlos allí.

El presupuesto de dos horas es por candidato y se conserva en configuración, pero su temporizador pertenece a T16: en T14 no hay candidatos en ejecución. Las fixtures omiten el preflight real explícitamente; las pruebas inyectan estados bajos/excesos para verificar fallos sin requerir 12 GiB en CI. Ningún exceso reduce datos automáticamente.

## Verificación y evidencia

Suite de desarrollo: **287 pruebas aprobadas**, 32 nuevas de T14. [Unitarias](../tests/unit/test_temporal_split.py) y [de integración](../tests/integration/test_temporal_split_pipeline.py): fronteras exactas, UTC/DST, etiquetas que cruzan corte, cobertura, orden y hashes lógicos, alineación, integridad, cambios durante escaneo, rechazo de catálogos incompletos, recursos, publicación fallida y CLI instalado. Ruff sin errores. Segundo entorno con wheel instalado y copia sin src/data: **287 pruebas aprobadas**, importación aislada de 19 módulos y CLI/help. pip check sin errores en ambos entornos.

```powershell
.\.venv\Scripts\python.exe -m src.training.split --help
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-t14-final -o cache_dir=.cache/pytest-cache-t14-final
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

Uso normal, una vez disponibles los 24 lotes de features validados y recursos:

```powershell
.\.venv\Scripts\python.exe -m src.training.split --inputs RUTA_CATALOGO_JSON --config configs/model.yaml
```

En la entrega inicial solo se ejecutó la [demostración sintética](../reports/quality/t14_temporal_splits.md): 24 fixtures, 288 filas, cuatro exclusiones por corte, 284 conservadas. Después se prepararon 14 meses reales y marzo 2025 falló D-04; no se publicaron particiones reales. El bloqueo actual es de calidad, no falta de aprobación del baseline/perfil de recursos. [Estado actual](t14-t15-quality-blocker.md).
## Ajuste independiente T15 posterior

El usuario autorizó ajustar solo train antes de T14 completa, sin publicar una T14 parcial como completa. Ajuste exacto train 2024 completo y auditado: 41.119.495 etiquetas, mediana 12,983333 minutos; 561 filas apartadas por corte de etiqueta entre 41.120.056 elegibles DQ. Evaluación y cierre de T14/T15 pendientes de marzo 2025; D-04 permanece congelada. [Artefacto provisional](../reports/quality/t15_train_fit.md). El CLI completo de T14 conserva la exigencia de los 24 meses aprobados.
