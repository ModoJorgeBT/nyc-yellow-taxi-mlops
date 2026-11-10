# T33 — Challenger LightGBM registrado

**PASS técnico, 2026-11-09.** Nuevo modelo entrenado desde cero y registrado
como candidato **versión 5**, sin alias. El champion sigue siendo **v4**.

| Comprobación | Resultado observado |
|---|---|
| Train | 48.144.298 viajes elegibles de todo 2025; 747 exclusiones por corte de etiqueta |
| Configuración | LightGBM 4.7.0, 100 árboles, mismas features/parámetros/semilla 42 que T16 |
| Discretización | 200.000 filas de train solo para bins; todos los viajes participan en los árboles |
| Duración del fit | 187,88 segundos |
| Pico RSS nativo | 2.663,41 MiB |
| Pico RSS combinado conservador | 3.636,54 MiB, inferior al límite de 4 GiB |
| Smoke | Pipeline serializado y reload MLflow con predicciones coincidentes |
| Alias antes/después | champion=4; candidato sin alias y serving_approved=false |

El primer intento quedó FAIL por el límite combinado de memoria. No publicó
un modelo. La escritura posterior por bloques produjo los mismos bytes y
hashes que el escritor anterior en la prueba de equivalencia; se conservaron
límites, datos y parámetros. El intento fallido permanece en
models/retraining/50f51b230abe41e2b9066dfac209d257/training_manifest.json.

Evaluación de desarrollo sobre las mismas 10.937.087 filas de enero–marzo
2026, declaradas conocidas tras la evaluación del champion anterior:

| Modelo | MAE min | RMSE min | MedAE min | P90 min |
|---|---:|---:|---:|---:|
| Champion v4 | 7,742891 | 12,368333 | 5,048365 | 16,815384 |
| Challenger v5 | 7,705447 | 12,282985 | 4,970043 | 16,949764 |

La mejora de MAE es pequeña y P90 empeora en validation. No se ajustaron
parámetros después de observarlo ni se presenta este periodo como nueva
prueba independiente. T34 compara ambos congelados sobre abril–junio 2026.

MLflow: nyc-yellow-taxi-duration, versión 5, run
946d8896e0dd45ea9ab991de74204539. SHA-256 de pesos:
1e1f122a3904e96304092806fc7c1d0821152efd54775c73c9ff933cfee75d4b.
Registro y smoke: reports/retraining/registrations/
4736d216a31828746718e519a43594ee50fa60fc5c12a809b77b7aefb3bc3adf.json.

Código ejecutado: 63 fuentes coinciden con wheel archivado SHA-256
8fb524cf060e0eb5eedb8d5aa126d366dba8239604624c2ab5c201bd555982c2.
Se registra el commit base 21a6abf y git_dirty=true: los nuevos cambios son
locales y el hash del árbol/paquete identifica el código real, sin fingir que
ya está publicado. Versiones/hashes de dependencias intactos.

Las tres cohortes tienen auditoría exhaustiva de valores, identidades,
cobertura y cortes. Vocabulario/bins train-only, destino solo como segmento,
sin lecturas de validation/final durante el ajuste. Los artefactos originales
no se sobrescribieron. La copia Docker y serving permanecen en v4.
[Contrato, comandos y límites](../../docs/t32-t34-retraining.md).
