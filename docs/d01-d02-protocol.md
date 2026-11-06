# D-01/D-02 — Periodos y ejecución con todos los registros

Fecha: 2026-11-03. **D-01 APROBADA. D-02 APROBADA para ejecución incremental con todos los datos elegibles. D-04 ratificada y congelada para v1.** Registro estructurado: [protocolo documental](d01-d02-execution-protocol.json), con configuración ejecutable derivada en [model.yaml](../configs/model.yaml) tras implementar T14; el JSON documental no se consume directamente. El cierre inicial fue documental. T14 se implementó posteriormente con fixtures; no se entrenó ni se ejecutaron particiones reales.

## D-01: distribución aprobada

El usuario aprobó sustituir la propuesta académica inicial de periodos por esta distribución de los datos existentes:

| Uso | Periodo de recogida en America/New_York | Filas raw declaradas por footers |
|---|---|---:|
| Entrenamiento | 2024-01-01 incluido a 2025-01-01 excluido | 41.169.720 |
| Validación y selección | 2025-01-01 incluido a 2025-04-01 excluido | 11.198.026 |
| Test final reservado | 2025-04-01 incluido a 2025-07-01 excluido | 12.885.358 |
| Monitoreo mediante replay | 2025-07-01 incluido a 2026-01-01 excluido | 24.639.218 |

Los conteos no son tamaños elegibles: faltan calidad y cortes de disponibilidad de etiquetas para los otros meses. El EDA previo y la definición de D-04 usaron solamente 2024, ahora dentro de train. No se exploraron filas de 2025 para elegir umbrales o modelos. La columna cbd_congestion_fee, presente en el esquema 2025, sigue fuera de X.

El protocolo es **replay retrospectivo por tiempo de evento**. No certifica que los archivos TLC estuvieran publicados al momento histórico de predicción. Las fechas reales de descarga/publicación no están verificadas; no se sustituyen por fechas inventadas. 2026 deja de ser requisito para esta demostración; un lote posterior exigiría nueva autorización.

## Cortes y controles contra leakage

La partición se decide por recogida localizada, con intervalos [inicio, fin), no mediante split aleatorio. Por la condición de disponibilidad de etiquetas ya exigida en T14, solo se incorporan al conjunto evaluable en cada corte filas cuyo evento de llegada UTC sea anterior al corte correspondiente. Una fila que atraviesa el corte se aparta con motivo y conteo, sin moverla a otra partición. Fechas ambiguas/inexistentes y duración no positiva o superior a 180 minutos siguen D-04.

Los cortes locales equivalen a 2025-01-01 05:00Z, 2025-04-01 04:00Z y 2025-07-01 04:00Z. El fin del replay es 2026-01-01 05:00Z; las ventanas mensuales futuras deberán documentar cuándo sus etiquetas están maduras. La disponibilidad por evento es una convención del replay, distinta de disponibilidad por publicación.

Preprocesador, vocabulario, normalización aprendida y baseline se ajustan únicamente con train. Validación permite elegir hiperparámetros/modelo; después se congelan antes de abrir el test. No se hace refit con test ni se usa su resultado para modificar filtros/umbrales. Los meses de replay no participan en la selección inicial. Referencia de drift, ventanas de retraining y promoción siguen pendientes de D-05 y sus tareas.

T14 debe probar fronteras exactas, viajes que cruzan corte, conversión UTC/DST, ausencia de solapamiento, conservación de conteos y rechazo de datos no aprobados. El cierre documental de D-01 no declara implementada esa partición.

## D-02: requisito confirmado y viabilidad

El usuario rechazó los topes de 500.000/100.000/100.000 y pidió **todos los registros**. Se documenta como todas las filas elegibles de cada partición tras D-04 y los cortes causales, sin submuestreo de modelado ni reducción automática al exceder recursos. Calidad recorre los lotes completos antes de cualquier entrenamiento. El muestreo anterior fue EDA, no una autorización de muestrear train.

Observación de solo lectura del host: 12 CPU lógicas, 33.970.917.376 bytes de RAM total (31,64 GiB), 10.662.636 KiB libres (10,17 GiB) y 343.830.917.120 bytes de disco libres (320,22 GiB). La memoria/disco libres cambian con el uso. WSL está en PATH; Docker no se encontró en PATH en esta sesión, lo que no prueba ausencia de toda instalación. No se instaló ni configuró infraestructura.

El preprocesador actual usa OneHotEncoder denso float32: [build.py](../src/features/build.py). Con 265 categorías posibles de origen y cinco columnas numéricas, el escenario de 41.169.720 filas × 270 columnas × 4 bytes requiere **44.463.297.600 bytes (41,41 GiB)** solo para X, antes de copias, targets, árboles o buffers. Es un cálculo de escenario, no una asignación medida ni un conteo de categorías efectivamente presentes en train. Demuestra que no puede aprobarse ese escenario como viable dentro de 8 GiB o de la RAM total actual.

El piloto de enero midió 256,26 MiB RSS y 1,480 GiB temporales para calidad, con bloques de hasta 65.536. No es evidencia del coste de entrenar modelos ni certifica un plazo para 2024 completo. No se extrapola el tiempo linealmente a un modelo.

### Presupuesto revisado aprobado

| Parámetro | Perfil aprobado |
|---|---|
| Datos | Todas las filas elegibles de los periodos aprobados; sin muestreo de modelado |
| Estrategia / candidatos | Entrenamiento incremental: SGDRegressor y MLPRegressor pequeño, en scikit-learn ya instalado |
| Concurrencia | Un modelo a la vez, hasta cuatro hilos totales, sin paralelismo anidado |
| RAM del proceso | Límite objetivo 8 GiB, instrumentado y comprobado antes de entrenar |
| Tiempo por candidato | Hasta 2 horas; exceder detiene el intento, sin publicar modelo completo |
| Preflight | Al menos 12 GiB RAM libre y 50 GiB disco libre |
| Calidad | Un mes a la vez, máximo 65.536 filas por bloque; medición de disco temporal |
| Exceso de recursos | Detener, reportar y revisar; no cambiar datos, algoritmos ni presupuesto silenciosamente |

Con los 10,17 GiB libres observados, el preflight propuesto de 12 GiB no pasaría hasta liberar memoria. Es una condición operativa, no una medición de fallo del entrenamiento, que no se ha ejecutado.

La documentación oficial identifica SGDRegressor y MLPRegressor como regresores aptos para aprendizaje fuera de memoria mediante partial_fit: [estrategias de escalado](https://scikit-learn.org/stable/computing/scaling_strategies.html), [SGDRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.SGDRegressor.html), [MLPRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.neural_network.MLPRegressor.html). Se verificó también su presencia en la versión instalada. Esto permite proponer dos familias de modelo, sin garantizar rendimiento predictivo o tiempo de ejecución.

El usuario aprobó explícitamente sustituir los candidatos de ejemplo por SGDRegressor y MLPRegressor pequeño, utilizando scikit-learn ya instalado. No se interpretará warm_start de un bosque o boosting como garantía de aprendizaje incremental equivalente sobre todos los bloques. No basta con leer Parquet por bloques si después se concatena toda la matriz densa para fit.

Una implementación incremental necesitará ajustar/fijar el preprocesador solo con train, controlar las pasadas y el orden por bloques, y serializarlo junto al estimador para inferencia. MAE/RMSE pueden acumularse por bloques; mediana, MedAE y P90 completos requieren un método exacto de disco u otra política aprobada, no promediar percentiles de bloques. Los números de épocas, arquitectura de la red, escalado y búsqueda de hiperparámetros se concretarán en sus tareas, dentro del presupuesto aprobado.

Los límites son un contrato aprobado, todavía sin controles de entrenamiento implementados ni mediciones de un fit real. Antes de usar todos los datos se deberán ensayar interrupción por RAM/tiempo/disco, limpieza segura de temporales, reportes de fallo y una comprobación de recursos. Si se agota el presupuesto antes de completar la cobertura de train aprobada, no se publicará un candidato como si hubiera usado todos los datos. Docker/Compose se verificarán en T23–T25; no se declara ese entorno disponible por cerrar un presupuesto de ejecución nativa.

## D-04: autorización ampliada y política congelada

El usuario ratificó la política inicial y autorizó uso académico de **los 24 archivos actuales**, por año/mes y SHA individual. La whitelist está en [data.yaml](../configs/data.yaml); el [registro estructurado de D-04](d04-policy-proposal.json) refleja la misma lista. Se comprobaron de nuevo tamaño y SHA de los 24 originales y footers, sin decodificar filas adicionales.

Esta ampliación permite preparar su incorporación en tareas posteriores. **Solo enero de 2024 está registrado y validado.** Los otros 23 no tienen manifiesto ni calidad aprobada. No se ejecutó registro, validación masiva, extracción de features reales ni entrenamiento en esta revisión. LOCAL_UNVERIFIED conserva URL/fecha de descarga nulas. La autorización no convierte los otros 23 lotes en VALIDATED_REAL.

Se conservan todos los límites de duración/tasas/volumen, catálogo, categorías y tratamiento de pasajeros de la política aprobada. El JSON de configuración cambia por el alcance de autorización y por tanto cambia su fingerprint; el reporte de enero conserva su configuración original, hash y autorización de aquel intento. No se reescribe la evidencia histórica para fingir que enero se ejecutó con autorización de 24 meses.

Evidencia: [activación original](d04-activation.md), [política](d04-quality-proposal.md), [piloto completo](../reports/quality/pilot_2024_01.md). Aprobar calidad y aprobar entrenamiento continúan siendo estados diferentes. Las decisiones D-01/D-02/D-04 de G0 quedan registradas y aprobadas para este protocolo local. Esto no certifica ejecución bajo presupuesto ni cierra G2/G3. T14 y posteriores no se ejecutan por esta revisión documental.

## Verificación de este cierre documental

Las tres decisiones quedaron registradas con las respuestas explícitas del usuario. Se alinearon intent/spec/plan/README, el registro de decisiones y las referencias de arquitectura/features. La configuración ejecutable solo amplía la whitelist de procedencia académica; el protocolo de periodos/recursos es un documento estructurado, no un módulo de entrenamiento ya implementado.

- Suite existente ejecutada tras ampliar la whitelist: **255 pruebas aprobadas**. Comando: `.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-decisions-d01-d02-d04 -o cache_dir=.cache/pytest-cache-decisions-d01-d02-d04`.
- Ruff check y format check sin errores. No se instalaron dependencias ni se modificó código de entrenamiento.
- Auditoría de los 24 hashes/tamaños contra el inventario original, coincidencia entre autorizaciones de configuración/documento y fronteras/offsets temporales. Reglas D-04 idénticas a las del piloto.
- Marcador, Parquet y configuración congelada del piloto enero verificados sin reescribirlos. Solo enero tiene manifiesto; sin datasets de features reales, entrenamiento ni registro/validación de los otros 23.
- Enlaces locales y UTF-8 verificados; PDF académico intacto. Auditoría detallada local en `.cache/d04/approved-protocol-audit.json`. Cambios locales sin nuevo commit/push.

Este cierre verifica coherencia documental/configuración y regresiones existentes. Las pruebas de particiones con datos completos, aprendizaje incremental y control efectivo del presupuesto corresponden a T14–T16; no se presentan como ejecutadas.

## Actualización T14 posterior

T14 fue autorizada y se implementó/probó con fixtures. [Contrato y evidencia](t14-temporal-splits.md). El preflight RAM/disco y supervisión cooperativa entre bloques ya existen para particionado; el temporizador y controles de candidatos siguen en T16. No se ejecutaron particiones reales ni entrenamiento. Las referencias anteriores a ausencia de implementación describen el cierre documental inicial de estas decisiones.

## Perfil específico T14/T15 aprobado después

Para terminar las tareas con todos los datos, el usuario aprobó mediana global exacta en disco de train y un perfil operativo de preparación/mediana: 4 GiB RAM libre, 2 GiB RSS, 50 GiB disco libre, cuatro hilos y proceso secuencial por bloques. Fallar detiene el intento sin reducir datos. Los candidatos SGD/MLP T16 conservan su perfil original de 12 GiB libres/8 GiB RSS. [Configuración](../configs/model.yaml), [contrato T15](t15-baseline.md). El baseline no abre test/replay; flujo real actualmente en curso, sin resultados finales todavía.

## Ejecución posterior detenida por D-04

15 meses registrados LOCAL_UNVERIFIED; 14 completaron calidad/features REAL (2024 completo y enero–febrero de 2025). Marzo de 2025 rechazado: 22.280 duraciones no positivas/4.145.257 filas (0,537482 %), máximo 0,50 %. El usuario decidió mantener D-04. No hay particiones reales ni baseline real publicados. [Auditoría](../reports/quality/t14_t15_preparation.md), [decisión y fuente](t14-t15-quality-blocker.md). 333 pruebas en desarrollo y wheel verifican software; no se afirma ejecución del baseline. Se conservan perfiles aprobados y originales. Las referencias previas a solo enero o ejecución en curso corresponden a etapas anteriores; no hay procesos activos.

## Ajuste independiente T15 posterior

Ajuste exacto train 2024 completo y auditado: 41.119.495 etiquetas, mediana 12,983333 minutos; 561 filas apartadas por corte de etiqueta entre 41.120.056 elegibles DQ. Evaluación y cierre de T14/T15 pendientes de marzo 2025; D-04 permanece congelada. [Evidencia](../reports/quality/t15_train_fit.md). La separación fue aprobada expresamente. Se respetó el perfil 4/2 y todas las filas elegibles al corte; el presupuesto T16 12/8 y el rechazo de marzo no cambian.

## Excepción de marzo y evaluación T15 posteriores

T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [Reporte](../reports/quality/t15_baseline_validation.md). Marzo aceptado por excepción humana solo para su hash/reporte; FAIL original y exclusiones conservados, sin cambiar D-04 global. T14 integral sigue pendiente; test/replay sellados, T16 no ejecutada y sin registro/promoción. [Contrato y autorización](t15-march-exception.md). Las referencias anteriores a bloqueo de evaluación o ausencia de excepción son históricas.


## Revisión posterior de entrenamiento — 2026-11-05

T14 terminó con su contrato congelado. Después, el usuario aprobó para T16/T17 8 GiB RAM libre/4 GiB RSS, manteniendo4 hilos, un candidato,2h y50 GiB disco. Sustituye el perfil inicial12/8 exclusivamente en estas fases; la configuración de particiones y su hash permanecen históricos. [Registro](d02-t16-resource-review.md) y [candidates.yaml](../configs/candidates.yaml). Todos los elegibles, sin submuestreo.
