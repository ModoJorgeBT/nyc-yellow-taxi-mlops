# D-02 — Revisión de recursos para inferencia final congelada

**Actualización de ejecución: APLICADA Y AUDITADA.** [Resultado final](../reports/evaluation/lightgbm_final_evaluation.md).
Las secciones siguientes conservan la propuesta y el estado previo a ejecutar.

Fecha: 2026-11-05, America/Costa_Rica. **APROBADO POR EL USUARIO: perfil 6/2 exclusivamente para inferencia final y reinicio trazado.** No autoriza cambiar entrenamiento, datos ni modelos.

La primera ejecución final `f913cf2217fb4c58b8da47895f42b463` se detuvo antes de LightGBM: el preflight por candidato midió **8.453.607.424 bytes (7,873 GiB) libres**, menos de los 8 GiB vigentes. El control funcionó: no se amplió el límite, no se redujeron filas y no se publicó una evaluación completa. El reporte FAIL y la reserva original se conservarán.

Después de terminar el proceso se midieron 8.571.985.920 bytes libres, todavía ligeramente por debajo del mínimo. La memoria disponible cambia con el uso del equipo. No se cerrarán aplicaciones del usuario automáticamente.

## Perfil específico propuesto

| Control | Vigente | Propuesta solo para esta evaluación final |
|---|---:|---:|
| RAM libre mínima por candidato | 8 GiB | **6 GiB** |
| RSS máximo del proceso | 4 GiB | **2 GiB** |
| Hilos | 4 | 4 |
| Concurrencia | Un modelo | Un modelo |
| Disco libre mínimo | 50 GiB | 50 GiB |
| Tiempo por candidato | 2 horas | 2 horas, incluyendo verificación compartida |
| Filas | Todas las elegibles | Las mismas **10.937.087** |
| Ajustes de modelos | Prohibidos | Prohibidos |

Este trabajo ejecuta únicamente inferencia de modelos congelados. Como evidencia previa, la comparación original T17 usó aproximadamente 0,563 GiB RSS y la validación LightGBM 0,481 GiB; la auditoría completa del nuevo holdout usó aproximadamente 0,467 GiB. Son mediciones de esas ejecuciones, no una garantía de coste idéntico. El nuevo máximo de 2 GiB se instrumentará y probará antes del reinicio; cualquier exceso detendrá el intento.

La implementación liberará buffers y cachés propios entre candidatos. No se cerrarán otros procesos, se modificará memoria del sistema ni se aplicará muestreo. Si el perfil tampoco pasa, se detiene y consulta.

## Conservación del experimento

- Mantener intactos `configs/lightgbm-final-evaluation.yaml`, el holdout `be5aef1e584949b897ccfd7b25d478fc` y su auditoría; tampoco se regeneran features ni se modifican las 139.305 exclusiones DQ y 814 exclusiones temporales.
- Registrar la revisión aprobada en un contrato separado de recursos. No reescribir el perfil de entrenamiento 8/4 ni el de preparación 4/2.
- Conservar el primer reporte FAIL, su reserva y su SHA-256. El reinicio debe enlazar ese intento y verificar exactamente los mismos modelos, periodo, datos y métricas. No se reinicia para elegir un resultado favorable.
- Una nueva reserva de reintento será adicional y no reemplazará la original. Las pruebas bloquearán reintentos sin fallo de infraestructura verificable o con datos/modelos cambiados.
- No hay promoción, elección de champion ni cambios D-04. T18 conserva su aprobación D-07 y de dependencias por separado, después del reporte final auditado.

Alternativa: mantener 8/4 y continuar cuando el equipo tenga suficiente RAM libre por candidato. Ninguna alternativa permite reducir los datos ni reajustar modelos usando resultados de 2026.

Registro: el usuario aprobó «Sí, aprobar el perfil final 6 GiB libres/2 GiB RSS y el reinicio trazado». [Contrato de ejecución](../configs/lightgbm-final-resources.yaml); implementación/pruebas y reanudación aún pendientes.
