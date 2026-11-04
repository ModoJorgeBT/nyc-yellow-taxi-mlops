# T12/T13 — Target, whitelist y transformaciones compartidas

Fecha: 2026-11-03, America/Costa_Rica. T12/T13 solicitadas por el usuario; decisiones consultadas y aprobadas tras revisar el diccionario oficial. Implementación verificada técnicamente con fixtures para revisión humana. Estado histórico de esta entrega: D-04 pendiente. Actualización posterior: [D-04 aprobada e implementada](d04-activation.md), lector REAL probado y piloto enero validado sin extraer features reales. Actualización adicional: [D-01/D-02 aprobadas](d01-d02-protocol.md), con todos los elegibles y modelos incrementales; controles de ejecución pendientes; no se entrenan modelos reales ni se ejecuta T14/T16.

## Decisiones aprobadas y fuente

Se leyó completo el [diccionario oficial TLC](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf), una página fechada el 18 de marzo de 2025. Distingue la zona de inicio del taxímetro de la zona final observada y describe pasajeros sin indicar cuándo se capturó su conteo. Define los eventos de activación/desactivación, pero no establece zona horaria ni reglas DST. RatecodeID corresponde al código final. El diccionario no prueba destino declarado al inicio ni garantiza la semántica horaria adoptada por este proyecto.

Después de esa revisión el usuario aprobó:

- **Whitelist v1:** origen, hora/día de semana/mes de recogida y pasajeros opcionales. Se asume expresamente que el conteo puede conocerse al abordar; si falta, se representa su ausencia. Destino deshabilitado. No se aprueba usar DOLocationID histórico como destino declarado.
- **Tiempo:** interpretar históricos sin zona en America/New_York; apartar horarios ambiguos/inexistentes con motivo, sin adivinar fold; duración entre instantes convertidos a UTC. Inferencia con offset obligatorio, calendario local de Nueva York.
- **Dependencias:** scikit-learn, tzdata y sus dependencias necesarias, versiones/hashes fijados y pruebas de Pipeline con fixtures. Sin pandas, MLflow ni FastAPI nuevos.

Esto resuelve la selección actual y la convención temporal de D-06. Catálogo/rangos y contrato REST completo siguen pendientes. Reintroducir destino requiere una nueva decisión explícita.

## Componentes y contrato

| Archivo | Responsabilidad |
|---|---|
| [schema.py](../src/features/schema.py) | PredictionInput inmutable, validación de entrada y whitelist exacta. |
| [target.py](../src/features/target.py) | Localización histórica sin ambigüedad y duración positiva en minutos UTC. |
| [build.py](../src/features/build.py) | Transformador compartido, Pipeline sin ajustar, adaptador histórico y CLI. |
| [artifacts.py](../src/features/artifacts.py) | Verificación de artefactos T10 y publicación aislada de features/target/contexto. |

Entrada compartida: `pickup_datetime` con offset, `pickup_location_id` entero positivo, `passenger_count` entero no negativo o ausente/null. Bool no se acepta como entero. El contrato de entrada inicial comprueba tipos y no impone catálogo/máximo real. D-04 posterior normaliza pasajeros históricos fuera de 0–6 y aprueba catálogo de calidad; T20/D-06 deberán alinear el contrato REST con ese tratamiento antes de servir. No hay API implementada. La entrada de inferencia rechaza cualquier campo adicional, incluidos destino, target, llegada, importes, distancia y RatecodeID. No se implementa todavía una API FastAPI.

Features semánticas, en orden: `pickup_location_id`, `pickup_hour` (0–23), `pickup_weekday` (lunes=0), `pickup_month` (1–12), `passenger_count`, `passenger_count_missing`. Un pasajero ausente produce valor de relleno 0 e indicador 1; el cero informado conserva indicador 0. Esta imputación constante no aprende estadísticas de validación/test. Pasajeros negativos se apartan con motivo, no se convierten a cero.

El adaptador histórico selecciona solo timestamps de etiqueta, origen y pasajero opcional. Puede leer una tabla con columnas históricas adicionales, pero no las incorpora a X. El destino no es una columna requerida para construir features; el gate estructural raw de T08 conserva su contrato aprobado de cuatro esenciales por separado. El target siempre se recalcula desde los eventos; una columna preexistente de duración no se reutiliza.

El Pipeline une extracción de calendario con OneHotEncoder de origen (`handle_unknown=ignore`) y numéricas float32. El vocabulario se ajusta con las filas entregadas a fit; transformar una zona no vista no amplía columnas. El llamador de T14 deberá ajustar exclusivamente train: esta librería no decide las particiones ni acredita que un conjunto llamado train lo sea. La salida es densa por compatibilidad con los estimadores propuestos; D-02 debe dimensionarla antes de datos grandes.

`make_model_pipeline(estimator)` clona el estimador y lo une al preprocesador sin fit. La prueba de serialización guarda/carga ambos juntos con joblib y comprueba features/predicciones iguales. Solo utiliza un DummyRegressor sobre fixtures como comprobación de infraestructura, sin implementar el baseline T15 ni seleccionar candidatos. Cargar joblib se limita en las pruebas al archivo local confiable que ellas mismas crearon.

## Tiempo y prevención de leakage

La localización intenta ambos folds y comprueba ida/vuelta UTC. Cero instantes válidos implica hora inexistente; dos instantes distintos, hora ambigua. Ambos casos se apartan explícitamente. Las entradas con offset ya identifican un instante: se convierten a Nueva York para obtener calendario.

Se carga directamente la base IANA de tzdata fijada, incluso si Linux tiene otra versión del sistema. La versión y la política temporal quedan en el manifiesto de features. Ejemplos sintéticos verificados: adelanto 2024-03-10 01:55→03:05 = 10 minutos; retraso 2024-11-03 00:55→02:05 = 130 minutos. Las horas ambiguas intermedias no se resuelven suponiendo DST arbitrariamente.

Target y contexto quedan fuera de las features. El contexto guarda recogida UTC y evento final de etiqueta UTC; **el evento final no acredita disponibilidad/publicación del lote**. D-01/T14 deben definir replay y maduración de etiquetas. No se ajustan agregados, imputadores estadísticos ni categorías con datos posteriores.

La validación T09 existente conserva su política sintética naive_wall_clock; no se modifica retrospectivamente el EDA ni sus resultados. En fixtures que cruzan DST, su diferencia de reloj y el target UTC pueden diferir. D-04 posterior aprobó e implementó controles reales coherentes con UTC y sus tolerancias. El piloto inicial aprobó solo enero de 2024; posteriormente se autorizaron 24 hashes y la preparación T14/T15 completó 14 meses antes del rechazo de marzo de 2025. [Estado vigente](t14-t15-quality-blocker.md). La aprobación temporal o de uso por sí sola no acredita calidad ni entrenamiento de otros lotes.

## Frontera de archivos y CLI

El lector exige directorio de lote explícito, data.parquet y validation.json de T10. Verifica modo REAL o TEST_ONLY solicitado, aprobación de entrenamiento false, identidad, metadata, configuración, conteos, hash y esquema. REAL exige data_quality_approved=true, política temporal y autorización de origen coherentes, y no admite exclusiones adicionales respecto del lote ya aprobado. Vuelve a comprobar marcador/contenido al terminar. Rechaza raw sin marcador, artefactos modificados, validación incompleta y mezcla de modos. El marcador es una declaración local de la ejecución, no una firma ni prueba externa de procedencia.

TEST_ONLY está limitado a fixtures, hasta 65.536 filas por lote. REAL lee el lote explícito aprobado por bloques (predeterminado 2.048), sin concatenar meses; soporte verificado con fixtures tras D-04. No se ha ejecutado extracción sobre el piloto real. El índice de contexto se refiere a la entrada validada compactada, no a la posición original de raw.

```text
data/processed/_test_only/YYYY/MM/<feature_id>/
    features.parquet
    target.parquet
    context.parquet
    features_manifest.json
```

Las tres tablas mantienen alineación posicional. Las exclusiones adicionales y hasta diez ejemplos de motivos se registran en el manifiesto. Si no queda ninguna fila, se falla indicando motivos sin publicar dataset. La construcción de estos archivos **no ajusta el preprocesador**; `preprocessor_fitted=false` impide confundir extracción determinista con un fit anterior al split. Todas las salidas conservan `approved_for_training=false` y metadata del modo REAL o TEST_ONLY. Salidas REAL usan processed/YYYY/MM/id; TEST_ONLY permanece en processed/_test_only.

Staging y publicación sin reemplazo reutilizan el mecanismo de T10. El manifiesto se publica al final: tres Parquet sin ese marcador son un resultado incompleto. No hay una transacción atómica conjunta; un fallo de marcador puede dejar archivos huérfanos para inspección. No se borran resultados publicados ni se ofrece reemplazo. No se garantiza tolerancia a modificaciones hostiles que ignoren las verificaciones del proceso local.

```powershell
.\.venv\Scripts\python.exe -m src.features.build --help
# Sustituir la ruta por el directorio explicito devuelto por T10 en una prueba:
.\.venv\Scripts\python.exe -m src.features.build --validated-batch "RUTA_LOTE_TEST_ONLY" --processed-dir .cache/features-demo --test-only
```

El CLI congela `--validated-batch`, `--processed-dir`, `--batch-size` y `--test-only`; reemplaza el ejemplo preliminar por año/mes, que no identificaba una versión única validada. Devuelve JSON y código 0 ante éxito; código 1 ante rechazo/error, 2 para sintaxis inválida. Los errores no conceden aprobación ni producen un manifiesto de éxito.

## Entorno y pruebas

Extra `features` en pyproject.toml: scikit-learn 1.9.1 y tzdata 2026.6. Lock completo: 23 paquetes con hashes; conserva las 15 versiones anteriores y añade NumPy 2.5.4, SciPy 1.18.1, joblib 1.6.0, threadpoolctl 3.7.0, cloudpickle 3.1.2 y narwhals 2.28.0 además de los dos directos. Los dos últimos son dependencias transitivas resueltas, no tecnologías principales elegidas para el proyecto. Descarga solo de wheels e instalación offline con verificación de hashes. Compatibilidad declarada por [PyPI scikit-learn](https://pypi.org/project/scikit-learn/1.9.1/) y [tzdata](https://pypi.org/project/tzdata/2026.6/); la ejecución local es la evidencia de compatibilidad real del entorno.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-t12-t13-full2 -o cache_dir=.cache/pytest-cache-t12-t13-full2
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Resultado de desarrollo: **227 pruebas aprobadas**, 65 nuevas. [Unitarias](../tests/unit/test_features.py) y [de integración](../tests/integration/test_feature_pipeline.py): whitelist, información futura que no cambia X, target recalculado, pasajeros opcionales, DST, histórico/serving, vocabulario train, serialización conjunta, consumo seguro de T10, alineación, mutación de archivos, publicación incompleta y CLI. La aprobación de T12/T13 no cierra D-01/D-02/D-04 ni habilita entrenamiento real.

## Auditoría final

- Lock de 23 paquetes instalado con hashes desde wheels locales en `.venv` y en el segundo entorno existente `.venv-verify`; `pip check` sin conflictos. La resolución inicial fue bloqueada por red del sandbox y se repitió con permisos de red; no se atribuye ese fallo a incompatibilidad de versiones.
- Wheel construido sin red/resolución de dependencias con `pip --isolated wheel --no-deps --no-build-isolation --no-index --wheel-dir .cache/t12-t13-dist .` e instalado sin dependencias en `.venv-verify`.
- Copia tests/scripts/configs/pyproject a `.cache/t12-t13-checkout`, sin src ni data: **227 pruebas aprobadas** desde el paquete instalado, incluidos CLI en subprocess aislados e importación de dieciséis módulos. Esta es una prueba local de empaquetado, no de Docker ni de otro equipo.
- Ruff sin errores, 33 archivos ya formateados. Los tests del modelo de juguete solo serializan/cargan su propio archivo confiable; no hay un modelo champion ni pipeline de entrenamiento real.
- Cuatro [ejemplos ejecutados](../reports/quality/features_t12_t13.md): válido, pasajeros ausentes y ambas transiciones DST. JSON/artefactos en `.cache/t12-t13-demo` y `.cache/t12-t13-examples.json`, sin versionar binarios.
- 24 hashes raw iguales al inventario original, cero manifiestos/eventos/locks/temporales nuevos en raw real, cero datasets en validated/processed reales, PDF académico intacto. No se decodificaron filas reales de 2025.
- Verificación de Markdown/enlaces locales ejecutada; referencias históricas de fases anteriores conservadas como evidencia de su fecha. Configuración real data.yaml sin cambios. T12/T13 quedan locales sin nuevo commit/push para revisión humana; T14/T16 sin implementar.
