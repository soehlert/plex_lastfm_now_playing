FROM python:3.12-slim AS builder

WORKDIR /app
RUN pip install uv
COPY pyproject.toml uv.lock ./
COPY src ./src
RUN uv build --out-dir /app/dist .


FROM python:3.12-slim

WORKDIR /app
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid 1001 --create-home --shell /bin/bash appuser
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install /tmp/*.whl && \
    rm /tmp/*.whl
USER appuser
EXPOSE 8000
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "plex_lastfm_now_playing.plex_lastfm_now_playing:app", "--bind", "0.0.0.0:8000"]
