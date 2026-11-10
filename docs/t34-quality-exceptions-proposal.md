# T34 — Excepciones exactas propuestas para abril–junio 2026

**APROBADAS por el usuario en conversación.** Los tres escaneos completos conservaron D-04 y rechazaron los lotes. Aún no se generaron features ni métricas predictivas de este periodo.

| Mes | Raw | Duración no positiva | Unión inválidos/exclusiones | Elegibles antes del corte |
|---|---:|---:|---:|---:|
| 2026-04 | 3,831,240 | 1.292297% | 50,772 (1.325211%) | 3,780,468 |
| 2026-05 | 4,090,836 | 1.272674% | 53,505 (1.307923%) | 4,037,331 |
| 2026-06 | 3,837,248 | 1.297988% | 50,930 (1.327253%) | 3,786,318 |

Los límites globales siguen siendo 0,50 % para duración no positiva y 1,00 % para unión de inválidos. La propuesta excluiría **155,207 filas** y conservaría **11,604,117 elegibles** antes del corte temporal.

Cada autorización quedaría ligada a mes, hash raw, configuración, reporte rechazado y conjunto exacto de mediciones/fallos del [JSON](t34-quality-exceptions-proposal.json). Conservar FAIL, quality_passed=false, exclusiones y procedencia oficial; aceptación excepcional explícita, sin cambiar D-04.

Solo se aplicarían después de aprobación humana. No cubren otros archivos, fallos nuevos, cambios de datos ni promoción. El lector v2 existente ya admite exactamente estos dos fallos; no necesita ampliarse.
