# Cierre técnico T35–T38 y evaluación G6

**CIERRE TÉCNICO PASS — 2026-11-10, America/Costa_Rica.** Revisión cruzada
humana y defensa oral NO VERIFICADAS, según separación aprobada explícitamente.

Alcance [aprobado](../../docs/t35-t38-execution-proposal.md): mecanismo y demo
sintética aislada, workflow local con reutilización trazada, reproducción offline
y materiales académicos. Champion real v4 intacto; v5 real rechazado. No hay
nuevos datasets, fits reales, consumo de holdout ni commit/push.

## Evidencia ya ejecutada

T35: .cache/t35-t38/demo-external/demo-result.json,
LIFECYCLE_DEMO_TEST_ONLY_PASS. Promoción/rollback manual desde otro proceso,
gate negativo bloqueado y caída HTTP compensada. Servicios propios detenidos.
Pico combinado 1.576.103.936 bytes (<2 GiB); puertos aislados 49377/49378.

T36: .cache/t35-t38/workflow-first/workflow-result.json,
WORKFLOW_TEST_ONLY_COMPLETE. 48 filas de train sintéticas, LightGBM fit,
evaluación/registro/compare en MLflow aislado; candidato sin alias. Gate
NOT_EVALUABLE por segmentos pequeños, sin promoción. Sin trigger no se llamó
a ninguna etapa. Pico combinado 992.325.632 bytes; servicios propios detenidos.
Reanudación real verificada en a0ffd7a4748b40679364cfa59a07f328.json: reutiliza
T32–T34, cero fits/evaluaciones/descargas y cero cambios de alias.
resume verifica una campaña completa existente; no reanuda automáticamente
un fit parcial ni ejecuta una campaña científica nueva sin otra aprobación.

## Verificación final

Reproducción offline final PASS: **681 pruebas aprobadas y una omisión prevista**
en 682 casos distintos, sin errores/fallos en las fases finales. Ruff, formato
(146 archivos) y pip check PASS. El entorno principal .venv-mlflow también
quedó actualizado con el mismo wheel, sin dependencias nuevas; pip check PASS.

Primer export .cache/repro35b: 680 PASS/una omisión prevista, 416,59 segundos;
venv limpio, Ruff/formato/pip check PASS, cero descargas. Tras la comprobación
adicional del champion previo se verifica una nueva fotografía final en
.cache/repro38, conservando intacta la evidencia del primer export.

El intento inicial de .cache/repro38 se detuvo con 148 PASS y un FAIL: API
sintética sin health=200 dentro de 90 segundos. Conserva pytest.log y el JUnit
original; sus servicios se detuvieron. Diagnóstico posterior de carga directa
del mismo artefacto: PASS. Repetición de ese caso HTTP: **1 PASS**, 175,59 s,
sin cambiar código, límites, paquetes ni artefactos científicos. La causa raíz
del timeout no está confirmada; se registra como riesgo de arranque local.
Las restantes terminaron: **680 PASS, una omisión y un caso deseleccionado**,
201,57 s, mismo venv limpio y otro temporal/JUnit. Ese caso corresponde al
HTTP aprobado por separado: la unión contiene 682 casos disjuntos, 681 PASS y
una omisión. No se repitió ningún fit real ni el holdout. El renderer Evidently
se omite por entorno separado, conforme a su protocolo; no es una omisión nueva.

Recibo final: .cache/t35-t38/final-completion.json. Auditoría de 30 hashes raw
y 28 archivos originales PASS; champion=4, rechazo de v5 comprobado antes de
writes. 306 archivos del export verificados; sus 71 fuentes empaquetadas
coinciden byte a byte con el código final y el SDK nativo instalado. 399 enlaces
locales válidos al cierre.
El export conserva los documentos del momento de ejecutar las pruebas; esta
síntesis y sus estados se actualizaron después, sin modificar el código probado.

| Artefacto local | SHA-256 |
|---|---|
| Wheel final del proyecto | c162da4c19391e1c65cfa63ea2b17ba1c433e3992ebc4ada73c219868785eac2 |
| Manifiesto del export | 55994553f73ca6eeae1e81db82b9bc62f6ec3ba7d73836544b3935c542169edf |
| Recibo de reproducción final | e2fa990986be9798954e1ea1132ef8ccaa2f9376883c87786c3a01a9e231bd27 |
| JUnit HTTP repetido | 6e518f4e76689c4515931c12a27b2c3656b5582adc6241c517b5caf3e7efe177 |
| JUnit restante | 2d229b8ef7a6519ef9bcca74f2d80a46470a5e6562eb16cbca7672d6cb7ca9c5 |
| Demo lifecycle externa | c094d04ee3add6baef8eb4ea60e5f6f4f890e331a1f7984b4d75c33eb28cec09 |
| Demo workflow | 4125e705ceabe4896f23efea581459cddd4691eebc1d5154a6a5a0319e0d3e0e |

Los dos JUnit finales y sus logs están bajo .cache/repro38; el original fallido
se conserva por separado. El recibo señala explícitamente la reanudación y
mantiene el mismo wheel, export, locks y presupuesto: no simula un primer intento
sin incidentes ni atribuye la revisión a una persona.

**Actualización documental posterior:** el usuario solicitó la quinta entrega
Git y renovar el README. Su alcance y la consulta del SHA figuran en el
[historial](../../docs/commit-history.md). Las menciones «sin commit/push» de
este cierre describen la ejecución técnica previa a esa solicitud; no se cambian
sus recibos, métricas, hashes ni resultados de prueba al preparar la entrega.

La revisión añadió comprobación de identidad del champion previo para futuras
promociones reales y detección de cambio externo al repetir una promoción ya
verificada. Sus pruebas específicas pasaron. Primer intento de export detenido
por distinto propietario Git; corregido con safe.directory acotado a cada
lectura de esta raíz, sin configuración global. Un intento inicial de tests
en temporal ajeno falló por ACL; repetir en temporal nuevo resolvió ese bloqueo,
sin borrar directorios existentes ni cambiar contratos.

## G6 y revisión humana

| Condición | Evidencia/estado |
|---|---|
| Ciclo científico real y rechazo trazado | T32–T34 PASS; v4 champion/v5 sin alias |
| Operación reversible y compensación | T35 PASS TEST_ONLY con HTTP/MLflow reales |
| Workflow sin promoción automática | T36 PASS TEST_ONLY y reanudación real verificada |
| Reproducción automática limpia | T37 PASS técnico, con timeout/repetición trazados y cero descargas |
| Guion, runbook y presentación | T38 PASS técnico; material Markdown y afirmaciones trazadas |
| Otro integrante clona y ejecuta | NO VERIFICADO, pendiente humano aprobado explícitamente |
| Defensa oral académica | NO VERIFICADA, pendiente humano |

**G6 PASS técnico** dentro del alcance aprobado, separado de los dos últimos renglones.
No se atribuyen a modelos reales mejoras de las fixtures ni se afirma una
transacción distribuida, promoción de v5 o actualización remota del repositorio.
