# Build stage: Install dependencies using uv
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS build

WORKDIR /app

# Copy workspace root files (for uv workspace resolution)
COPY pyproject.toml uv.lock /app/

# Copy orchestration module
COPY pipeline/application/batch/orchestration/ /app/pipeline/application/batch/orchestration/

# Set working directory to orchestration member
WORKDIR /app/pipeline/application/batch/orchestration

# Install dependencies (creates .venv at workspace root: /app/.venv)
RUN uv sync --frozen --no-default-groups

# Release stage: Use official Airflow 3.1.5 image with Python 3.12
FROM apache/airflow:3.1.5-python3.12

USER root

# Copy the virtual environment from build stage
COPY --from=build /app/.venv /app/.venv

USER airflow

# Add .venv to PATH so Airflow uses our dependencies
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/.venv/lib/python3.12/site-packages:$PYTHONPATH"
