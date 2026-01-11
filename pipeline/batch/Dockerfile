FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS build

WORKDIR /app

# Copy library to maintain the relative path structure expected by pyproject.toml
COPY library/ /app/library/

# Copy batch project files to /app/batch to maintain relative paths
COPY batch/pyproject.toml batch/uv.lock /app/batch/
COPY batch/main.py /app/batch/main.py

# Change to batch directory and install dependencies
WORKDIR /app/batch
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS release

WORKDIR /app

ENV VIRTUAL_ENV="/app/.venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy virtual environment from build stage
COPY --from=build /app/batch/.venv /app/.venv

# Copy library source (required because library is installed as editable reference)
COPY --from=build /app/library /app/library

# Copy application from build stage
COPY --from=build /app/batch/main.py /app/main.py

CMD ["python", "main.py"]
