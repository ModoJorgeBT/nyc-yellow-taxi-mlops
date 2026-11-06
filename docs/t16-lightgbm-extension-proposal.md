# T16/T17 — Incorporación de LightGBM

Fecha: 2026-11-05, America/Costa_Rica. **APROBADO, IMPLEMENTADO Y AUDITADO: ajuste completo y evaluación solo en validation. Nueva evaluación final independiente pendiente.** Esta propuesta no modifica artefactos ni resultados de la primera comparación.

## Motivo y restricción temporal

T14 y la primera comparación T16/T17 tienen cierre técnico auditado: baseline, SGD Huber y MLP16. SGD fue elegido exclusivamente con validación antes de abrir test. Ahora el resultado de abril–junio de 2025 ya es conocido. Añadir LightGBM inicia un experimento posterior; no permite presentar ese mismo test como una evaluación independiente de la nueva decisión de modelado.

Decisión aprobada: entrenar LightGBM con 2024 y compararlo únicamente con enero–marzo de 2025. Conservar la selección SGD y el reporte final originales. No evaluar LightGBM sobre test ni replay en esta extensión; una nueva evaluación final independiente necesita un conjunto futuro aún no utilizado y aprobación de su alcance. No se aprueban aquí nuevos periodos ni descargas.

Alternativa NO elegida por el usuario: evaluar también abril–junio como comparación retrospectiva exploratoria. Debe etiquetarse como test reutilizado, sin sustituir la primera selección ni afirmar confirmación independiente. No se ajustarán parámetros tras esa comparación.

## Perfil inicial propuesto

- Añadir `lightgbm==4.7.0` como dependencia de modelado, fijada en el lock con hashes. PyPI publica wheel Windows x64 y declara Python 3.14; importación, biblioteca nativa y compatibilidad con NumPy/scikit-learn deben probarse localmente. No instalar pandas, GPU, compiladores ni runtimes globales automáticamente. Fuente: [publicación oficial en PyPI](https://pypi.org/project/lightgbm/4.7.0/).
- Mantener **las 41.119.495 filas elegibles de train** y las seis features causales existentes. Origen como categoría nativa mediante vocabulario ajustado solo con train; categorías futuras se tratan como desconocidas. Calendario, pasajeros imputados e indicador de ausencia conservan su significado. No usar destino como predictor ni ajustar transformaciones con 2025.
- Usar CPU, `boosting_type=gbdt`, `objective=regression_l1`, `metric=l1`, 100 árboles, `learning_rate=0.05`, `num_leaves=31`, `max_depth=-1`, `min_data_in_leaf=1000`, `max_bin=63`, cuatro hilos, semilla 42, `deterministic=true`, `force_col_wise=true` y caché de histogramas de 256 MB. Sin bagging, GOSS, selección de columnas, búsqueda de hiperparámetros ni early stopping. No confundir 100 iteraciones de boosting con las pasadas incrementales de SGD/MLP.
- Construir el Dataset desde datos en disco y acceso por bloques, sin la expansión densa de 268 columnas. `Sequence` permite lectura por rangos, pero el Dataset nativo y las estructuras del entrenamiento consumen memoria: no garantiza entrenamiento fuera de RAM. [Interfaz Sequence](https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.Sequence.html).
- Proponer `bin_construct_sample_cnt=200000`, únicamente para estimar cortes de discretización sobre train, con semilla fija y registro de esta aproximación. **El ajuste de árboles utilizará todas las filas**; no equivale a entrenar con una muestra. Si el equipo exige calcular también los cortes con todas las filas, hace falta revisar viabilidad y presupuesto antes de cambiarlo.
- Mantener el presupuesto vigente: mínimo 8 GiB RAM libre y 50 GiB disco; máximo 4 GiB RSS, cuatro hilos, un modelo y dos horas, incluyendo conversión/construcción del Dataset. Un supervisor externo vigilará el proceso nativo; exceder un límite cancela el intento, sin reducir datos ni ampliar recursos. `histogram_pool_size` limita solo la caché de histogramas, no el RSS total. [Parámetros oficiales](https://lightgbm.readthedocs.io/en/stable/Parameters.html).
- Mantener predicciones entre 1 segundo y 180 minutos, con conteo de recortes, fallo ante no finitos y mismas métricas exactas y segmentos de la primera comparación. Guardar un modelo y manifiesto nuevos; no sobrescribir SGD, MLP, baseline o selección originales.

La matriz compacta float32 de seis columnas ocupa aproximadamente 0,92 GiB en disco, más etiquetas y estructuras nativas. **La viabilidad de este perfil quedó verificada en la ejecución real**; los recursos observados están en el reporte enlazado al final. No se promete una mejora de precisión.

## Archivos y pruebas previstos

Modificar `pyproject.toml` y regenerar `requirements-dev.lock` conservando las versiones existentes. Crear un contrato separado `configs/lightgbm.yaml`, entrenador/adaptador serializable y evaluación de extensión con manifiestos propios. Mantener `configs/candidates.yaml` y el software de la primera ejecución como evidencia congelada.

Las pruebas cubrirán categorías desconocidas, whitelist, ausencia de fit con datos futuros, cobertura de todas las filas, guardas de proceso nativo y timeout, serialización con predicción equivalente, recortes/no finitos, integridad de artefactos y rechazo de acceso a test/replay cuando el alcance sea solo validación. Ejecutar primero fixtures, lint y prueba del wheel en entorno limpio; después preflight, preparación y ajuste real, si están aprobados.

No se inicia T18, no hay registro/promoción y no se cambian D-01 ni D-04. Cualquier nueva excepción de calidad sigue requiriendo aprobación por lote/hash/reporte.

El usuario respondió «Sí, aprobar el perfil propuesto» y «Solo validación; nueva evaluación final pendiente». No hace falta solicitar otra vez esas autorizaciones. Si la compatibilidad o los límites fallan, se conserva el intento fallido y se consulta antes de cambiar el presupuesto o reducir datos.

LightGBM 4.7.0 fue entrenado con las 41.119.495 filas train y 100 árboles. En las 11.163.264 filas validation: MAE 6.496404, RMSE 9.847425, MedAE 4.631360 y P90 13.478764 minutos. Ajuste y evaluación auditados; 447 pruebas por entorno. Solo validation: una nueva evaluación final independiente sigue pendiente. La selección SGD y el test de la primera comparación permanecen intactos; no hay promoción. [Evidencia completa](../reports/evaluation/lightgbm_validation.md).
