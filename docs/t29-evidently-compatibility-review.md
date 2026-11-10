# T29 — Incompatibilidad comprobada y propuesta de aislamiento

Estado: APROBADA por el usuario en conversacion. Fecha: 2026-11-09.

Evidencia: la instalación offline terminó y `pip check` pasó, pero importar
Evidently 0.7.23 con pandas 3.1.1 falla en
`evidently.legacy.tests.data_integrity_tests`: intenta importar
`pandas.core.dtypes.common.infer_dtype_from_object`, que no existe en ese
pandas. Nueve pruebas propias pasaron y la integración real falló. No se
parchean librerías ni se oculta la integración con una omisión.

Se verificaron metadatos oficiales y wheels Python 3.14 para pandas 2.3.3 en
Windows amd64 y Linux x86_64. Eso no acredita aún que Evidently funcione.

Propuesta:

1. Fijar pandas 2.3.3 exclusivamente en `.venv-monitoring` y su imagen CI de
   reportes; demás versiones compartidas conservadas. Locks propios, hashes
   y descargas dentro del contador adicional aprobado de 256 MiB.
2. Ejecutar el CLI, lectura y predicciones reales con `.venv-mlflow`, cuyo
   pandas 3.1.1 y dependencias históricas no cambian. El modelo congelado se
   verifica antes/después del replay y se prueba contra predicciones de
   referencia, sin reajustarlo.
3. Entregar a un subproceso local de reportes solo los bins agregados JSON,
   no modelos, viajes individuales ni etiquetas. Ese subproceso usa Evidently
   y pandas 2.3.3 para producir JSON/HTML. Sin servidor nuevo ni Cloud.
4. Supervisar el subproceso propio: timeout vigente y suma de RSS medida de
   coordinador/renderer <=2 GiB; un mes a la vez. Presupuesto sin ampliación.
5. CI prueba la suite histórica en el runtime original y la integración
   Evidently por separado, secuencialmente con el perfil CI aprobado.

Si la integración vuelve a revelar incompatibilidades que exijan cambiar
versiones adicionales, consultar antes de hacerlo. El protocolo estadístico,
D-04, modelo, referencia temporal y alcance de publicación no cambian.
