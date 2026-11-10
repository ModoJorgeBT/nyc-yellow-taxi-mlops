# T29–T31 — Monitoreo mensual local verificado

**Cierre técnico PASS, 2026-11-09.** [Resultados completos y CI](../reports/monitoring/t29-t31_monthly_replay.md).
El usuario aprobó el protocolo, las dependencias, el aislamiento de pandas,
la recuperación de descargas y ampliar el PR #1 conservando main/historial.

## Entornos y arranque

Python 3.14.7. `.venv-mlflow` conserva el runtime del champion y pandas 3.1.1.
`.venv-monitoring` utiliza Evidently 0.7.23 y pandas 2.3.3 solo para rendering.
La incompatibilidad y su [revisión aprobada](t29-evidently-compatibility-review.md)
quedan registradas. No ejecutar predicciones reales en el entorno de reportes.

```powershell
# Solo al preparar un entorno nuevo; los existentes ya están instalados.
python -m venv .venv-monitoring
.\.venv-monitoring\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements-monitoring.lock
```

Windows y Linux tienen locks separados. Los artefactos compartidos de serving
se conservan; solo el renderer tiene la excepción pandas 2.3.3. CI comprueba
el runtime original y el renderer en contenedores separados y secuenciales.
No repetir la generación masiva de hashes; ver [incidente y recuperación](t29-dependency-download-incident.md).

El perfil `configs/monitoring.yaml` identifica split T14, modelo/aprobación
T19, evaluación de validation, reglas T28, locks y referencia por hash. Está
ligado a los artefactos locales auditados; clonar Git no descarga modelos,
datos, recibos ni referencias generadas. Se necesita el bootstrap de las
tareas anteriores y evidencia compatible, no una aceptación automática.

## CLI y salidas

Desde la raíz, con MLflow nativo disponible en 127.0.0.1:5000:

```powershell
.\.venv-mlflow\Scripts\python.exe -m src.monitoring.run --year 2025 --month 7
.\.venv-mlflow\Scripts\python.exe -m src.monitoring.run --year 2025 --month 7 --without-labels
```

Cada ejecución crea `reports/monitoring/monthly/2025/MM/<uuid>/` con
`monitoring.json`, `drift.json`, Evidently JSON/HTML, predicciones y evidencia
del renderer. Una repetición crea otra versión. Los FAIL se conservan y el
CLI retorna código 1; no se sobrescriben ejecuciones previas.

La referencia completa se construye por separado con `--build-reference
<nueva-ruta.json>`. El perfil debe identificar explícitamente su ruta/hash
sellados antes de consumirla; rehashear una referencia alterada no la aprueba.
El perfil actual ya está sellado: no reconstruir ni sustituir sus archivos.

Modelo y runtime se verifican antes/después, incluyendo el smoke congelado
T19. El renderer recibe únicamente bins JSON; se identifica y supervisa antes
de importar pandas/Evidently, con RSS combinado <=2 GiB. El coordinador aplica
guardas entre bloques; no se afirma un límite duro del SO en Windows.
Presupuesto: 4 GiB libres/2 GiB RSS, 50 GiB disco, cuatro hilos, un mes a la
vez y dos horas; CI tiene su perfil independiente 2 CPU/4 GiB/10 GiB/20 min.

## Semántica y límites

- Referencia train 2024 frente al mismo mes del replay julio–diciembre 2025;
  seis features discretas, conteos completos, PSI >0,20, alpha=0,5 y mínimo
  1.000 filas. No se aplican defaults de drift de Evidently ni se muestrea.
- Identidad de split/feature/fila para unir predicciones y etiquetas; ventanas
  por recogida NY y corte fin de mes UTC +24 h. Es replay de eventos, sin
  acreditar disponibilidad histórica de los archivos TLC.
- Sin etiquetas, métricas NOT_AVAILABLE; con etiquetas maduras, MAE/RMSE y
  cuantiles R7 exactos en disco. Rutas T17 congeladas y bandas de seis horas;
  destino solo para segmentación.
- Servicio histórico 2025 NOT_AVAILABLE. T27 documenta observaciones actuales
  reales de la API; no se trasladan sus latencias a meses pasados.
- D-04, sus FAIL y excepciones no cambian. ALERT_REVIEW_REQUIRED es una señal
  para revisión. Triggers T32, 115 %/dos ventanas y promociones futuras siguen
  pendientes de aprobación; no se reentrena ni modifica champion.

Auditor independiente: `scripts/audit_monitoring.py`, con catálogo de reportes
por ruta/hash y salida nueva. Recalcula toda la población y valida los cuantiles
mediante CDF completa, sin ordenar la partición en memoria. La auditoría real
cubrió 24.266.924 filas y mantuvo modelos/evaluaciones originales.

G5 cumple técnicamente CI, calidad, drift, desempeño condicionado a etiquetas
y observaciones de servicio. Revisión humana del PR y T32–T38 independientes.
