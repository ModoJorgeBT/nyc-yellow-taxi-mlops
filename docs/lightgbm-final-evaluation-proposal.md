# LightGBM — Propuesta de evaluación final independiente

**Actualización de ejecución: APLICADA Y AUDITADA.** [Resultado final](../reports/evaluation/lightgbm_final_evaluation.md).
Las secciones siguientes conservan la propuesta y el estado previo a ejecutar.

Fecha: 2026-11-05, America/Costa_Rica. **PERIODO, PROTOCOLO Y TRES DESCARGAS LIMITADAS APROBADOS por el usuario.** Configuración congelada: [lightgbm-final-evaluation.yaml](../configs/lightgbm-final-evaluation.yaml). La ejecución y sus resultados siguen pendientes; esta aprobación no concede excepciones D-04 ni autorización de MLflow.

## Periodo propuesto y alcance

Reservar **enero–marzo de 2026 completos** para una única evaluación final de los modelos congelados. Estos archivos no existen actualmente en el proyecto: el inventario local contiene solo los 24 meses de 2024/2025. No se han leído filas ni medido resultados predictivos de 2026 durante esta preparación.

La [página oficial TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) publica enlaces Yellow Taxi para esos tres meses, verificados el 2026-11-05. La disponibilidad efectiva, tamaño e integridad de cada archivo se verificarán al incorporarlo; no se inventan fechas de publicación.

Esta reserva amplía D-01 para un experimento final independiente y no altera train 2024, validation enero–marzo de 2025, el test original abril–junio de 2025 ni el replay julio–diciembre de 2025. No se sustituye la evaluación independiente por reutilizar el test conocido ni por consumir el replay reservado.

El intervalo de recogida propuesto es `[2026-01-01 00:00 America/New_York, 2026-04-01 00:00 America/New_York)`. Para respetar el mismo criterio de maduración de etiquetas, la llegada UTC deberá ser estrictamente anterior a **2026-04-01 04:00:00Z**. Los viajes que crucen ese corte se apartan con motivo/conteo y no se trasladan a otro conjunto. Se conserva la convención histórica Nueva York/UTC y el tratamiento DST aprobado.

## Incorporación de datos que requiere aprobación

Opción recomendada: descargar **solo tres Parquet oficiales**, uno por mes, bajo `data/raw/2026/MM/yellow_tripdata_2026-MM.parquet`, mediante el módulo de ingesta y manifiestos del proyecto.

- URLs: `https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-01.parquet`, con el mes correspondiente 01, 02 o 03.
- Máximo **512 MiB por archivo y 1 GiB acumulado**. No son tamaños observados. La descarga debe comprobar el tamaño anunciado y aplicar también un límite durante la transferencia; si se supera, se detiene y consulta, conservando el motivo y sin incorporar un archivo parcial.
- Sin otros años, meses, tipos de taxi ni datasets auxiliares. Si una URL falla, no se sustituye el periodo silenciosamente.
- Registrar URL y fecha UTC reales de descarga, bytes, SHA-256, esquema y filas del footer. No marcar una descarga nueva como LOCAL_UNVERIFIED.
- Alternativa: el equipo aporta los tres archivos. Antes de consumirlos se verifican hashes y procedencia; si esta es desconocida, se solicita una autorización LOCAL_UNVERIFIED específica para los nuevos archivos. La autorización de los 24 anteriores no se extiende automáticamente.

El usuario aprobó esta parte mediante «Sí, autorizar esas tres descargas limitadas». Se requiere controlar el tamaño anunciado y el transferido, sin ampliar automáticamente el presupuesto.

## Calidad y cobertura

Aplicar **D-04 v1 sin modificar umbrales, catálogo ni normalizaciones**, un mes a la vez, con los perfiles aprobados de preparación por bloques. Los tres meses deben tener resolución explícita antes de abrir resultados predictivos; no se eligen meses en función de sus errores ni se omiten los rechazados para presentar un resultado parcial como trimestre completo.

Cualquier incompatibilidad de esquema, incumplimiento de calidad o procedencia no autorizada se presenta al usuario antes de consumir el lote. Las diez excepciones de 2025 no autorizan excepciones de 2026. Una eventual autorización nueva deberá identificar mes, hash, configuración, reporte, fallos exactos y filas excluidas; conservará FAIL y exclusiones. No cambiar filtros después de ver errores del modelo.

Procesar todas las filas elegibles, sin muestreo. Auditar `raw = exclusiones DQ + features previas al corte` y `features = exclusiones por corte + evaluables`, con identidades y hashes. Nuevos directorios de validated/features/evaluación; no sobrescribir las cuatro particiones de T14 ni sus recibos.

## Modelos y protocolo que requieren aprobación

Evaluar **LightGBM, baseline y SGD ya congelados** sobre las mismas filas de 2026. Baseline y SGD permiten una comparación temporal directa; no se usarán sus métricas de 2025 como sustituto de una comparación sobre el mismo conjunto.

- LightGBM: entrenamiento `a36932872f8e49989a52bb76186ca88a`; joblib SHA-256 `8bd17196b3a5c1974036c11456f61083d2a5f601236d55d56f884802b477cff6`; Booster texto `daaa5d3d98530529695ea98749a00f9cca999b10126c592525a5a289cc4714eb`.
- SGD: entrenamiento original `faf8ab304ffb447f8bff8c1372715352`; SHA-256 `bfe284f297e7eb8d67261242ab1d4d35dc9639d181760dc923da128e52082541`.
- Baseline T15: mediana train `779/60` minutos; modelo evaluado SHA-256 `7d6e3eefd040f04f46e7a8f6ef6068fd65dcf86c56bb0e97cde5ecb8f0c8abf9`.

Se fijan estas identidades, el periodo, las políticas y el protocolo **antes de abrir métricas de 2026**. No hay entrenamiento, actualización de vocabulario, escalado, discretización, early stopping ni selección de hiperparámetros. MLP queda fuera de esta evaluación adicional propuesta; su resultado original no se altera.

Métricas: MAE principal y RMSE, MedAE y P90 absoluto exactos, con interpolación lineal y unidades en minutos. Reporte global, por mes real de 2026, cuatro franjas locales de seis horas y las veinte rutas ya congeladas por frecuencia de validation 2025, más «otras». Destino continúa exclusivamente como segmentación posterior. Se registran orígenes desconocidos y recortes a [1 segundo, 180 minutos]; no finitos provocan fallo.

Una sola ejecución final completa; si existe un fallo de infraestructura o integridad, conservar el intento y corregir la causa antes de un reinicio trazado. No repetir para elegir un resultado ni ajustar modelos usando este conjunto. La auditoría puede reproducir las predicciones y recomputar métricas sin modificar el protocolo ni los modelos.

Conservar recursos vigentes: preparación con mínimo 4 GiB libres/2 GiB RSS y bloques hasta 65.536; evaluación con mínimo 8 GiB libres/4 GiB RSS, cuatro hilos, un modelo a la vez, 50 GiB disco y máximo dos horas por candidato. Si los controles fallan, detener y consultar antes de ampliar recursos o reducir datos. No se inicia otro fit.

La evaluación termina aunque LightGBM no mejore: publicar el resultado real y sus límites. **No equivale a promoción ni garantiza capacidad predictiva en otros periodos.** D-05 y la decisión de champion siguen pendientes.

## Implementación prevista después de aprobar

- Crear `configs/lightgbm-final-evaluation.yaml`: aprobación, periodo, corte, modelos/hashes, política, recursos y límites de transferencia.
- Añadir límite de bytes al descargador, con comportamiento anterior conservado para otros usos; pruebas de tamaño anunciado/transferido, límite acumulado y limpieza de parciales.
- Crear un preparador y evaluador final separado del contrato validation-only de `configs/lightgbm.yaml` y `src/evaluation/lightgbm_run.py`. Esos archivos y sus resultados anteriores se conservan como evidencia de la extensión inicial.
- Derivar los meses con su año efectivo: el helper histórico de segmentos usa etiquetas `month_2025_*` y no se reutilizará para etiquetar 2026.
- Pruebas de corte UTC/DST, ausencia de fit, bloqueo de periodos no aprobados, integridad, calidad no autorizada, cobertura completa, comparación sobre las mismas filas, métricas exactas y recursos. Probar primero con fixtures y wheel, antes de datos reales.
- Publicar `reports/evaluation/lightgbm_final_evaluation.md` y recibos locales auditables; actualizar README/intent/spec/plan/decisions con la aprobación y los resultados reales.

## Aprobaciones siguientes y orden de T18

1. **Ahora:** aprobar enero–marzo de 2026 y el protocolo anterior, incluidos baseline/SGD como comparadores congelados.
2. **Ahora:** aprobar la descarga oficial limitada o elegir aportar los archivos. La segunda opción puede requerir después autorización de procedencia por hash si es desconocida.
3. **Solo si aparecen:** resolver cada incumplimiento D-04, esquema, integridad o presupuesto antes de consumirlo; no se conceden excepciones futuras.
4. **Después del reporte final auditado:** presentar D-07 para aprobación de MLflow: versión/dependencias compatibles, entorno, SQLite/artefactos persistentes, puerto local y alcance del Registry. No se instalará ni iniciará MLflow antes de esa aprobación. Las propuestas técnicas se contrastarán con la [documentación oficial del servidor](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/).
5. T18 registrará modelos/resultados y verificará persistencia, linaje y carga. La aprobación de champion corresponde a T19 y no queda concedida por esta evaluación ni por instalar MLflow.

Esta propuesta requiere aprobación porque el [D-01 vigente](d01-d02-protocol.md) solo autorizó los datos existentes de 2024/2025 y exige nueva autorización para un lote posterior. Se conserva la aprobación original de LightGBM limitada a validation; la evaluación final tendrá autorización y contrato propios.

## Registro de aprobación

El usuario respondió «Sí, aprobar periodo y protocolo propuestos» y «Sí, autorizar esas tres descargas limitadas». Esto autoriza implementar y probar el flujo final descrito y descargar solo los tres archivos. Cualquier nuevo incumplimiento se presenta antes de consumir el lote. D-07, instalación de MLflow y promoción conservan sus aprobaciones separadas.
