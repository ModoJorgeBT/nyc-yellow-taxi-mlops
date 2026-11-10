# T29–T31 — Replay mensual completo

**Datos y auditoría PASS, 2026-11-09.** Champion LightGBM v4 congelado;
24.266.924 viajes elegibles de julio–diciembre 2025, sin submuestreo.
CI del nuevo renderer está en corrección tras detectar un WORKDIR incorrecto;
el cierre de G5 requiere observar su ejecución verde.

| Cohorte | Filas evaluadas | MAE min | RMSE min | MedAE min | P90 min | Features con PSI >0,20 |
|---|---:|---:|---:|---:|---:|---|
| 2025-07 | 3,841,674 | 7.369577 | 11.160331 | 5.092338 | 15.866329 | passenger_count, passenger_count_missing |
| 2025-08 | 3,524,959 | 7.356742 | 11.260358 | 5.033043 | 15.744723 | passenger_count_missing |
| 2025-09 | 4,192,264 | 8.126385 | 12.357400 | 5.515144 | 17.756834 | ninguna |
| 2025-10 | 4,359,033 | 8.207974 | 12.687376 | 5.471875 | 17.963672 | ninguna |
| 2025-11 | 4,104,925 | 8.099161 | 12.527308 | 5.445878 | 17.566825 | ninguna |
| 2025-12 | 4,244,069 | 8.614525 | 13.275330 | 5.756477 | 18.872561 | passenger_count, passenger_count_missing |

Referencia: las 41.119.495 filas completas de train 2024, distribuciones por
mes y comparación con el mismo mes de 2025. Conteos completos, seis features
discretas, alpha=0,5 y mínimo 1.000 viajes. Evidently genera JSON/HTML sobre
bins reales; sus valores se verificaron contra el PSI recalculado.
Los indicadores de pasajeros y ausencia están relacionados; sus alertas
no prueban una causa del error ni activan reentrenamiento.

La auditoría independiente volvió a calcular todas las predicciones,
MAE/RMSE y cuantiles mediante la CDF completa, sin ordenar la partición en
memoria. Verificó identidades, features, etiquetas maduras, cobertura de
24.266.924 filas y agregación de segmentos. Mantiene las 20 rutas congeladas
por validation y franjas de seis horas; destino nunca es predictor.

Predicciones y etiquetas se procesaron separadamente, con corte mensual
de Nueva York y maduración de 24 h UTC. Todas las etiquetas elegibles están
disponibles bajo esa convención. No acredita la publicación histórica del
archivo TLC. Sin etiquetas, las pruebas verifican NOT_AVAILABLE y métricas
nulas. No se reabrieron test 2025 ni holdout 2026 para calcular métricas.

Los seis reportes mantienen FAIL y excepciones D-04 exactas, exclusiones,
hashes y aceptación original. Las decisiones preliminares son alertas para
revisión; no cambian el champion ni implementan triggers T32. La comparación
con MAE de validation es descriptiva; el 115 % continúa pendiente.

Servicio histórico 2025: NOT_AVAILABLE, sin atribuir a ese periodo las
ventanas actuales de la API. Las métricas operativas reales corresponden a
[T27](t27_service_metrics.md), sin afirmación de disponibilidad continua.

Recursos observados: máximo RSS del coordinador **853.27 MiB** y máximo
combinado coordinador/renderer durante rendering **535.34 MiB**;
ambos bajo 2 GiB. Preflight 4 GiB RAM/50 GiB disco, cuatro hilos, meses
secuenciales y menos de dos horas por ejecución. Guardas cooperativas en
el coordinador y supervisor externo del renderer, no un límite duro del SO
para todo el proceso local. CI mantiene su perfil independiente aprobado.

Evidently 0.7.23 falló con pandas 3.1.1. El aislamiento aprobado conserva
ese pandas en el runtime original y utiliza pandas 2.3.3 solo para reportes,
con bins JSON entre procesos y supervisión antes de importar librerías.
No se parcheó ninguna dependencia. Locks Windows/Linux separados.

El primer intento de generar hashes excedió su presupuesto y permanece
FAIL. La recuperación adicional aprobada transfirió **169.37 MiB**,
contabilizados frente al límite de 256 MiB; no borra el incidente original.
[Incidente](../../docs/t29-dependency-download-incident.md) y
[compatibilidad](../../docs/t29-evidently-compatibility-review.md).

Evidencia local excluida de Git: referencia en reports/monitoring/reference/;
seis carpetas versionadas bajo reports/monitoring/monthly/2025/MM/;
catálogo y auditoría en .cache/t29-t31/month-catalog.json y full-replay-audit.json.
Auditor reproducible: `python scripts/audit_monitoring.py --catalog <catalogo> --output <nuevo-audit.json>`.
Los datos/modelos y el PDF nuevo del equipo permanecen locales.
