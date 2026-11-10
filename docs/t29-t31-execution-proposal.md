# T29–T31 — Propuesta para aprobación

Estado: APROBADA por el usuario en conversación. Fecha: 2026-11-09, America/Costa_Rica. Solicitud del usuario:
terminar T29–T31 y publicar/documentar la cuarta entrega. Esta propuesta no
por sí sola no acreditaba instalación, procesamiento real ni reglas ejecutables.
El usuario aprobó después herramientas/entorno, protocolo/presupuesto y
ampliación del PR #1, conservando main y el historial.
La [revisión de compatibilidad](t29-evidently-compatibility-review.md),
también aprobada, separa el renderer pandas 2.3.3 del runtime de predicción
pandas 3.1.1. El [incidente de descargas y su recuperación](t29-dependency-download-incident.md)
se conserva sin presentar el primer intento como cumplimiento de presupuesto.

## Dependencias y herramientas

Evidently 0.7.23, verificado en [PyPI](https://pypi.org/project/evidently/0.7.23/),
declara Python >=3.10, pero no acredita compatibilidad probada con 3.14.
Propuesta: verificar resolución, wheels e importación en Python 3.14.7;
instalar en `.venv-monitoring` separado, con lock y hashes propios y versiones
compartidas fijadas a las aprobadas de serving. Preparar un lock Linux y etapa
CI separada para probar realmente su integración con fixtures. Conservar los
locks históricos y el runtime de serving. Máximo 1 GiB de descargas nuevas;
si faltan wheels o hay conflictos, consultar antes de cambiar versiones/Python.

Sin extras LLM, descargas NLP, Cloud, cuentas ni servicios nuevos. Uso como
biblioteca, con `DO_NOT_TRACK=1`; [opción oficial](https://docs.evidentlyai.com/faq/telemetry).

## T29 — Distribuciones completas, referencia train

- Leer por bloques todas las features elegibles de train 2024 del split T14
  auditado, sin targets. Congelar distribuciones por mes; comparar cada mes
  de julio–diciembre 2025 con el mismo mes de 2024 para evitar que el cambio
  de mes, por construcción, se interprete como drift.
- Las seis features discretas v1: origen, hora, día semanal, mes, pasajeros
  normalizados e indicador de ausencia. Categorías/dominios fijados con train
  y el contrato aprobado; categoría adicional explícita para valores nuevos.
  No ajustar bins, referencia ni umbrales con replay.
- PSI calculado sobre conteos exhaustivos, sin muestreo ni expansión de los
  conteos a millones de filas. Suavizado aditivo alpha=0,5 por categoría y
  normalización separada para referencia/actual. Alerta por feature si
  PSI >0,20; mínimo 1.000 registros por ventana en ambos conjuntos, o
  NOT_AVAILABLE por evidencia insuficiente. El mes será también control
  descriptivo; no se adoptan defaults estadísticos de Evidently.
- Usar métricas personalizadas de Evidently sobre las distribuciones
  agregadas reales, con JSON/HTML identificados como agregados, sin simular
  que una categoría equivale a un viaje. [API oficial](https://docs.evidentlyai.com/metrics/customize_metric).
  Probar cálculo/serialización antes de procesar datos reales; si la API no
  permite esa representación, consultar antes de sustituirla por muestreo.

## T30 — Desempeño retrospectivo con etiquetas posteriores

- Champion LightGBM v4 congelado, con hashes y aprobación verificados; todas
  las 24.266.924 filas elegibles preparadas de replay julio–diciembre 2025.
  Sin entrenamiento, ajustes, test 2025 o holdout final 2026.
- Predicciones generadas solo desde features de inicio; etiquetas unidas en
  una fase separada mediante identidad compuesta de split, feature_id y
  validated_row_index, con hashes y controles de unicidad/cobertura.
- Cohortes mensuales por recogida en Nueva York; corte de maduración a fin
  de mes UTC +24 horas. Solo usar etiquetas con evento final disponible en
  ese corte. Esta simulación de tiempo de evento no acredita disponibilidad
  histórica del archivo publicado por TLC. Conservar exclusiones T14/D-04.
- Sin etiquetas: NOT_AVAILABLE, sin MAE inventado. Con etiquetas: MAE, RMSE,
  MedAE y P90 exactos, denominadores y cobertura; mes, franjas de seis horas
  y las 20 rutas congeladas por validation en T17. Destino solo en segmentación.
  Cuantiles en disco; nunca ordenar toda la partición en memoria.
- Comparación descriptiva con MAE de validación ya congelado de LightGBM;
  no recalcular validación ni usar replay para elegir o reajustar modelos.
  El umbral de deterioro del 115 % y la condición de dos ventanas siguen
  pendientes de T32; no se aprueban por esta tarea.

## T31 — Informe mensual y presupuesto

CLI `python -m src.monitoring.run --year YYYY --month MM`, con salidas
versionadas, configuración/linaje, calidad T28 y sus FAIL/excepciones,
drift T29, desempeño T30 y métricas de servicio T27 cuando exista evidencia.
Las ventanas actuales de la API no se atribuyen a meses históricos 2025;
en ausencia de logs correspondientes, servicio = NOT_AVAILABLE.

Decisión preliminar: ALERT_REVIEW_REQUIRED por PSI o calidad; si no hay
alertas y la evidencia está completa, OBSERVED. Insuficiencia = NOT_AVAILABLE.
No implementar triggers T32, recomendar automáticamente entrenamiento,
promover modelos ni modificar el champion. Una excepción nueva se consulta.

Perfil propuesto: preflight 4 GiB RAM libre y 50 GiB disco, máximo RSS 2 GiB,
cuatro hilos, bloques <=65.536 (predicción 4.096), un mes a la vez y dos horas
por ejecución. Supervisar recursos y detener ante exceso, sin muestreo ni
relajación automática. CI conserva 2 CPU/4 GiB/10 GiB disco/20 minutos y fixtures.

## Archivos y aceptación

`src/monitoring/{drift,performance,run}.py`, adaptador Evidently, configuración
de monitoreo, locks/manifest Linux nuevos, pruebas unitarias/integración,
informes Markdown y actualización de documentos rectores/historial.

Pruebas: referencia estable frente a alterada; frontera PSI y categorías
nuevas/ausentes; métricas con valores conocidos; etiquetas ausentes/tardías,
identidades alteradas o duplicadas; linaje/hash, corte temporal, restricciones
de memoria y salidas incompletas; integración Evidently y dos meses simulados;
seis meses reales auditados, sin cambios de modelos. Ruff, suite apropiada y CI
real antes de declarar G5 verificado. No implementar T32–T38.

## Publicación

`main` conserva tres commits. La cuarta entrega T20–T28 ya está publicada
en PR #1 mediante f675188 y el seguimiento documental 6b9d449. Propuesta:
ampliar ese PR con T29–T31 y nuevos commits normales, dejando explícitos
alcances/SHA en `docs/commit-history.md`; sin renumerar, reescribir historia,
merge a main, datos, modelos, secretos ni el PDF nuevo del equipo.
