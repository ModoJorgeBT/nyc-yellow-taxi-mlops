# ADR 0002 — Operación reversible y evidencia por alcance

Estado: aprobado para T35–T38; promoción real futura requiere aprobación propia.

T34 rechazó v5. Hace falta demostrar promoción/rollback sin alterar champion
v4 ni rebajar el gate. Se adopta contrato operativo v2 separado de T19/v1,
diario encadenado, snapshots de aprobación/alias, API gestionada por identidad
y compensación ante fallos. El loader conserva v1. Bloqueo local y controles
de concurrencia no constituyen una transacción distribuida.

La demostración positiva usa modelos sintéticos, namespace/raíz/puertos
aislados y marca TEST_ONLY. Workflow no promueve automáticamente. Reproducción
automática offline usa export del árbol de trabajo sin datos/modelos/secretos,
no clon del main remoto. Revisión por otro integrante y defensa oral permanecen
NO VERIFICADAS. Consecuencia: el cierre técnico puede acreditarse sin fingir
aprobación de v5, actividad humana o publicación Git.

[Aprobación](../t35-t38-execution-proposal.md), [runbook](../runbook.md),
[evidencia y limitaciones](../../reports/final/completion.md).
