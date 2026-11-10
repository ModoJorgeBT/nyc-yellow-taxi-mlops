# Perfil aprobado: Linux amd64 / Python 3.14.7. Base inmutable.
FROM python:3.14.7-slim-bookworm@sha256:998acd06f485adfd6890e3e15a4b542543e0cf22ff904310095da328a5e3e561 AS build
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /build
ARG BUILD_PROFILE=local
COPY configs/container-wheels-linux.json configs/container-system-packages.json ./configs/
COPY scripts/container_build.py ./scripts/container_build.py
COPY requirements-serving-linux.lock ./
RUN python scripts/container_build.py --preflight --profile "$BUILD_PROFILE" \
    && python scripts/container_build.py --fetch system --destination /tmp/system \
    && dpkg -i /tmp/system/*.deb \
    && python scripts/container_build.py --fetch wheels --destination /tmp/wheels \
    && python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-index --find-links=/tmp/wheels \
       --require-hashes --only-binary=:all: -r requirements-serving-linux.lock \
    && /opt/venv/bin/python -m pip check
COPY pyproject.toml README.md ./
COPY src ./src
RUN /opt/venv/bin/python -m pip install --no-deps --no-build-isolation .

FROM build AS ci
ENV PATH=/opt/venv/bin:$PATH HOME=/tmp MLFLOW_DISABLE_TELEMETRY=true \
    MLFLOW_DISABLE_AGENT_HINT=1 MLFLOW_SERVER_ENABLE_JOB_EXECUTION=false
COPY configs/ci-tools-linux.json ./configs/
COPY requirements-ci-linux.lock ./
RUN python -c "import json; from pathlib import Path; from scripts.container_build import download_file; download_file(json.load(open('configs/ci-tools-linux.json'))['ruff'],Path('/tmp/ci-tools'))" \
    && python -m pip install --no-index --find-links=/tmp/ci-tools --no-deps \
       --require-hashes -r requirements-ci-linux.lock
WORKDIR /workspace
CMD ["python", "scripts/ci_checks.py"]

FROM ci AS ci-monitoring
WORKDIR /build
COPY configs/monitoring-wheels-linux.json ./configs/
COPY requirements-monitoring-linux.lock ./
RUN python scripts/container_build.py --fetch-monitoring --destination /tmp/wheels \
    && python -m pip install --no-index --find-links=/tmp/wheels --require-hashes \
       --only-binary=:all: -r requirements-monitoring-linux.lock \
    && python -m pip check
WORKDIR /workspace

FROM python:3.14.7-slim-bookworm@sha256:998acd06f485adfd6890e3e15a4b542543e0cf22ff904310095da328a5e3e561 AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 HOME=/tmp MLFLOW_DISABLE_TELEMETRY=true MLFLOW_DISABLE_AGENT_HINT=1 \
    OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4
WORKDIR /app
COPY --from=build /tmp/system /tmp/system
RUN dpkg -i /tmp/system/*.deb \
    && rm -r /tmp/system \
    && groupadd --gid 10001 app \
    && useradd --uid 10001 --gid 10001 --no-create-home app \
    && mkdir -p tracking data reports .cache \
    && chown 10001:10001 tracking data reports .cache
COPY --from=build /opt/venv /opt/venv
COPY configs ./configs
COPY scripts ./scripts
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --start-period=45s --retries=6 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=3)"]
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log", "--log-config", "configs/serving-logging.json"]
