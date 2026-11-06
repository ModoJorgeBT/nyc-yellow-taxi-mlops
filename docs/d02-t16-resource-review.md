# D-02 — Revisión concreta de recursos para T16/T17

Fecha: 2026-11-05, America/Costa_Rica. **APROBADA LA ALTERNATIVA 8/4.** Respuesta del usuario: «Sí, aprobar el perfil incremental 8 GiB libres/4 GiB RSS». T14 terminó su auditoría; el primer preflight 12/8 de T16 falló antes de ajustar preprocesadores o entrenar modelos reales. El perfil revisado queda registrado en configs/candidates.yaml; configs/model.yaml conserva el contrato histórico de T14.

Medición: **11.262.042.112 bytes disponibles (10,49 GiB)** frente al mínimo vigente **12 GiB**. Disco: más de 315 GiB libres. El perfil vigente conserva máximo RSS 8 GiB, cuatro hilos, un candidato y dos horas por candidato. Reiniciar el uso de Codex no cambia esta condición física.

## Alternativas

1. Mantener el perfil 12 GiB libres/8 GiB RSS y liberar memoria hasta superar su preflight. No se cerrarán procesos ajenos automáticamente.
2. Aprobar para el entrenamiento/evaluación incremental T16/T17 un perfil de **8 GiB RAM libre y máximo RSS 4 GiB**, manteniendo cuatro hilos, un candidato, 50 GiB disco y dos horas por candidato, incluidos los costes compartidos de preprocesamiento. Se detendrá si incumple límites; no se muestrean datos ni se amplían recursos automáticamente.

Se recomienda la segunda alternativa para esta arquitectura concreta: seis columnas base, vocabulario de origen de como máximo 265 zonas, hasta 270 columnas codificadas y bloques de 4.096. Una matriz densa float32 por bloque ocupa como máximo **4.423.680 bytes (4,22 MiB)**; la MLP16 tiene aproximadamente 4.353 parámetros. Eso evita la matriz densa de todo el histórico. Habrá buffers, lectores y librerías adicionales; este cálculo no sustituye la supervisión RSS ni demuestra por sí solo el consumo total real.

El perfil 8/4 conserva un margen de cuatro GiB entre memoria mínima libre y máximo RSS permitido, igual que 12/8. Antes de entrenar se probarán límites/interrupción con fixtures y se verificará nuevamente el preflight. Si una ejecución real supera 4 GiB, se detendrá para revisión; no se aceptará silenciosamente ni reducirá el número de registros.

## Alcance de una aprobación

- Cambia únicamente el perfil de recursos de los candidatos/evaluación incremental. Mantiene todos los registros elegibles, parámetros y protocolo T17 ya aprobados.
- Preparación T14/T15 conserva su perfil histórico 4/2. El contrato de particiones en configs/model.yaml y su hash se mantienen congelados; el nuevo perfil se registrará por separado en la configuración T16/T17, con esta decisión y su aprobación.
- No modifica D-04, autorizaciones de lotes, cortes, target, features, límites de predicción ni dependencias. No permite iniciar T18, registro o promoción.

La aprobación permite continuar después de implementar/probar controles y verificar el preflight 8/4. Los parámetros de modelos y evaluación previamente aprobados se conservan; no implica que el fit real ya haya ocurrido.
