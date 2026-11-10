# T32–T34 — Ciclo challenger local

Contrato aprobado: [propuesta de ejecución](t32-t34-execution-proposal.md).
La aprobación incluye periodos, descargas limitadas, recursos, reglas y gate;
las [tres excepciones Q2 2026](t34-quality-exceptions-proposal.md) se
aprobaron después de observar sus fallos exactos. No se ejecuta T35.

## Datos y contratos

| Partición nueva | Filas finales | Exclusiones por corte de etiqueta |
|---|---:|---:|
| Train, 2025 completo | 48.144.298 | 747 |
| Validation conocida, enero–marzo 2026 | 10.937.087 | 814 |
| Final nueva, abril–junio 2026 | 11.603.243 | 874 |

Las tres cohortes tienen auditoría completa contra features/contexto/target
originales y destinos de datos validados: **70.684.628 filas verificadas**.
Las 155.207 exclusiones de calidad de Q2 preceden a las 874 temporales.
Los splits y modelos anteriores no se sobrescriben. El corte anual restaura
1.644 viajes de 2025 elegibles que los cortes intermedios de T14 apartaban.

El nuevo ciclo es retrospectivo y no demuestra publicación histórica de TLC
ni despliegue real en esas fechas. El holdout Q1 2026 del champion ya fue
consumido: aquí se declara validation conocida. No se reajusta el candidato
con Q2 2026. Features: origen, calendario NY y pasajeros opcionales; destino
únicamente para segmentos. Mismas convenciones UTC/DST y D-04 congelada.

configs/retraining.yaml es independiente y referencia por hash las fuentes
T29/T31/T19. Cambiarlo no concede aprobación: la ejecución real exige el
perfil canónico aprobado. Las fixtures usan TEST_ONLY y no pueden convertirse
en lotes reales. No se cambian dependencias ni se utiliza el renderer de
Evidently para entrenar o predecir.

## Ejecución explícita

Los comandos requieren manifiestos, artefactos, catálogos locales e informes
de las tareas anteriores. Clonar Git no los descarga ni crea un champion.
Desde la raíz, con .venv-mlflow y MLflow nativo en 127.0.0.1:5000:

```powershell
.\.venv-mlflow\Scripts\python.exe -m src.retraining.triggers
.\.venv-mlflow\Scripts\python.exe -m src.retraining.downloads
.\.venv-mlflow\Scripts\python.exe -m src.retraining.cohorts --help
.\.venv-mlflow\Scripts\python.exe -m src.retraining.audit --help
.\.venv-mlflow\Scripts\python.exe -m src.retraining.train_challenger --help
.\.venv-mlflow\Scripts\python.exe -m src.retraining.evaluation --help
.\.venv-mlflow\Scripts\python.exe -m src.retraining.registration --help
.\.venv-mlflow\Scripts\python.exe -m src.retraining.compare --help
```

Orden: trigger → preparar/auditar train y validation → fit → evaluación
de desarrollo → registrar candidato sin alias → preparar/auditar final →
comparación final una vez → gate. Cada fase recibe entradas explícitas por
ruta/hash; sin recomendación no hay fit y sin auditoría no hay ejecución real.
Estos comandos no implementan el workflow automático de T36.

T32 produce recomendaciones desde seis reportes completos; no inicia
entrenamiento. T33 reutiliza parámetros LightGBM de T16, desde cero, sin
early stopping, búsqueda de parámetros ni warm start. Vocabulario y bins se
aprenden solo de train; las 200.000 filas de discretización no sustituyen
las 48.144.298 usadas para los árboles.

En evaluación, primero se generan predicciones con features iniciales;
después se unen etiquetas por identidad de feature/fila y posición global.
Contexto de destino no llega al predictor. Métricas exactas y cuantiles R7
en disco; tres meses, cuatro franjas y las 20 rutas T17 congeladas.

La reserva final está ligada al perfil/periodo completo: cambiar el archivo
de cohorte o el candidato no permite consumir el mismo holdout otra vez.
Los fallos quedan versionados. Un reintento de evaluación final requerirá
revisar lo ocurrido y autorizarlo antes de reutilizar la reserva.

## Recursos e integridad

Preparación 4 GiB libres/2 GiB RSS; fit 8/4; evaluación 6/2. En todos los casos,
50 GiB disco, cuatro hilos, un candidato y dos horas por modelo. El fit tiene
supervisión externa y límite combinado conservador de padre/worker de 4 GiB.
Las demás guardas son cooperativas; no se afirma un límite duro del SO.

El primer fit se canceló por el límite combinado; no publicó un modelo.
Se conservó su FAIL y se cambió la escritura de matrices del padre a bloques
secuenciales, evitando retener todo el memmap en su pico de memoria. Una
prueba compara bytes y hashes contra el escritor original; filas, bins,
parámetros, límites y semillas permanecen iguales. No se elevó el presupuesto.

La descarga Q2 reservó 192 MiB dentro de 1 GiB; contador persistente antes de
cada lectura, límite 512 MiB/archivo y sin devolver reservas tras un fallo.
Los archivos ya existentes se verifican y se omiten; no se descargan otros meses.

Se observó conversión CRLF del lock serving al sincronizar main en Windows.
Se restauraron sus bytes LF aprobados y .gitattributes evita repetirla; las
versiones y hashes de paquetes no cambiaron. Los 28 archivos originales del
snapshot vuelven a coincidir, incluidos pesos, evaluaciones y locks.

## Decisiones y salidas

T34 solo permite ELIGIBLE_FOR_HUMAN_REVIEW si MAE mejora >=2 %, RMSE/P90
globales no empeoran, MAE/P90 por segmento aumentan <=5 %, todos los segmentos
requeridos tienen al menos 1.000 filas y pasan calidad, integridad y smoke.
Fallo: CHALLENGER_REJECTED; evidencia insuficiente: NOT_EVALUABLE/BLOCKED.
No se elimina un segmento para conseguir PASS ni se habilita no inferioridad.

Reportes y recibos locales se escriben bajo reports/retraining, modelos en
models/retraining y cohortes en data/processed/retraining; permanecen excluidos
de Git. La configuración y los reportes Markdown son públicos. Los hashes
acreditan integridad local, no constituyen firma digital de identidad.

El registro crea una versión candidata trazable y verifica carga/predicciones
y alias antes/después. La API y la copia Docker conservan v4. Cualquier
promoción, recarga o rollback requiere T35 y aprobación explícita posterior.

Estado medido del trigger: [T32](../reports/retraining/t32_trigger.md).
Fit y registro v5: [T33](../reports/retraining/t33_challenger.md).
Comparación final y auditoría: [T34](../reports/retraining/t34_comparison.md).
T32–T34 tienen cierre técnico; gate CHALLENGER_REJECTED por mejora MAE
0,737317 % <2 %. Se registraron también métricas/decisión en MLflow mediante
scripts/log_retraining_gate.py, sin tocar aliases. V4 continúa como champion.
