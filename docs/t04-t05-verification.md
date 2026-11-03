# T04/T05 — Fixtures y perfilado técnico acotado

Fecha: 2026-11-03, America/Costa_Rica. Estado: implementación y verificaciones técnicas realizadas; revisión humana de T04/T05 y cierre G1 pendientes. El usuario solicitó avanzar desde T03 a T04/T05 y aprobó perfilar únicamente 2024 con las primeras 2.048 filas por row group. No aprobó periodos finales, presupuesto de entrenamiento ni umbrales DQ.

## T04: por qué siguen siendo necesarias las fixtures

Los archivos reales sirven para conocer características y problemas observados. Las fixtures controlan qué anomalía existe y su cantidad exacta, se ejecutan offline y no requieren subir datos TLC a Git/CI. Se conservaron conforme a spec/plan, sin mezclar datos sintéticos con EDA real ni entrenamiento.

Archivos: [factoría](../tests/fixtures/factory.py), [contrato y casos](../tests/fixtures/README.md), [pruebas de fixtures](../tests/unit/test_fixtures.py). Se generaron diez Parquet de 12 filas cada uno, semilla 42, con 103.906 bytes en total. La metadata identifica origen sintético, caso y semilla. El contrato histórico reproduce 19 columnas observadas; no es una whitelist de inferencia ni el contrato productivo T08.

Casos controlados: válido, origen nulo, llegada nula, duración cero/negativa, recogida fuera de mes, duplicado exacto, pasajeros negativos, columna ausente, tipo incompatible y columna adicional. La regeneración determinista se compara por hashes; se rechaza sobrescribir archivos sin marcador sintético.

## T05: alcance y evidencia

Archivos: [script reproducible](../scripts/profile_sample.py), [notas del reporte](../scripts/eda_notes.md), [informe EDA](../reports/eda_schema.md) y [pruebas del perfilador](../tests/unit/test_profile_sample.py).

Se seleccionaron las primeras 2.048 filas de cada uno de los 44 row groups de los doce meses de 2024: 90.112 filas de 41.169.720 declaradas en sus footers. La muestra es determinista, posicional y sesgada; las métricas no estiman tasas anuales. Las filas de 2025 no fueron perfiladas. El cambio de esquema 2024/2025 se contrasta con los metadatos ya obtenidos en T03.

La salida detallada `reports/eda_schema.json` es local y está excluida de Git: contiene conteos, estadísticas, esquemas, hashes y rangos seleccionados, sin volcar las filas completas. Los hashes SHA-256 requieren leer los bytes comprimidos de cada fuente 2024 por bloques; la decodificación de filas permanece acotada a la muestra. El Markdown resume la evidencia y las propuestas para revisión.

Observaciones de la muestra:

- 35 duraciones no positivas y 155 recogidas fuera del mes nominal.
- 4.096 pasajeros nulos, concentrados en los segmentos seleccionados de abril/junio; no deben extrapolarse a todo el año.
- Duraciones positivas máximas cercanas a 24 horas; no se eliminan ni se declara un máximo aceptable por esta observación.
- Sin nulos de zonas/timestamps ni duplicados exactos en las filas seleccionadas; no prueba ausencia en los archivos completos.
- Sin validación de pertenencia al catálogo de zonas, todavía pendiente; códigos especiales no se clasifican automáticamente como inválidos.
- `Airport_fee` en archivos frente a `airport_fee` en el diccionario: normalización pendiente de T08. Timestamps `us` sin zona declarada: interpretación histórica/DST pendiente de D-06.

Recursos observados durante la primera ejecución: 12 CPU lógicas, 33.970.917.376 bytes de RAM total, pico RSS de 129.622.016 bytes (123,62 MiB), pico Arrow de 31.951.680 bytes y Python/tracemalloc de 9.462.440 bytes; tiempo 6,59 s incluyendo hashes. Son métricas de esta muestra y máquina. No se suman los distintos asignadores ni se extrapolan a entrenamiento; límites Docker no medidos y D-02 sigue parcial.

El perfilado se repitió y coincidieron los perfiles, rangos, esquemas y hashes de muestra/fuente de los doce meses, comparando representaciones JSON normalizadas. Tiempo/memoria/fecha operacional no se comparan como valores deterministas.

## Verificaciones ejecutadas

```powershell
.\.venv\Scripts\python.exe -m tests.fixtures.factory --seed 42 --output-dir tests/fixtures
.\.venv\Scripts\python.exe -m scripts.profile_sample --rows-per-group 2048
.\.venv\Scripts\python.exe -m pytest -q --basetemp=.cache/pytest-t04-t05-verified -o cache_dir=.cache/pytest-cache-t04-t05-verified
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
```

Resultado observado: **32 pruebas aprobadas**, Ruff sin errores, 18 archivos Python/TOML con formato correcto y dependencias sin conflictos. Las pruebas cubren anomalías, lecturas Parquet, determinismo, preservación de archivos ajenos, cuantiles conocidos, lectura acotada por grupo, fuentes sin modificar, ausencia de lectura de 2025 y rechazo de reportes dentro de raw. Todas usan datos sintéticos; no dependen de los Parquet reales ni de Internet.

Además se copiaron únicamente `tests`, `scripts` y pyproject a un checkout temporal bajo `.cache`, sin carpeta `data`, y se ejecutaron las 32 pruebas con el entorno de verificación de T03: **32 aprobadas**. Esta comprobación demuestra independencia de raw y usa dependencias ya instaladas; no es un workflow GitHub ejecutado. La primera prueba de esa copia encontró que faltaba el padre `.cache` del temporal configurado. Se añadió [tests/conftest.py](../tests/conftest.py), que prepara ese padre únicamente dentro del `.cache` del checkout, y la repetición pasó. No crea ni borra carpetas raw.

Incidentes corregidos: Ruff detectó líneas largas y se aplicó formato/split de texto; una aserción de cuantiles usaba igualdad exacta de floats y se corrigió a tolerancia numérica; la primera comparación de repetibilidad mezcló listas JSON y tuplas en memoria, y se normalizó a JSON antes de comparar. No se alteraron cálculos ni datos para forzar resultados y no se declaran exitosos esos intentos iniciales fallidos.

## Pendientes y límites

D-01: periodos y rol de 2024/2025/2026 siguen pendientes. D-02: host medido y lectura acotada probada, presupuesto de entrenamiento/Docker pendiente. D-04: frontera estructural y validez de etiqueta propuestas; tolerancias de lote, máximo de duración y volumen requieren aprobación y más evidencia representativa. D-06 y el resto de decisiones no se cierran por este perfilado.

No se implementaron validadores productivos, ingesta, modelos ni API; no se generaron datos validated/processed. Raw se conserva, no se instalaron dependencias nuevas ni se hicieron commits/remotos/publicación. G0 permanece abierto y la evidencia técnica G1 se presenta para revisión humana antes del siguiente sprint.

Auditoría final: SHA-256 de los 24 Parquet reales coincide con el registrado antes de organizarlos en T03; diez fixtures sintéticas (103.906 bytes) permitidas por Git, y raw/JSON de EDA/cachés excluidos. Se comprobaron 14 Markdown y 77 enlaces locales; PDF original intacto. Git sigue en `main`, con índice vacío y cero commits/remotos. Los 59 archivos públicos no rastreados incluyen documentación, código y fixtures sintéticas; los archivos reales no aparecen en ese listado.
