# Publicación requerida para cerrar T26

Estado: **APROBADA por el usuario el 2026-11-09**; verificación local PASS
(601 pruebas Linux, Ruff, dependencias, smoke HTTP y build/inspección de
producción). Código publicado en ci/t26-t28, PR #1 en borrador verde y
demostración roja/verde en ci/t26-signal verificadas. Backend fijado y límites
globales CI comprobados. [Evidencia real](../reports/monitoring/t26_github_ci.md).

El remoto `ModoJorgeBT/nyc-yellow-taxi-mlops` tiene como último commit local
`07f8729` (tercera entrega T14–T19). T20–T25 todavía no están comprometidas;
son necesarias para probar la API/Docker de T26. El paquete propuesto incluye
T20–T28: código, configuración, locks, fixtures, workflow y documentación.
Excluye datos, modelos, SQLite, envs, secretos, cachés/reportes JSON y el PDF
nuevo `Informe_Proyecto_MLOps_NYC_Taxi_2.pdf`, que no corresponde a estas tareas.

Después de completar las pruebas locales, la aprobación permitiría:

1. Crear un commit en una rama nueva `ci/t26-t28` y subirla al mismo remoto,
   conservando main. Crear un PR en borrador contra main, sin merge ni comentarios.
2. Ejecutar CI sobre ese código y verificar el PR verde en GitHub.
3. Crear una rama de demostración separada `ci/t26-signal`, introducir una
   única prueba sintética fallida, observar CI rojo y restaurarla con otro
   commit para verificar verde. La prueba fallida no formará parte del PR.
4. Conservar enlaces/SHA/resultados reales de las ejecuciones en el reporte.

No se forzarán pushes, cambiarán protecciones del repositorio ni se publicarán
imágenes. Si el acceso existente no permite workflows/PR, se consultará antes
de cambiar autenticación o permisos. No se solicita merge ni publicación en main.

## PR propuesto

Título: `Implement serving, Docker, CI and quality monitoring (T20–T28)`

La entrega conecta el champion LightGBM aprobado a FastAPI y Docker Compose,
conservando el Registry original. Añade contrato REST validado, logs agregados
con ventanas operativas y comparación mensual de calidad sobre evidencia
congelada. El workflow comprueba Ruff, fixtures, HTTP y build sin datasets
reales. No reentrena ni cambia pesos, D-04 o reglas automáticas de promoción.

Validación local y enlaces de CI reales se adjuntarán antes del cierre de T26.
La demostración roja/verde usa una rama separada; G5 no se considera terminado
porque T29–T31 quedan fuera de esta entrega.
