# T27 — Métricas operativas verificadas

**PASS técnico, 2026-11-09.** API Docker con LightGBM champion v4 en
`127.0.0.1:8080`, sin cambiar pesos, contrato REST ni Registry original.

Una ventana parcial de 8,781 segundos registró diez solicitudes: ocho 200 y
dos 422; p50 4,516 ms y p95 21,446 ms, con throughput observado 1,139 req/s.
Son solicitudes sintéticas de smoke, no una prueba de carga ni un SLA.
Los tiempos incluyen respuestas completas de `/health`, `/model-info` y
`/predict`. Una instancia aislada sin recibo produjo las respuestas 503
esperadas; luego se retiró y la API normal quedó saludable.

Contadores, rutas y latencias se exportaron desde logs JSON a
`reports/operational/t27/serving-windows.json` y `unavailable-windows.json`;
la comprobación está en `audit.json` (evidencia local excluida de Git).
No se registran entradas, headers, query, IP ni identificadores de viajes.

La aprobación fija ventanas de 60 segundos y hasta 10.000 solicitudes para
percentiles exactos. Al superar ese límite se conservan los contadores y
los percentiles quedan no disponibles. Las pruebas incluyen ese caso,
ventanas parciales, errores y privacidad. No se infiere disponibilidad
continua; un cierre abrupto puede perder la última ventana en memoria.

[Implementación, comandos y limitaciones](../../docs/t26-t28.md).
