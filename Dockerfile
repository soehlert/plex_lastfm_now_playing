FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Install dependencies using uv
COPY pyproject.toml uv.lock* ./
RUN uv venv && source .venv/bin/activate && uv pip install -e .

# Create user
RUN groupadd --gid 1001 appgroup && \
    useradd --uid 1001 --gid 1001 --create-home --shell /bin/bash scrobbler

# Set permissions
RUN chown -R scrobbler:appgroup /app

# Switch to non-root user
USER scrobbler

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "plex_lastfm_now_playing.plex_lastfm_now_playing:app", "--bind", "0.0.0.0:8000"]