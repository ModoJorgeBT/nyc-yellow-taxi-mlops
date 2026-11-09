# INTENT — NYC Yellow Taxi MLOps

## 1. Identidad y contexto
Proyecto de maestría de Universidad CENFOTEC, curso Tópicos Especiales en Analítica de Datos. Equipo: Bernal Rojas, Jorge Garnier y Jorge Bermúdez.

## 2. Problema
Estimar, al inicio de un viaje de taxi amarillo en Nueva York, su duración en minutos utilizando información disponible en ese instante. Además de obtener predicciones, demostrar cómo operar un modelo de forma reproducible, verificable y controlada durante todo su ciclo de vida.

## 3. Objetivo principal
Construir una plataforma MLOps modular y reproducible que ingiera datos mensuales públicos de NYC TLC, valide su calidad, prepare características, entrene y compare modelos, registre experimentos y versiones, publique inferencia mediante API, automatice pruebas y construcción, monitoree cambios y habilite reentrenamiento y rollback bajo reglas explícitas.

## 4. Usuarios y valor
- Equipo de desarrollo y evaluación académica: reproducir y auditar el flujo completo.
- Consumidor de API de demostración: solicitar una estimación de duración al comienzo del viaje.
- Operador de la plataforma: inspeccionar calidad, versiones, salud del servicio y decisiones de promoción.

## 5. Alcance funcional
1. Ingesta parametrizada por año y mes de archivos Parquet de NYC TLC, con metadatos, hash e idempotencia.
2. Validación automática de esquema, fechas, volumen, duplicados, nulos, rangos y trazabilidad; fallar explícitamente ante incumplimientos críticos.
3. Preparación reproducible de datos y características consistentes entre entrenamiento e inferencia.
4. Baseline y al menos dos modelos candidatos; partición temporal; evaluación con MAE como métrica principal y RMSE, MedAE y P90 del error absoluto como complementarias.
5. Tracking y registro de modelos en MLflow, con referencia a datos y código.
6. API FastAPI con POST /predict, GET /health y GET /model-info, validación Pydantic y versión de modelo en la respuesta.
7. Docker/Compose y CI mediante GitHub Actions.
8. Monitoreo de calidad, drift, desempeño cuando exista verdad observada y salud operativa.
9. Reentrenamiento condicionado; comparación challenger/champion, promoción controlada y rollback demostrable.
10. Documentación y pruebas para reproducibilidad por otra persona.

## 6. Principios y restricciones
- Predecir exclusivamente duración del viaje, en minutos.
- Definir el target a partir de la diferencia entre timestamps de llegada y recogida, solo para construir etiquetas históricas.
- No utilizar en inferencia información posterior al inicio del viaje: hora de llegada, tarifa final, propina, pago, peajes o cargos finales.
- Excluir del MVP la distancia real del taxímetro (`trip_distance`), porque no se conoce al inicio.
- Usar zonas de origen y destino, momento de recogida y otras variables solo si son conocidas en el instante de predicción.
- Evitar fugas temporales también en agregados históricos, imputación y validación.
- Priorizar una implementación local, modular y defendible; no añadir Kubernetes, Kafka, Airflow o infraestructura cloud sin una necesidad aprobada.
- No almacenar secretos, archivos Parquet grandes, modelos binarios ni artefactos locales de MLflow directamente en Git.
- No permitir que un agente cambie el objetivo, introduzca nuevas tecnologías principales o promueva modelos sin aprobación.

## 7. Criterios de éxito
- Otro integrante puede clonar el repositorio y ejecutar el flujo documentado.
- La ingesta admite año/mes por configuración y produce evidencia de procedencia.
- Los controles críticos de calidad bloquean lotes inválidos y registran el motivo.
- El pipeline produce métricas temporales reproducibles y registra experimentos en MLflow.
- La API valida solicitudes, devuelve duración estimada, unidad y versión del modelo.
- La imagen Docker se construye con un workflow CI reproducible.
- Se demuestra al menos un escenario de drift y una decisión documentada de reentrenar o no.
- Se demuestra comparación champion/challenger y un mecanismo de rollback.
- El éxito del proyecto se mide por el ciclo MLOps demostrable, no solo por la precisión del modelo.

## 8. Decisiones confirmadas y pendientes
- Confirmado por el equipo en la conversación de T01 (2026-11-03): Python, MLflow, FastAPI y Docker Compose; demostración y ejecución locales. Esto no fija versiones ni aprueba automáticamente herramientas adicionales.
- Acuerdo T03 (2026-11-03): Python 3.14.7, entorno `.venv`, setuptools, Ruff, Pytest y pip-tools con versiones fijadas y hashes; PyArrow aprobado para la revisión de metadatos/esquemas locales. No implica compatibilidad ya probada del stack MLOps completo.
- Acuerdo T12/T13: scikit-learn, tzdata y dependencias necesarias aprobadas, fijadas y probadas con fixtures. Origen, calendario y pasajeros opcionales aprobados bajo conteo conocido al abordar; destino deshabilitado. Convención histórica America/New_York, apartando horarios ambiguos/inexistentes y calculando duración en UTC. [Contrato y evidencia](docs/t12-t13-features.md).
- D-01 aprobada: entrenamiento 2024 completo, validación enero–marzo 2025, test final abril–junio 2025 y replay de monitoreo julio–diciembre 2025. Sustituye la propuesta académica inicial; no exige descargar 2026. [Protocolo y controles temporales](docs/d01-d02-protocol.md).
- Las herramientas adicionales aún no autorizadas, incluida Evidently, permanecen pendientes. D-07 aprobó e implementó MLflow y sus dependencias exclusivamente en el entorno separado T18. GitHub Actions permanece en el alcance de CI; la aprobación de herramientas se registra por separado.
- Destino deshabilitado en la versión actual por aprobación T12/T13; reintroducirlo requiere una nueva decisión causal explícita.
- D-02 vigente T16/T17: todos los elegibles, SGD/MLP incrementales, cuatro hilos, un candidato, 4 GiB RSS y dos horas por candidato; preflight 8 GiB RAM/50 GiB disco libres. El usuario aprobó [la revisión 8/4](docs/d02-t16-resource-review.md) tras fallar el mínimo inicial 12/8. Controles probados con fixtures y respetados en el ajuste real de SGD/MLP y su evaluación. Preparación T14/T15 conserva su perfil histórico 4/2. Drift/promoción y criterio general de PR pendientes.
- D-04 ratificada/congelada para v1: [política](docs/d04-quality-proposal.md), perfil real implementado y piloto enero 2024 aprobado con WARN. Autorización académica ampliada a los 24 archivos actuales por mes/hash, conservando LOCAL_UNVERIFIED; no implica su incorporación automática. [Activación y resultados](docs/d04-activation.md).
- Estados y riesgos: [registro](docs/decisions.md). T15 tiene ajuste/evaluación auditados y congelados: mediana 12,983333 min, MAE 7,741890 min y RMSE 11,912962 min en validation. T14 integral terminó técnicamente y confirmó el mismo train/validation, con cuatro particiones y 24 meses auditados. [Evidencia](reports/quality/t14_completion.md). La primera comparación T16/T17 está ejecutada y auditada, con SGD elegido antes de abrir test; replay sigue sin métricas predictivas. No hay registro ni promoción. Procedencia desconocida y excepciones de calidad explícitas conservadas.
- Continuación 2026-11-05: los incumplimientos D-04 se presentan para aceptación humana antes de consumirlos. Las nueve excepciones exactas de abril–diciembre están aprobadas y aplicadas, con 543.725 exclusiones y FAIL originales intactos. T14 integral terminó su auditoría sobre 24 meses; T16/T17 se ejecutaron después según [protocolo aprobado](docs/t16-t17-execution-proposal.md) y D-02, sin nuevas excepciones automáticas ni promoción.

## 9. Instrucciones para el agente de desarrollo
1. Leer `intent.md`, `spec.md` y `plan.md` antes de modificar código, cuando estén disponibles.
2. Si `spec.md` o `plan.md` aún no existen, no inventar requisitos ni comenzar una implementación integral: proponer primero las decisiones faltantes.
3. Implementar en incrementos pequeños, con pruebas y evidencia verificable.
4. Explicar cada cambio importante, los comandos ejecutados y las pruebas realizadas; no declarar como ejecutadas pruebas que no se hayan corrido.
5. Solicitar aprobación antes de cambios de arquitectura, dependencias principales, infraestructura, datos destructivos o promoción de modelos.
6. Mantener alineados documentación, código, configuración y pruebas.

## 10. Fuente de referencia
Documento base: «Diseño de una Plataforma MLOps para Predicción de Duración de Viajes de NYC Yellow Taxi», estructura propuesta y revisión técnica, versión 1.0, septiembre de 2026.


**Resultados T16/T17, 2026-11-05:** SGD Huber y MLP16 se ajustaron con las 41.119.495 filas train, una pasada por candidato. SGD fue elegido con validation antes de abrir test: MAE 6,876910 frente a 7,741890 del baseline. En test obtuvo MAE 7,965068 frente a 9,032999. MLP fue peor que el baseline; SGD empeoró ligeramente P90 en validation. Sin reajustes después de test ni promoción.
[Informe auditado](reports/evaluation/t17_model_comparison.md). El usuario solicitó y aprobó [LightGBM como tercer candidato](docs/t16-lightgbm-extension-proposal.md), con evaluación solo en validation y una nueva evaluación final independiente pendiente. El presupuesto vigente y la prohibición de usar destino como predictor se conservan.

**Extensión LightGBM ejecutada — 2026-11-05:** LightGBM 4.7.0 fue entrenado con las 41.119.495 filas train y 100 árboles. En las 11.163.264 filas validation: MAE 6.496404, RMSE 9.847425, MedAE 4.631360 y P90 13.478764 minutos. Ajuste y evaluación auditados; 447 pruebas por entorno. Solo validation: una nueva evaluación final independiente sigue pendiente. La selección SGD y el test de la primera comparación permanecen intactos; no hay promoción. [Evidencia](reports/evaluation/lightgbm_validation.md).


**Evaluación final independiente completada y auditada — 2026-11-05:**
enero–marzo de 2026, 10.937.087 viajes; MAE LightGBM **7,742891 min**, SGD
**8,352735** y baseline **9,141254**. Se excluyeron 139.305 filas DQ mediante
tres excepciones humanas exactas y 814 por corte de etiqueta; los 27 raw,
modelos y selección de 2025 permanecen intactos. Reinicio de recursos aprobado
6 GiB libres/2 GiB RSS solo para inferencia final; entrenamiento 8/4 y preparación
4/2 sin cambios. 474 pruebas por entorno y auditoría completa. Sin promoción.
[Reporte final y trazabilidad](reports/evaluation/lightgbm_final_evaluation.md). Las referencias anteriores a evaluación
final pendiente describen la entrega histórica previa a esta aprobación. T18
requiere D-07 y dependencias; no hay Registry ni champion todavía.


**T18 verificada — 2026-11-05:** D-07 aprobada e implementada con MLflow 3.16.1
en entorno separado, SQLite y artefactos persistentes. Cuatro candidatos:
baseline v1, SGD v2, MLP v3 y LightGBM v4, sin alias. Reinicio real, carga,
idempotencia y auditoría independiente PASS; 488 pruebas nativas más una omisión
explícita y 489 sobre wheel MLflow. Los modelos y evaluaciones anteriores no
cambian. Champion/T19 y G3 permanecen pendientes de aprobación.
[Registro y evidencia](reports/tracking/t18_completion.md). Las referencias previas a D-07 o Registry
pendientes describen la cronología anterior a esta aprobación y ejecución.


**T19 verificada — 2026-11-05:** el usuario aprobó LightGBM v4 como champion
inicial, después de conocer las limitaciones por rutas, y descartó optimización
de hiperparámetros. Alias `champion` aplicado a la versión fija 4, run
`be28c76c84c44efa8914c5950a2959bf`; paquete, aprobación y resolución auditados.
501 pruebas nativas PASS y dos omisiones explícitas; 503 PASS sobre wheel MLflow.
G3 cumple sus condiciones de Sprint 3. D-05 conserva pendientes sus reglas
automáticas de drift y promociones futuras; no se aprueban nuevos umbrales.
[Decisión, pruebas y evidencia](reports/model_selection.md). Las menciones anteriores a champion
pendiente son históricas; API y despliegue siguen en sus tareas posteriores.


**Continuación T20–T22 — 2026-11-09:** contrato D-06 y HTTPX aprobados explícitamente.
Esquemas, carga segura del champion LightGBM v4 y endpoints FastAPI verificados;
553 casos serving, 501 nativos y 51 sobre wheel fuera de src. El reinicio
sintético de T18 necesitó reintento fuera del sandbox; pasó y se limpió su proceso.
Registry, modelos, evaluaciones y locks históricos intactos. Sin recarga
automática; Docker/T23–T25 y G4 pendientes. [Contrato y evidencia](docs/t20-t22-serving.md).
Las menciones previas a API/contrato REST pendientes describen su estado histórico.


**T23–T25 verificadas — 2026-11-09:** build Docker Linux amd64, usuario
10001 y límites 2 GiB/2 CPU por API/MLflow verificados; smoke real 200/422/503,
reinicio y persistencia PASS. G4 cumple técnicamente su alcance. API en 8080
y MLflow Docker en 5001, solo loopback; originales conservados. El usuario
aprobó el perfil Linux, el cambio de puerto y la auditoría portable de
metadatos sin modificar datos. Volumen Linux aislado con champion v4;
sin reentrenamiento ni promoción nueva. [Guía y evidencia](docs/t23-t25-docker.md).
Las menciones previas a Docker pendiente describen estados históricos;
T26–T38 y la revisión humana de resultados permanecen independientes.

**Actualización T26–T28 — 2026-11-09:** T27/T28 verificadas técnicamente:
métricas operativas Docker y comparación de calidad/schema con referencia
aprobada de train 2024 frente al mismo mes del replay julio–diciembre 2025.
D-04, excepciones, pesos y champion conservados. Workflow T26 preparado con
perfil exclusivo CI aprobado 2 CPU/4 GiB/10 GiB disco/20 minutos; ejecución
GitHub pendiente de publicación autorizada. G5 y T29–T31 siguen abiertos.
[Detalle y límites](docs/t26-t28.md).
