# T14/T15: preparación real y bloqueo de calidad

Fecha: 2026-11-03, America/Costa_Rica. **NO CERRADAS: ejecución real detenida por D-04 en marzo de 2025.** [Decisión vigente y contraste de fuente](../../docs/t14-t15-quality-blocker.md). No se modificaron tolerancias, periodos ni originales.

## Meses completos

| Mes | Raw | Elegibles DQ y features REAL | Excluidas DQ | Estado |
|---|---:|---:|---:|---|
| 2024-01 | 2,964,624 | 2,961,753 | 2,871 | WARN |
| 2024-02 | 3,007,526 | 3,004,760 | 2,766 | WARN |
| 2024-03 | 3,582,628 | 3,579,306 | 3,322 | WARN |
| 2024-04 | 3,514,289 | 3,510,931 | 3,358 | WARN |
| 2024-05 | 3,723,833 | 3,720,354 | 3,479 | WARN |
| 2024-06 | 3,539,193 | 3,535,780 | 3,413 | WARN |
| 2024-07 | 3,076,903 | 3,073,739 | 3,164 | WARN |
| 2024-08 | 2,979,183 | 2,976,025 | 3,158 | WARN |
| 2024-09 | 3,633,030 | 3,629,857 | 3,173 | WARN |
| 2024-10 | 3,833,771 | 3,830,685 | 3,086 | WARN |
| 2024-11 | 3,646,369 | 3,631,916 | 14,453 | WARN |
| 2024-12 | 3,668,371 | 3,664,950 | 3,421 | WARN |
| 2025-01 | 3,475,226 | 3,471,776 | 3,450 | WARN |
| 2025-02 | 3,577,543 | 3,571,047 | 6,496 | WARN |

Totales de los 14 meses completos: **48,222,489 raw** y **48,162,879 elegibles**. Estos conteos preceden al corte de etiquetas de T14; no son todavía filas de particiones publicadas.

## Rechazo de marzo de 2025

Escaneo completo: 4.145.257 filas. Único FAIL: duración no positiva, 22.280 filas (0,537482 %) frente al máximo de 0,50 %. Diagnóstico independiente: 22.199 duraciones cero, 81 negativas, 21.481 de los casos con VendorID=7. No se filtró ese proveedor ni se modificó la causalidad de las features.

La unión de exclusiones suma 23.886 (0,576225 %). Las 4.121.371 potencialmente elegibles **no se publicaron**: el gate de lote sigue rechazado. El archivo conserva sus bytes y su manifiesto LOCAL_UNVERIFIED. No se ejecutaron los nueve meses restantes; no se sustituyó marzo ni se redujo el intervalo de validación.

Reporte local FAIL: `reports/quality/2025/03/077a819319564b4eb4913a4e389da48a.json`; SHA-256 `90586cd9bd750d0e1894e899d6871376bd924af29069f05c2bb5b952e175b261`. Diagnóstico por bloques: `.cache/t15/march-diagnosis.json`.

## Integridad y pruebas

Auditoría posterior al rechazo: hashes y tamaños de los 24 raw intactos; 15 manifiestos locales; 14 versiones completas de features/validated verificadas contra sus marcadores, hashes, conteos y reglas congeladas. PDF académico intacto. Locks y temporales de calidad propios liberados. Estado/progreso y versiones completas conservados; los procesos terminaron y no se reiniciaron automáticamente.

**333 pruebas aprobadas en desarrollo y 333 desde el wheel instalado**, copia de verificación sin src/data, 21 imports aislados, Ruff check/format y pip check en ambos entornos sin errores. El wheel probado coincide byte por byte con todos los módulos Python actuales. No se añadieron dependencias para este cierre parcial.

Wheel probado SHA-256: `6140df7fffd36f28761f63f9682707101a970f56c0af3d7b28591c94dd63307f`. Lock SHA-256: `372c8949a3c4fbc62c3f334d8ddf565ff213e56a80deca8d00a007cde6673529`. Evidencia local ampliada: `.cache/t15/blocked-audit.json`.

La conversión de features cuenta además con una optimización NumPy equivalente probada mediante comparación exacta de tablas para todos los meses/días/horas de 2024/2025, minutos muestreados y casos DST/pasajeros ausentes, y sobre 8.192 filas reales. El proceso de referencia se detuvo por calidad antes del cambio de motor previsto para abril; los 14 lotes conservados fueron generados con el motor de referencia. La muestra no certifica rendimiento anual.

## Pendiente

Resolver explícitamente el rechazo de marzo antes de reanudar. Después: completar las fuentes restantes, publicar y auditar T14, calcular la mediana exacta sobre todo train y verificar las predicciones/MAE/RMSE de validation. El baseline y el perfil 4 GiB libres/2 GiB RSS ya están aprobados. No hay métricas reales de baseline que reportar ni candidatos T16 entrenados. Test/replay no se usaron para seleccionar el baseline. No hubo promoción, registro MLflow ni nuevo commit/push.

## Decisión y fuente oficial posteriores

El usuario eligió conservar D-04 y revisar la fuente. HEAD del objeto oficial: 69.964.745 bytes y ETag multipart idéntico al calculado localmente (14 partes de 5 MiB). No se descargó el dataset ni se encontró indicio de una versión corregida distinta en esa URL. Esta comprobación no verifica SHA-256 remoto ni la descarga histórica; no cambió el manifiesto local. [Método, fuente y límites](../../docs/t14-t15-quality-blocker.md). El rechazo sigue vigente, sin excepción aprobada.

## Continuación independiente posterior

Ajuste exacto train 2024 completo y auditado: 41.119.495 etiquetas, mediana 12,983333 minutos; 561 filas apartadas por corte de etiqueta entre 41.120.056 elegibles DQ. Evaluación y cierre de T14/T15 pendientes de marzo 2025; D-04 permanece congelada. [Ajuste real](t15_train_fit.md). Las afirmaciones anteriores de ausencia de fit corresponden al rechazo inicial antes de esta separación aprobada. Evaluación/cierre siguen pendientes.

## Excepción posterior y evaluación completa de T15

Se conserva el rechazo original. La aceptación excepcional exacta de marzo y evaluación posteriores se documentan en [el reporte T15](t15_baseline_validation.md). T14 integral sigue pendiente; no se amplió la excepción a otros meses.
