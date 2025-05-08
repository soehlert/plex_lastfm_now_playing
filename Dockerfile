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
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "src.plex_lastfm_now_playing.main:app", "--bind", "0.0.0.0:8000"]