# ADR 0001 — Ejecución local con Docker Compose

Fecha: 2026-11-03. Estado de la decisión: ACEPTADA por el equipo en la conversación. Entregable T01: CERRADO por aprobación humana al solicitar T03.

## Contexto

El proyecto académico exige demostrar un ciclo MLOps reproducible y defendible, con recursos acotados y sin infraestructura distribuida innecesaria. [Intent](../../intent.md) §6 prioriza local; [spec](../../spec.md) §§1/10 lo confirma y el [PDF](../../Proyecto_Maestria_MLOps_NYC_Taxi_Estructura.pdf) pp. 5–6/9/13 propone Compose y pide acordar local frente a cloud.

El equipo solicitó desarrollar con Python, MLflow, FastAPI y Docker Compose en local. Posteriormente autorizó los entregables documentales de T01, conservando pendientes las herramientas adicionales y la hipótesis de destino conocido.

## Decisión

La plataforma se desarrollará y demostrará localmente con Python, MLflow, FastAPI y Docker Compose. El único target sigue siendo duración en minutos con información disponible al inicio. No se añade nube pública, Kubernetes, Kafka, Airflow ni Terraform.

Separar lógicamente pipeline de datos/modelado, tracking/registro e inferencia; los servicios `mlflow`, `api` y `pipeline` bajo demanda son el diseño propuesto para revisión. La aprobación de Compose no fija su configuración ni autoriza implementar esos servicios en T01.

## Alternativas consideradas

- Despliegue cloud o plataforma distribuida: no elegidos para el MVP por alcance, costo y complejidad; requerirían una nueva necesidad y aprobación.
- Ejecución exclusivamente manual en el host: no elegida como mecanismo completo de demostración reproducible; el desarrollo y las CLI locales siguen siendo posibles según spec.

## Consecuencias

La demostración depende de recursos de la máquina y de Docker Desktop/Compose; debe documentarse el bootstrap y comprobarse en entorno limpio. Datos y artefactos requieren persistencia y backup. No se promete alta disponibilidad, escalado distribuido ni desempeño sin medición.

Una instalación limpia no contiene champion: su aprobación y carga son pasos explícitos. Los metadatos de respuestas deben reflejar el modelo realmente cargado. Registro, promoción y rollback son operaciones separadas.

## Decisiones que este ADR no cierra

D-01/D-02: meses y presupuesto; D-03: herramientas adicionales y versiones; D-04/D-05: umbrales; D-06: payload, destino y tiempo; D-07: SQLite, acceso a artefactos, alias, volúmenes y recarga; D-08: criterio general de terminado. Ver [registro de decisiones](../decisions.md).

## Evidencia y revisión

Evidencia de aceptación: instrucciones del equipo en la conversación de T01 del 2026-11-03; correcciones posteriores y cierre explícito de T01/T02 aprobados por el usuario. T03 y herramientas de entorno/PyArrow se autorizaron por separado, según el registro de decisiones. Este ADR no acredita aprobación docente general ni servicios ejecutándose; G0/G1 siguen abiertos.
