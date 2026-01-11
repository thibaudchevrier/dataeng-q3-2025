FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS build

WORKDIR /app

# Recreate the folder structure: library/ and streaming/producer/
# This maintains the relative paths expected by pyproject.toml (../../library)
COPY library/ /app/library/
COPY streaming/producer/pyproject.toml streaming/producer/uv.lock /app/streaming/producer/
COPY streaming/producer/main.py /app/streaming/producer/main.py

# Change to producer directory and install dependencies
WORKDIR /app/streaming/producer
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS release

WORKDIR /app

ENV VIRTUAL_ENV="/app/.venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy virtual environment from build stage
COPY --from=build /app/streaming/producer/.venv /app/.venv

# Copy library source (required because library is installed as editable reference)
COPY --from=build /app/library /app/library

# Copy application from build stage
COPY --from=build /app/streaming/producer/main.py /app/main.py

CMD ["python", "main.py"]
