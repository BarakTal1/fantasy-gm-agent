FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# --no-install-project: install only third-party deps (the app source isn't copied
# yet, and we run it via PYTHONPATH, not as an installed package). --no-dev skips
# nba_api/pandas so the runtime image stays lean.
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
ENV PYTHONPATH=/app/src
CMD ["sh", "scripts/start.sh"]
