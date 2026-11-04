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
- Aprobación de herramientas adicionales no incluidas en el acuerdo T03, incluida Evidently, pendiente. GitHub Actions permanece en el alcance de CI; la aprobación de herramientas se registra por separado.
- Destino deshabilitado en la versión actual por aprobación T12/T13; reintroducirlo requiere una nueva decisión causal explícita.
- D-02 aprobada: todas las filas elegibles, sin submuestreo de modelado; SGDRegressor y MLPRegressor pequeño incrementales, cuatro hilos, un candidato a la vez, 8 GiB y dos horas por candidato; preflight 12 GiB RAM libre/50 GiB disco libre. Controles por implementar antes de entrenar. Drift/promoción y criterio general de PR pendientes.
- D-04 ratificada/congelada para v1: [política](docs/d04-quality-proposal.md), perfil real implementado y piloto enero 2024 aprobado con WARN. Autorización académica ampliada a los 24 archivos actuales por mes/hash, conservando LOCAL_UNVERIFIED; no implica su incorporación automática. [Activación y resultados](docs/d04-activation.md).
- Estados y riesgos: [registro de decisiones](docs/decisions.md). T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [evaluación real auditada](reports/quality/t15_baseline_validation.md). Marzo aceptado por excepción humana solo para su hash/reporte; FAIL original y exclusiones conservados, sin cambiar D-04 global. T14 integral sigue pendiente; test/replay sellados, T16 no ejecutada y sin registro/promoción. No se aprende de 2025; solo se evalúa validation. Calidad medida y aceptación humana se distinguen; procedencia desconocida conservada.

## 9. Instrucciones para el agente de desarrollo
1. Leer `intent.md`, `spec.md` y `plan.md` antes de modificar código, cuando estén disponibles.
2. Si `spec.md` o `plan.md` aún no existen, no inventar requisitos ni comenzar una implementación integral: proponer primero las decisiones faltantes.
3. Implementar en incrementos pequeños, con pruebas y evidencia verificable.
4. Explicar cada cambio importante, los comandos ejecutados y las pruebas realizadas; no declarar como ejecutadas pruebas que no se hayan corrido.
5. Solicitar aprobación antes de cambios de arquitectura, dependencias principales, infraestructura, datos destructivos o promoción de modelos.
6. Mantener alineados documentación, código, configuración y pruebas.

## 10. Fuente de referencia
Documento base: «Diseño de una Plataforma MLOps para Predicción de Duración de Viajes de NYC Yellow Taxi», estructura propuesta y revisión técnica, versión 1.0, septiembre de 2026.
