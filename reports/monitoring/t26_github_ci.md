# T26 — Evidencia CI en GitHub

**PASS técnico, 2026-11-09.** Publicación autorizada. [PR #1 en borrador](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/pull/1)
contra `main`, sin merge. La entrega de código T20–T28 es
[`f675188`](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/commit/f675188fa52d7d50fc6a61f181569975ff846ded):
51 archivos auditados, sin datos, modelos, SQLite, secretos ni el PDF nuevo.

| Comprobación | Commit | Ejecución | Resultado |
|---|---|---|---|
| CI del PR | f675188 | [42717204897](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/actions/runs/42717204897) | PASS |
| CI del push | f675188 | [42717203539](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/actions/runs/42717203539) | PASS |
| Demostración roja, rama ci/t26-signal | 22396d9 | [42717406383](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/actions/runs/42717406383) | FAIL intencional verificado |
| Restauración, rama ci/t26-signal | 3d89195 | [42718092772](https://github.com/ModoJorgeBT/nyc-yellow-taxi-mlops/actions/runs/42718092772) | PASS, 601 pruebas y smoke |

Los logs del PR y push confirman **601 pruebas**, Ruff, formato, dependencias,
smoke HTTP real 503 y comprobación de producción. El job rojo construyó las
imágenes y falló exactamente en `test_ci_detects_authorized_failure`, con
AssertionError y una prueba fallida; no fue un error de infraestructura.
Los jobs del PR, push y rojo duraron 294, 206 y 165 segundos respectivamente,
verificados mediante timestamps de GitHub: todos dentro de los 20 minutos.
La restauración eliminó ese único archivo y su árbol Git es idéntico al de
f675188. La prueba fallida nunca formó parte del PR.

El runner verificó el builder fijado y los límites globales 2 CPU/4 GiB;
mínimo 10 GiB de disco y timeout 20 minutos. Solo fixtures sintéticas, sin
descarga de datasets, ajuste de modelos reales ni cambios de champion/D-04.

Los logs y recibos originales se conservan en `.cache/t26-t28/`; los enlaces
anteriores son evidencia remota independiente de esa carpeta local. T26
tiene cierre técnico con PR verde y demostración roja/verde. G5 y T29–T31
siguen pendientes. [Contrato y límites](../../docs/t26-t28.md).
