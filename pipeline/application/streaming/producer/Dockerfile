FROM ghcr.io/astral-sh/uv:python3.13-bookworm AS build

WORKDIR /app

# Copy root workspace configuration first (required for workspace = true to work)
COPY pyproject.toml uv.lock /app/

# Copy the library and producer to match workspace structure
COPY pipeline/library/ /app/pipeline/library/
COPY pipeline/application/streaming/producer/ /app/pipeline/application/streaming/producer/

# Change to producer directory and install dependencies
WORKDIR /app/pipeline/application/streaming/producer
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS release

WORKDIR /app

ENV VIRTUAL_ENV="/app/.venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Copy virtual environment from build stage - it's at the workspace root!
COPY --from=build /app/.venv /app/.venv

# Copy library source (required because library is installed as editable reference)
COPY --from=build /app/pipeline/library /app/pipeline/library

# Copy application from build stage
COPY --from=build /app/pipeline/application/streaming/producer/main.py /app/main.py

CMD ["python", "main.py"]
