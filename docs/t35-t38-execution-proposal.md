# T35–T38 — Propuesta para aprobación

2026-11-09, America/Costa_Rica. **APROBADA por el usuario en tres respuestas:**
T35/demo aislada, T36/workflow local y T37–T38/cierre técnico con revisión
humana pendiente explícita. T34 rechazó v5 (mejora MAE
0,737317 % <2 %); v4 sigue champion. La solicitud de estas tareas no aprueba
promover v5, modificar umbrales, repetir la evaluación final ni publicar Git.

## T35: promoción y rollback verificables

Propuesta: mecanismo con aprobación explícita por operación, gate elegible,
identidad/paquete/modelo por hash, versión previa recuperable, bloqueo local,
diario PREPARED/APPLIED/VERIFIED y recuperación. Alias, aprobación y reinicio
no forman una transacción atómica: se comprobarán cambios concurrentes y se
fallará sin sobrescribir un estado ajeno. El rollback conserva artefactos y
restaura versión/aprobación previas, con smoke posterior.

El contrato inicial T19 permanece compatible. Un contrato operativo v2
separado permite resolver promociones futuras aprobadas; el loader existente
mantiene v1 y rechaza fixtures como serving real. Solo se reiniciarán APIs
creadas por un controlador con identidad/PID/puerto/directorio verificados;
no se detendrán procesos ajenos ni se actualizará el volumen Docker actual.

Como no existe un challenger real elegible, demostrar promoción y rollback
con **dos modelos sintéticos**, namespace synthetic- y MLflow/FastAPI reales
en SQLite/artefactos nuevos bajo .cache, puertos loopback libres diferentes
de 5000/5001/8000/8080 y recibos TEST_ONLY explícitos. Incluir gate positivo,
negativo, caída de smoke, recuperación parcial y conflicto concurrente.
Intentar promover v5 real deberá bloquear antes de cambiar alias/serving.
No atribuir al modelo real las mejoras artificiales de estas fixtures.

Perfil demo propuesto: 4 GiB RAM libres, máximo RSS combinado 2 GiB, 50 GiB
disco, cuatro hilos de cálculo, un escenario y 20 minutos. Dependencias ya
aprobadas, sin nuevas instalaciones de librerías ni descargas de datos.
La API/Registry reales mantienen champion v4.

## T36: workflow manual

CLI src.retraining.evaluate: planificar, validar y reanudar etapas con
manifiesto/estado y hashes; sin trigger no entrena, con trigger exige datos
aceptados y autorización de ejecución, registra candidato y nunca promueve
automáticamente. Sin workflow remoto adicional ni credenciales de GitHub.

En esta entrega: probar escenarios completos con fixtures y verificar/reusar
la campaña real T32–T34 existente, sin nuevos fits, descargas ni consumo del
holdout. Una nueva campaña científica necesitará aprobación propia. El demo
de promoción T35 sigue siendo una acción separada del workflow T36.

## T37–T38: reproducibilidad y defensa

Preparar exportación aislada del código actual con manifiesto SHA-256,
excluyendo raw/modelos/SQLite/secretos/PDF nuevo/entornos/cachés. Crear venv
limpio con Python 3.14.7 y **solo wheels exactos ya disponibles**; cero nuevas
descargas. Instalar el proyecto, probar CLI/fixtures y demo. Si falta un wheel,
consultar antes de descargar o cambiar versiones. Conservar locks históricos.

El export es una fotografía del trabajo sin commit, no un clon del main
remoto actualizado. La prueba automática aislada acredita reproducibilidad
técnica; **no equivale a otro integrante clonando y ejecutando**. Propuesta:
cierre técnico de T37 con esa evidencia y revisión cruzada humana registrada
como NO VERIFICADA, sin inventar una revisión. La defensa académica también
queda separada de la preparación técnica T38.

Entregar README, docs/runbook.md, matriz de trazabilidad y reports/final con
guion ejecutable, resultados, limitaciones y presentación Markdown. Separar
evidencia científica real, operación actual/histórica y demo TEST_ONLY. No se
generará un PDF/PPT ni se añadirán herramientas para ello sin otra solicitud.
G6 se informará por condición técnica y revisión humana, sin mezclar ambas.

## Archivos, aceptación y pruebas

Crear src/retraining/{promote,rollback,evaluate}.py y auxiliares de estado/
control/aprobación v2; extender el loader solo para el contrato nuevo sin
alterar configs/champion.yaml. Añadir scripts de demo/reproducción, fixtures,
tests, docs/runbook.md y reports/final/*.md. Actualizar documentos rectores,
decisiones/arquitectura e historial con el estado local, sin inventar un SHA.

Aceptar solo si: promoción sin aprobación/gate se bloquea; peor candidato se
rechaza; rollback restaura versión y predicción previas; fallo de smoke se
compensa; estado ajeno no se sobrescribe; no acción no entrena; workflow no
promueve; fixtures no se admiten como reales; reproducción aislada y evidencia
son trazables. Ruff, suite pertinente/completa y smoke HTTP real en aislamiento.

No publicar commits/PR, cambiar champion real, reentrenar ni descargar datos
en este alcance. La publicación y revisión externa podrán solicitarse después
de presentar el resultado concreto y verificable.
