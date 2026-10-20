FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements.txt ./
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt
COPY pyproject.toml README.md ./
COPY app ./app
COPY Leadscorefrontend/lead-scoring-prioritisation-system.html ./Leadscorefrontend/
RUN python -m pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && python -m pip install --no-cache-dir --no-deps --no-index --find-links=/wheels lead-scoring-backend \
    && rm -rf /wheels \
    && groupadd --gid 10001 leadscoring \
    && useradd --uid 10001 --gid leadscoring --no-create-home leadscoring
COPY --chown=leadscoring:leadscoring alembic ./alembic
COPY --chown=leadscoring:leadscoring alembic.ini ./
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
