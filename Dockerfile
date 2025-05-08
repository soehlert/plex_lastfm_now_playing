FROM python:3.12-slim

WORKDIR /app

RUN pip install uv
RUN uv venv

COPY pyproject.toml uv.lock* ./
RUN . .venv/bin/activate && uv pip install -e .

RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid 1001 --create-home --shell /bin/bash scrobbler

RUN chown -R scrobbler:appgroup /app

USER scrobbler

EXPOSE 8000

CMD ["/app/.venv/bin/gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "plex_lastfm_now_playing.plex_lastfm_now_playing:app", "--bind", "0.0.0.0:8000"]