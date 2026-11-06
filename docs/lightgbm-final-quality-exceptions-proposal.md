# Evaluación final LightGBM — Tres excepciones D-04 propuestas

**Actualización de ejecución: APLICADA Y AUDITADA.** [Resultado final](../reports/evaluation/lightgbm_final_evaluation.md).
Las secciones siguientes conservan la propuesta y el estado previo a ejecutar.

Fecha: 2026-11-05, America/Costa_Rica. **TRES EXCEPCIONES EXACTAS APROBADAS POR EL USUARIO. Aplicación pendiente; todavía sin métricas predictivas de 2026.**

El usuario aprobó enero–marzo de 2026 y sus tres descargas oficiales limitadas. Se descargaron y verificaron 190.739.682 bytes, 11.077.206 filas raw, con URL y fecha UTC reales. D-04 v1 se aplicó completa, sin modificar reglas. Los tres lotes fueron REJECTED por exactamente los dos fallos siguientes; no se han habilitado features ni evaluación real con ellos.

| Mes | Raw | Duración no positiva (máximo 0,50 %) | Unión de inválidos (máximo 1,00 %) | Excluir por DQ | Elegibles antes del corte |
|---|---:|---:|---:|---:|---:|
| 2026-01 | 3,724,889 | 1.209969 % | 1.257272 % | 46,832 | 3,678,057 |
| 2026-02 | 3,399,866 | 1.194106 % | 1.239490 % | 42,141 | 3,357,725 |
| 2026-03 | 3,952,451 | 1.243102 % | 1.273438 % | 50,332 | 3,902,119 |

Se propone aceptar excepcionalmente **solo estos tres lotes y sus hashes**, excluyendo **139.305 filas inválidas** en total y conservando **10.937.901 elegibles antes del corte temporal**. No se aceptan las filas inválidas ni se cambia D-04 global. Las exclusiones por disponibilidad de etiqueta del 1 de abril de 2026 se aplicarán adicionalmente.

La autorización se ligará a mes, SHA-256 raw, configuración, SHA-256 del reporte original, conjuntos exactos de checks FAIL, observaciones y límites. El lector v2 existente exige que coincidan y conservará FAIL medido, quality_passed=false y la aceptación humana explícita. Otro archivo, otro fallo o nuevas mediciones no quedan cubiertos.

Datos completos y checks originales: [propuesta estructurada](lightgbm-final-quality-exceptions-proposal.json). No se cambian fuente/fecha de descarga, modelos congelados, periodos, catálogo, normalizaciones ni protocolo final. Estos son archivos DOWNLOADED de fuente oficial; no se inventa procedencia ni se usa la autorización LOCAL_UNVERIFIED de 2024/2025.

La decisión de calidad se solicita **antes** de observar errores predictivos. La evaluación describirá exclusivamente la población elegible y declarará las tres excepciones y exclusiones. No se elegirán meses ni filtros por el desempeño del modelo.

Si se aprueba: crear `configs/quality-exception-2026-01.json`, `-02.json` y `-03.json`; probar su enlace exacto mediante el lector existente, revalidar secuencialmente, contrastar conteos con los originales, generar features y auditar el corte. Si no se aprueba, se conserva el rechazo y se revisa la fuente antes de usarla. No se inicia MLflow ni se promueve un modelo por esta autorización.

Aprobación recibida: «Sí, aprobar las tres excepciones exactas con exclusiones y trazabilidad». Las tres autorizaciones v2 se crearon y el lector comprobó sus enlaces contra los reportes FAIL originales; falta la revalidación completa y su auditoría.
