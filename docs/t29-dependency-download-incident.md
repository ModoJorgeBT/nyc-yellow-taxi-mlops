# T29 — Incidente de presupuesto al generar hashes

Fecha: 2026-11-09. Estado del primer intento: FAIL / ABORTADO.

La resolución se lanzó con pip-tools y `--generate-hashes` sobre el conjunto
de serving más Evidently. Ese método descargó artefactos de múltiples
plataformas para calcular hashes. Fue una elección incorrecta para el límite
de 1 GiB aprobado. La auditoría posterior contó 6.757.848.835 bytes de cuerpos
HTTP en la caché nueva; el tráfico de red exacto no estaba instrumentado y
no se puede acreditar el cumplimiento del límite original.

Se verificó y detuvo el proceso propio del compilador. No terminó el lock,
no instaló paquetes ni cambió los locks históricos, modelos o Registry.
La caché y el recibo `.cache/t29-t31/cache-audit.json` conservan evidencia.

Recuperación propuesta: reutilizar wheels compatibles ya existentes y
obtener hashes/tamaños desde metadatos oficiales PyPI, sin volver a calcular
hashes descargando todas las plataformas. Cualquier archivo faltante se
descargará individualmente con contador persistente de bytes y bloqueo
previo por Content-Length/tamaño esperado, hash obligatorio y límite total.
El usuario aprobó expresamente la recuperación con caché y un máximo
adicional de 256 MiB para wheels exactos faltantes, con contador persistente
y bloqueo estricto. El intento original permanece FAIL y no se
presentará como si hubiese respetado 1 GiB.

Recuperación completada: el contador persistente registró **177.600.252 bytes
(169,37 MiB)** adicionales, dentro de los 256 MiB autorizados, incluyendo
metadatos. Se fijaron 141 paquetes por plataforma en locks propios Windows y
Linux. El renderer usa la excepción pandas 2.3.3 aprobada por separado; las
dependencias del modelo no cambiaron. Importación, reportes reales y CI
separado pasaron. El exceso inicial conserva su estado FAIL/ABORTADO y su
evidencia; el resultado de la recuperación no lo elimina.
