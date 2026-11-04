# D-04 — Activación provisional y piloto enero 2024

Fecha: 2026-11-03. **APROBADA E IMPLEMENTADA**, versión `d04-real-v1-2026-11-03`. El usuario respondió «Sí, aprobar e implementar la política provisional» y, separadamente, «Sí, autorizar únicamente enero de 2024 como piloto». Esta fue la autorización del piloto inicial. Posteriormente el usuario ratificó/congeló v1 y amplió uso académico a los 24 hashes actuales, sin ejecutar su incorporación; [protocolo y aprobaciones actuales](d01-d02-protocol.md). No autoriza entrenamiento, T14 ni cierre humano automático de G2.

## Política aplicada

[Justificación y tablas completas](d04-quality-proposal.md), [registro estructurado](d04-policy-proposal.json) y [configuración ejecutable](../configs/data.yaml). Duración UTC estrictamente positiva y hasta 180 minutos; históricos America/New_York con cuarentena DST; origen del catálogo aprobado, conservando 264/265. Pasajeros fuera de 0–6 pasan a null, sin eliminar el viaje. Destino/categorías opcionales son informativos; no son predictores. Los duplicados se cuentan sobre todas las columnas originales antes de normalizar y se conservan.

Rechazo si la unión de filas inválidas supera 1 %, alerta global si supera 0,50 %, además de límites específicos aprobados. Las comparaciones de tasa son estrictas (>), con denominador raw completo. Cualquier exclusión tolerada queda visible como WARN por regla aunque no active la alerta global; un null de categoría opcional y la procedencia local también generan WARN. Mínimos mensuales: 1.000.000 raw y 990.000 elegibles; banda informativa de volumen 0,5–2 veces el footer del mismo mes de 2024. El mínimo de lote no define un tamaño de entrenamiento.

El catálogo incluye 265 IDs, versionado por lista/hash y por el SHA del CSV original. Su snapshot de 2026-11-03 se acepta como referencia operativa; no demuestra vigencia histórica independiente. El rango de pasajeros es una convención de tratamiento de históricos, no un límite legal. El contrato REST completo, incluido cómo validar/normalizar valores fuera de rango al servir, sigue pendiente de T20/D-06; no hay API desplegada.

## Implementación y garantías

- [Motor real](../src/validation/real.py): duración compartida con T12, contadores por motivo y unión sin doble conteo; cache temporal acotada e índice SQLite exacto en disco, sin cargar el mes completo.
- [Orquestador](../src/validation/run.py): autorización de mes/hash, manifiesto y contenido verificados antes/después, exhaustividad contra footer y publicación sin reemplazo. Parquet por bloques y `validation.json` publicado al final; un Parquet aislado no es un lote completo.
- [Lector de features](../src/features/artifacts.py): acepta REAL solo con calidad aprobada, hashes/configuración/tiempo/autorización consistentes; rechaza nuevas exclusiones incompatibles con el perfil real. TEST_ONLY conserva aislamiento. Este soporte se probó con fixtures; no se extrajeron features del piloto.

El evaluador aislado nunca concede aprobación de datos ni entrenamiento. Tras validar linaje y completar publicación, T10 marca `data_quality_approved=true`; **`approved_for_training=false`** permanece en reportes y artefactos. D-01 debe fijar ventanas y disponibilidad de etiquetas/publicación; D-02, presupuesto de modelado. No se hizo fit, split ni selección de modelo.

## Ejecución real autorizada

Registro explícito de `data/raw/2024/01/yellow_tripdata_2024-01.parquet`, SHA `c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510`. LOCAL_UNVERIFIED no se transforma en DOWNLOADED: fuente y fecha de descarga siguen nulas. La configuración del piloto autorizaba ese contenido exacto y mes. La configuración actual autoriza uso académico de los 24 hashes; los otros 23 siguen sin incorporación. Conservación comprobada de tamaño y SHA de los 24 originales, leyendo únicamente bytes comprimidos de 2025.

Piloto `eb3c22ba4da94a2fb647fa4ffe1c6a0f`, entre `2026-11-03T21:24:29.348278+00:00` y `2026-11-03T21:25:58.340235+00:00`. Resultado **WARN / VALIDATED_REAL**, calidad aprobada: **2.964.624 raw → 2.961.753 elegibles**, 2.871 exclusiones (0,096842 %), 60 pasajeros normalizados, cero duplicados exactos observados. [Reporte de conteos, límites, recursos y rutas](../reports/quality/pilot_2024_01.md).

Tiempo total 89.02 s; pico RSS 256.26 MiB; índice temporal exacto 1.480 GiB, eliminado al terminar. Son observaciones de este host/mes y no un presupuesto de Docker o entrenamiento. No se extrapolan los resultados a otros meses, especialmente a las transiciones DST.

Comandos ejecutados (desde la raíz, con dependencias ya instaladas):

```powershell
.\.venv\Scripts\python.exe -m src.ingestion.download --year 2024 --month 1 --register-local --expected-sha256 c4d59da7bbc8abaeeeb1727947ee93d9891a71acb42854bd80db1571b2030510
```

El piloto invocó `src.validation.run.validate(2024, 1)` con configuración/rutas predeterminadas, medición de tiempo/RSS y logging por bloque desde `.cache/d04/run_pilot.py`. Su equivalente CLI es:

```powershell
.\.venv\Scripts\python.exe -m src.validation.run --year 2024 --month 1 --batch-size 65536
```

Repetir la validación genera un intento nuevo, no reemplaza el resultado. La autorización inicial solo cubrió enero. La ampliación posterior permite preparar incorporación de otros meses, sin ejecutarla en esta revisión documental. JSON completos locales: `.cache/d04/pilot-result.json`, `.cache/d04/pilot-audit.json` y reporte/marcador indicados en el informe Markdown; datos/JSON de ejecución excluidos de Git.

## Verificación y límites

**255 pruebas aprobadas** en desarrollo y **255** desde wheel instalado en `.venv-verify`, ejecutadas en `.cache/d04-checkout` sin src ni data. Importación aislada de 17 módulos y CLI incluidos; las pruebas reales usan fixtures y tolerancias miniatura explícitas, sin rebajar el perfil productivo. Las 18 pruebas nuevas cubren DST/UTC, límites, unión, duplicados entre bloques, normalización, política incompleta, autorización, mínimos reales y publicación/consumo REAL sin entrenamiento. Ruff y `pip check` verificados sin errores.

Auditoría posterior: hash/marker/metadata/footer de la salida consistentes; sus 2.961.753 valores de pasajeros están en 0–6 o null. Se conservaron 31.395 ceros informados y 140.108 nulls en elegibles. Solo enero tiene manifiesto raw; temporales SQLite, staging y locks limpiados. No existen features reales nuevos. Ningún original se movió ni cambió de bytes; no se decodificaron filas de 2025 ni se añadieron dependencias. Cambios locales sin nuevo commit/push.

La aprobación provisional no prueba que los umbrales sean óptimos. T17 debe mostrar cobertura/exclusiones y segmentos (ausencia de pasajeros, zonas especiales), y comprobar desempeño sin ajustar estos controles sobre test. D-01/D-02 y el uso académico de los otros 23 archivos actuales se aprobaron posteriormente en el [protocolo](d01-d02-protocol.md). Nuevos archivos fuera de esos hashes requieren aprobación. El siguiente trabajo requiere autorizar su tarea e implementar/probar controles antes de entrenar; no se validan otros lotes en esta revisión.

## Actualización posterior de preparación T14/T15

15 meses registrados LOCAL_UNVERIFIED; 14 completaron calidad/features REAL (2024 completo y enero–febrero de 2025). Marzo de 2025 rechazado: 22.280 duraciones no positivas/4.145.257 filas (0,537482 %), máximo 0,50 %. El usuario decidió mantener D-04. No hay particiones reales ni baseline real publicados. [Reporte actual](../reports/quality/t14_t15_preparation.md), [decisión de mantener D-04](t14-t15-quality-blocker.md). Las cifras y afirmaciones de solo enero incorporado/sin lectura 2025 de las secciones anteriores describen exclusivamente el piloto inicial; no el estado actual. La consulta oficial posterior no modifica la fuente/fecha históricas nulas de los manifiestos.

## Excepción de marzo y evaluación T15 posteriores

T15 verificada técnicamente: mediana congelada 12,983333 min de 41.119.495 etiquetas train 2024; 11.163.264 predicciones enero–marzo 2025. MAE 7,741890 min y RMSE 11,912962 min. [Reporte](../reports/quality/t15_baseline_validation.md). Marzo aceptado por excepción humana solo para su hash/reporte; FAIL original y exclusiones conservados, sin cambiar D-04 global. T14 integral sigue pendiente; test/replay sellados, T16 no ejecutada y sin registro/promoción. [Contrato y autorización](t15-march-exception.md). Las referencias anteriores a bloqueo de evaluación o ausencia de excepción son históricas.
