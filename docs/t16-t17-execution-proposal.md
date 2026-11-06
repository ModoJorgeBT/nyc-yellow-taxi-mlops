# T16/T17 — Propuesta de ejecución posterior al cierre de T14

Fecha: 2026-11-05, America/Costa_Rica. **APROBADA POR EL USUARIO, CON EJECUCIÓN CONDICIONADA AL CIERRE DE T14.** Respuestas: «Sí, aprobar ese perfil inicial de T16» y «Sí, aprobar ese protocolo de T17». D-02 ya fija los dos candidatos incrementales y sus recursos; este documento concreta las decisiones aprobadas de implementación y evaluación. T14 debe terminar su preparación y auditoría antes de ejecutar este protocolo; registrar la aprobación no inicia entrenamiento ni evaluación.

## Datos y preprocesamiento

- Consumir solo las cuatro particiones T14 identificadas por manifest y hashes. Entrenar con todas las filas elegibles de 2024, sin submuestreo; seleccionar con enero–marzo de 2025. Test abril–junio reservado hasta congelar la comparación de validación; replay julio–diciembre no participa en métricas ni selección T17.
- Conservar las seis columnas de T12/T13: origen, hora, día semanal, mes, pasajeros normalizados e indicador de ausencia. Destino, distancia y cargos no son predictores.
- Vocabulario one-hot obtenido exhaustivamente de train; desconocidos ignorados manteniendo dimensión. Ajustar StandardScaler(with_mean=False) por bloques únicamente sobre train codificado; congelar ambos componentes antes de validation/test. Esta normalización adicional busca estabilidad numérica en SGD/MLP y no incorpora dependencias nuevas.
- Un único Pipeline serializable incluirá adaptador de entrada T13, codificación, escalado y estimador con salida acotada. La transformación rápida desde tablas se contrastará contra el Pipeline usado por inferencia, con pruebas de igualdad y serialización.
- Semilla 42; orden de bloques reproducible; bloques externos de 4.096 filas. Una pasada de entrenamiento por candidato sobre todo train, sin early stopping ni validación interna aleatoria. El barrido previo de vocabulario/escalado también cubre todo train; no ajusta estimadores ni mira 2025.

## Candidatos y predicciones

| Candidato | Parámetros iniciales a congelar |
|---|---|
| SGDRegressor | loss=huber, epsilon=1.35, penalty=l2, alpha=0.0001, learning_rate=invscaling, eta0=0.001, power_t=0.25, average=True, shuffle=True dentro del bloque, random_state=42. Una llamada partial_fit por bloque, una pasada total. |
| MLPRegressor pequeño | hidden_layer_sizes=(16,), activation=relu, solver=adam, loss=squared_error, alpha=0.0001, learning_rate_init=0.001, batch_size=256, shuffle=True dentro del bloque, random_state=42, early_stopping=False. Una llamada partial_fit por bloque, una pasada total. |

Aplicar a ambos una cota explícita de predicción **[1/60, 180] minutos** (un segundo a tres horas), dentro del estimador serializado. Registrar cuántas salidas se recortan; una predicción no finita falla, no se oculta con recorte. Es una decisión de salida del modelo, no modifica etiquetas, target, calidad ni filas elegibles. No se promete superar el baseline: si es mejor en validación, seguirá siendo la referencia recomendada.

## Recursos y pruebas

D-02 inicial fijó 12 GiB libres/8 GiB RSS. Tras fallar el preflight real con 10,49 GiB disponibles, el usuario aprobó la [revisión 8 GiB libres/4 GiB RSS](d02-t16-resource-review.md) para T16/T17. Se mantienen cuatro hilos, un candidato, dos horas por candidato y 50 GiB disco. El tiempo compartido de preprocesamiento se contabiliza en el presupuesto de cada candidato. Controlar recursos/tiempo antes, entre bloques y antes de publicar; son controles cooperativos, con límites efectivos del SO/Docker todavía no certificados. Exceder detiene el intento, sin reducir datos ni ampliar límites automáticamente.

Si no hay 8 GiB libres al iniciar, presentar la medición y esperar a liberar memoria o a otra revisión explícita de D-02. No se instalan dependencias adicionales; se usan las versiones ya aprobadas de scikit-learn, NumPy, PyArrow, joblib y threadpoolctl.

Pruebas necesarias: cobertura de todos los bloques y filas; fit del preprocesador solo sobre train; categorías desconocidas; no acceso a validation durante fit ni a test durante selección; partial_fit y reejecución reproducible; equivalencia entre transformación de tablas y Pipeline; serialización/carga/predicciones; límites de RAM/disco/tiempo; interrupción y ausencia de manifest completo ante fallos; integridad y revocación de las autorizaciones de calidad.

## Evaluación T17

- MAE principal; RMSE, MedAE y P90 de error absoluto complementarias, en minutos. MedAE/P90 exactos, percentiles con interpolación lineal, usando errores temporales en disco y memoria supervisada; no aproximaciones silenciosas.
- Comparar baseline T15 congelado y ambos candidatos sobre las mismas filas de validation. Elegir menor MAE global sin cambiar hiperparámetros después de ver test; empates exactos favorecen baseline, luego SGD y luego MLP por complejidad creciente. Si un candidato no completa sus controles, reportar fallo y no inventar métricas ni cierre de T16.
- Reportar por mes y cuatro franjas de seis horas (00–05, 06–11, 12–17, 18–23). Rutas observadas: top 20 pares origen–destino con al menos 1.000 filas en validation, seleccionados solo por frecuencia, no por error. Mantener ese catálogo fijo al reportar test; demás rutas agrupadas como otras. Desempatar frecuencias por IDs ascendentes y reportar soporte.
- DOLocationID se recuperará del dataset validado alineado mediante identidad de fuente/índice, exclusivamente para segmentación posterior. No entra en features, entrenamiento, inferencia, elección de hiperparámetros ni selección de rutas por métricas. La evaluación de rutas no demuestra que el destino fuese conocido al inicio.
- Congelar el resultado de selección en validation y su catálogo de segmentos antes de abrir test para métricas. Hacer una evaluación final de baseline y los dos candidatos ya congelados; no elegir de nuevo ni reajustar después. Documentar exclusiones de calidad y corte por mes, incluida la aceptación excepcional de test.
- Registrar hashes, configuración, semilla, recursos, soporte de cada segmento y limitaciones. No registrar/promover un champion en MLflow ni iniciar T18/T19 por estas tareas; requieren sus propias decisiones y pruebas.

Archivos previstos: src/training/train.py y soporte de preprocesamiento/modelos incrementales, src/evaluation/metrics.py y CLI de evaluación, configuración pública de candidatos, tests unitarios/integración y reportes Markdown. Datos, errores temporales, modelos y predicciones permanecerán locales y excluidos de Git. El detalle de módulos auxiliares se resolverá dentro de este alcance sin nuevas tecnologías.
