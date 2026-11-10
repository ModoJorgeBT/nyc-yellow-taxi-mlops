# T32–T34 — Propuesta de ejecución para aprobación

Fecha: 2026-11-09, America/Costa_Rica. **APROBADA por el usuario en conversación:**
reglas T32, periodos/descargas/ejecución T33–T34 y gate T34, por separado.
El usuario solicitó T32–T34. El PR #1 ya fue integrado en main mediante
21a6abf; su CI pasó. Esta propuesta no activa reglas ni autoriza descargas,
entrenamiento, nuevas excepciones o cambios de champion por sí sola.

## Dependencias y riesgos

T31/G5 están verificados. D-05 solo tiene aprobado PSI para alertas; faltan
triggers ejecutables y el criterio champion/challenger. T33 requiere aprobar
nuevos periodos de entrenamiento. Enero–marzo 2026 ya se evaluó para T19:
no puede presentarse otra vez como evaluación independiente.

Propuesta: nuevo ciclo retrospectivo separado, conservando resultados y
artefactos anteriores. El origen de datos/eventos no demuestra que TLC los
hubiera publicado al cierre de cada mes. La fuente oficial advierte un
retraso típico de publicación de dos meses:
[TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page).

No se añadirán dependencias ni se modificarán los locks. Predicciones y fit
seguirán en el runtime original .venv-mlflow; Evidently seguirá aislado.
Las configuraciones y reportes T29 están ligados a hashes: se creará un
perfil nuevo de retraining que los referencie, sin alterar monitoring.yaml
ni invalidar los recibos existentes.

## Aprobación 1 — T32: reglas de recomendación

- Deterioro: MAE mensual **estrictamente mayor que 115 %** del MAE de
  validation congelado del champion (6,496404304242834 minutos), durante
  dos meses de calendario consecutivos. Mínimo 1.000 etiquetas maduras por
  mes y cobertura completa del conjunto elegible bajo el protocolo T30.
  Es una referencia fija de validation, sin corrección estacional; el
  resultado no atribuye causalidad al drift.
- Drift: la **misma feature** supera PSI 0,20 durante dos meses consecutivos,
  con mínimo 1.000 registros en ambas poblaciones y el suavizado/dominios
  T29 congelados. Pasajeros y ausencia pueden estar correlacionados: no se
  suman como evidencias independientes.
- Cualquiera de esas dos condiciones produce RETRAIN_RECOMMENDED; nunca
  inicia un entrenamiento ni cambia el alias. Evaluación sin condición
  suficiente: NO_ACTION, con disponibilidad de cada señal por separado.
  Meses ausentes no se unen artificialmente para formar una pareja.
- Evidencia corrupta, otra versión de modelo, protocolo diferente o lote
  rechazado sin excepción exacta: BLOCKED_REVIEW; no entrenar. Los FAIL
  aceptados explícitamente mantienen sus exclusiones y su trazabilidad.
- Revisión trimestral: aviso REVIEW_REQUIRED desde el último ajuste,
  calculado con fechas explícitas y sin interpretar una revisión como un
  trigger automático. Cambios relativos de calidad sin umbral aprobado
  permanecen descriptivos; cambios incompatibles bloquean para revisión.
- Recepcionar seis reportes T31 por ruta/hash, verificar linaje común,
  orden, periodos y modelo. Persistir reporte versionado de reglas,
  evidencia, motivos y decisión. No reabrir datasets para decidir T32.

## Aprobación 2 — T33: ciclo temporal y recursos

| Uso nuevo | Periodo | Tratamiento |
|---|---|---|
| Train challenger | enero–diciembre 2025 | Todos los elegibles con etiqueta anterior al 1 de enero 2026 NY |
| Validation de desarrollo | enero–marzo 2026 | Datos ya conocidos; no prueba independiente |
| Comparación final T34 | abril–junio 2026 | Nuevo conjunto reservado, sin consultar métricas hasta congelar candidato y reglas |

Se crearán manifiestos y particiones nuevos desde features aceptadas;
no se concatenarán sin más los splits antiguos: sus cortes trimestrales
excluyeron etiquetas que podrían ser elegibles bajo el nuevo corte anual.
Intervalos por recogida [inicio, fin) en America/New_York, etiquetas
anteriores al corte correspondiente; misma política temporal/DST de T12.
Se auditarán identidades, cobertura, exclusiones, valores, hashes y cortes.
No se sobrescribirán splits, features ni resultados anteriores.

Challenger: LightGBM 4.7.0 **desde cero**, seis features aprobadas,
origen categórico y vocabulario ajustado solo con train nuevo, mismos
parámetros de configs/lightgbm.yaml: 100 árboles, 31 hojas, learning_rate
0,05, max_bin 63, semilla 42 y cuatro hilos. Sin búsqueda de parámetros,
early stopping, warm start ni selección con el conjunto final. Los 200.000
registros de discretización son solo para bins; todos los elegibles
participan en los árboles, conforme al diseño T16.

Entrenamiento: mínimo 8 GiB RAM libres/50 GiB disco, máximo 4 GiB RSS,
un candidato, cuatro hilos y dos horas; supervisor nativo y controles
probados antes del fit. Preparación 4 GiB libres/2 GiB RSS; evaluación
6 GiB libres/2 GiB RSS, 50 GiB disco/cuatro hilos/dos horas por modelo.
No reducir datos ni ampliar límites automáticamente ante incumplimientos.

T33 registrará un único candidato trazable en MLflow nativo, sin alias,
incluyendo datos/configuración/código/dependencias, trigger, parámetros,
validación y artefactos. Verificará champion v4 antes/después. La copia
Docker y la API permanecerán en v4; su actualización corresponde a T35.

Se necesita autorización para descargar **solo** Yellow Taxi abril, mayo y
junio 2026 oficiales, actualmente enlazados por TLC, a data/raw/2026/MM.
Máximo **512 MiB por archivo y 1 GiB total**, con contador persistente y
bloqueo estricto antes de excederlo; fuente/fecha/hash reales. Sin descargas
de paquetes u otros meses. Registrar, validar y construir features no
autoriza consumir lotes nuevos que fallen D-04: se presentará cada caso
por mes/hash/reporte antes de aceptarlo. Las excepciones anteriores no se
extienden a los nuevos meses.

Si no se autorizan nuevas descargas/periodos, se puede verificar el motor
con fixtures, pero la comparación final real independiente quedará pendiente.

## Aprobación 3 — T34: gate comparativo

Antes de evaluar abril–junio 2026 se congelan protocolo, candidato, champion
v4, rutas y hashes. Una única comparación emparejada sobre todas las mismas
filas elegibles y etiquetas maduras. El candidato no se ajusta después de
abrir ese periodo; un resultado desfavorable se conserva.

- Métricas exactas MAE/RMSE/MedAE/P90, con cuantiles en disco.
- Para quedar ELIGIBLE_FOR_HUMAN_REVIEW: mejora global de MAE **>=2 %**,
  RMSE y P90 globales **sin empeorar**, y aumento de MAE/P90 **<=5 %** en
  cada mes, cada franja de seis horas y las 20 rutas T17 ya congeladas.
- Mínimo 1.000 filas por segmento requerido, misma cobertura entre modelos.
  Segmento insuficiente: NOT_EVALUABLE, sin aprobación implícita ni eliminar
  segmentos para conseguir PASS. El margen 5 % es una propuesta del proyecto
  pendiente; no se presenta como requisito académico ya confirmado.
- Calidad aceptada con D-04 y excepciones exactas, integridad, ausencia de
  leakage, esquema, serialización y smoke aislado satisfactorios. Mejora
  numérica no compensa fallos de estos controles. Destino solo segmenta.
- Challenger inferior o gate incumplido: CHALLENGER_REJECTED; evidencia
  insuficiente/corrupta: BLOCKED/NOT_EVALUABLE, según el motivo.
- No activar la alternativa de no inferioridad: se exige la mejora 2 %
  propuesta. No se hará promoción automática ni se ejecutará T35.
- Reporte versionado con identificador, timestamp, configuración y hashes
  de evidencias/modelos. La integridad SHA-256 no es una firma digital de
  identidad ni se declarará como tal; no se añade infraestructura de firma.

## Archivos previstos y pruebas

Crear src/retraining/{triggers,train_challenger,compare}.py y auxiliares
necesarios para protocolo/particiones nuevas, configs/retraining.yaml,
pruebas unitarias/integración con fixtures y reportes Markdown en
reports/retraining/. Reutilizar lectura por bloques, workers, supervisión,
métricas, serialización y MLflow existentes. No relajar verificadores de
configuración histórica para habilitar el nuevo ciclo.

Pruebas: límites exactos 115 %/PSI/2 %/5 %, meses consecutivos y faltantes,
etiquetas ausentes, n mínimo, informes/modelos/protocolos incompatibles,
hashes alterados, calidad no aceptada, sin trigger no entrena, fit train-only,
cortes/DST y cobertura completa, límites RAM/tiempo/descarga, idempotencia,
registro sin alias, reload/smoke, candidato peor rechazado y mejora bloqueada
por segmento/calidad. Fixtures nunca podrán consumirse como datos reales.
Ruff, tests apropiados, auditoría de ejecuciones y documentación coherente;
CI mantiene el perfil aprobado de fixtures sin entrenamientos reales.

Aceptación: T32 con decisión auditable, T33 con fit/registro trazable y
champion intacto, T34 con comparación real y decisión justificada. Una
comparación correctamente rechazada satisface T34; no se fuerza un ganador.
No marcar cierre real por aprobar únicamente las pruebas sintéticas.

Se actualizarán plan/spec/intent/decisiones y el registro del merge anterior
al aplicar el alcance aprobado. Esta solicitud no incluye nuevos commits,
push, PR, promoción, rollback ni T35–T38.
