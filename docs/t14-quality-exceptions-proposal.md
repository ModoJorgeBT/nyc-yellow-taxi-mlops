# T14 — Solicitud de aceptación excepcional de nueve lotes

Fecha: 2026-11-05, America/Costa_Rica. **APROBADA Y APLICADA.** Respuesta: «Sí, aprobar los nueve meses con esas exclusiones y trazabilidad». Se aplicaron las nueve autorizaciones individuales, se excluyeron las 543.725 filas inválidas y se conservó cada FAIL original. Las 24 versiones y sus particiones terminaron la auditoría: [cierre técnico T14](../reports/quality/t14_completion.md). No autoriza incumplimientos nuevos automáticamente.

Se verificaron nuevamente tamaño/SHA-256 de los nueve raw, sus manifiestos, los reportes FAIL originales y la coincidencia con la configuración congelada. El [registro exacto de la propuesta y aprobación](t14-quality-exceptions-proposal.json) fija mes, hash raw, hash del reporte, configuración y conjunto completo de fallos. Las autorizaciones ejecutables son los archivos individuales de configs/; la excepción v1 de marzo se conserva intacta.

## Incumplimientos concretos

D-04 bloquea duración no positiva por encima de **0,50 %** y unión de filas inválidas por encima de **1,00 %**. Abril incumple solo la primera regla; mayo–diciembre incumplen ambas.

| Mes | Duración no positiva | Total filas inválidas | Filas excluidas | Elegibles antes del corte temporal |
|---|---:|---:|---:|---:|
| 04/2025 | 0,875671 % | 0,915968 % | 36,369 | 3,934,184 |
| 05/2025 | 1,399699 % | 1,433541 % | 65,826 | 4,526,019 |
| 06/2025 | 1,586482 % | 1,618868 % | 69,983 | 4,252,977 |
| 07/2025 | 1,437921 % | 1,469339 % | 57,289 | 3,841,674 |
| 08/2025 | 1,338326 % | 1,374671 % | 49,132 | 3,524,959 |
| 09/2025 | 1,345067 % | 1,382046 % | 58,751 | 4,192,264 |
| 10/2025 | 1,534717 % | 1,573058 % | 69,666 | 4,359,033 |
| 11/2025 | 1,447275 % | 1,829966 % | 76,519 | 4,104,925 |
| 12/2025 | 1,347757 % | 1,398140 % | 60,190 | 4,244,816 |

Total: **37,524,576 filas raw**, **543,725 excluidas** y **36,980,851 potencialmente elegibles**. Las elegibles aún no son datos aprobados y pueden reducirse al aplicar los cortes de disponibilidad de etiqueta de T14.

## Alcance a aprobar

- Aceptación académica excepcional, individual por mes/hash/reporte, únicamente para los fallos exactos enumerados. Puede aprobarse el conjunto de nueve meses o un subconjunto explícito.
- Todas las filas inválidas siguen excluidas; los FAIL medidos y reportes originales se conservan. La aceptación humana se registra separada de la calidad medida, igual que en marzo.
- D-04 global, periodos, target y reglas de filas permanecen vigentes. Un archivo distinto, reporte alterado, fallo nuevo o medición distinta requiere otra decisión.
- Las autorizaciones nuevas requieren ampliar de forma versionada el lector actual: v1 solo admite duración no positiva; v2 admitirá el conjunto exacto autorizado de duración y unión de inválidos. La compatibilidad de marzo y el rechazo de autorizaciones pendientes/revocadas o ampliadas se probarán antes de aplicar nada real.
- Cada incumplimiento futuro se presentará para decisión y quedará pendiente de aceptación humana. La mera solicitud de consultar no aprueba estos nueve lotes ni otros futuros.

Aceptar esos lotes permite generar features exclusivamente de sus filas elegibles y preparar las cuatro particiones. No cierra T14 por sí solo: se deben auditar cobertura, alineación, hashes, cortes causales y no solapamiento; train/validation se contrastarán con T15 congelada.

## Limitación y continuación

El test final describirá viajes elegibles bajo estas exclusiones; no demostrará desempeño sobre las filas descartadas ni sobre toda la población raw. Las tasas de exclusión por mes deben acompañar los resultados. No se calibran umbrales ni modelos con test/replay y no se cambia la procedencia LOCAL_UNVERIFIED.

Una vez completada y auditada T14, la solicitud actual autoriza continuar con T16/T17. La arquitectura, épocas e hiperparámetros concretos de SGD/MLP y las decisiones de evaluación pendientes se presentarán antes del entrenamiento real, respetando D-02; no se instalarán dependencias ni se promoverán modelos sin las autorizaciones correspondientes.

Documentos previstos después de aprobar: autorizaciones públicas por mes en configs/, ampliación de src/validation/exceptions.py con pruebas de integración, catálogo local de 24 versiones, artefactos/features/particiones locales y reporte de auditoría. Se actualizarán plan.md, spec.md, intent.md, README y decisiones según evidencia real. No se crea un commit ni push por esta tarea.
