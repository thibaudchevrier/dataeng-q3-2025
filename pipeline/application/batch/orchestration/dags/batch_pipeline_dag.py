"""
Airflow DAG for batch transaction processing pipeline.

This DAG orchestrates the batch processing of transaction data:
- Extracts data from S3/MinIO
- Validates transaction records
- Performs ML fraud predictions
- Loads results into PostgreSQL database

Schedule: Daily at 2 AM UTC
"""

import logging
from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from airflow.sdk.bases.hook import BaseHook

logger = logging.getLogger(__name__)

# Default arguments for the DAG
default_args = {
    "owner": "data-engineering",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

# Define the DAG
with DAG(
    dag_id="batch_transaction_pipeline",
    default_args=default_args,
    description="Batch processing pipeline for fraud detection on transaction data",
    schedule="*/2 * * * *",  # Every 2 minutes
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["batch", "ml", "transactions"],
) as dag:
    # Batch processing configuration (adjust as needed)
    BATCH_CONFIG = {
        "ROW_BATCH_SIZE": "5000",  # Number of rows to process at once from CSV
        "API_BATCH_SIZE": "100",  # Number of records per ML API request
        "API_MAX_WORKERS": "5",  # Concurrent API request workers
        "DB_ROW_BATCH_SIZE": "1000",  # Number of rows per database insert
    }

    # Get connections and secrets securely
    def get_environment_vars(**context):
        """Retrieve secrets from Airflow Connections and add batch configuration."""
        # Get PostgreSQL connection
        postgres_conn = BaseHook.get_connection("postgres_transactions")
        database_url = postgres_conn.get_uri()

        # Fix SQLAlchemy 2.x compatibility: replace postgres:// with postgresql://
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)

        # Get MinIO/S3 connection
        minio_conn = BaseHook.get_connection("minio_s3")
        endpoint_url = f"http://{minio_conn.host}:{minio_conn.port}"
        minio_key = minio_conn.login
        minio_secret = minio_conn.password

        # Get ML API connection
        ml_api_conn = BaseHook.get_connection("ml_api")
        ml_api_url = f"http://{ml_api_conn.host}:{ml_api_conn.port}"

        # Combine secrets with batch configuration
        env_vars = {
            "DATABASE_URL": database_url,
            "ENDPOINT_URL": endpoint_url,
            "KEY": minio_key,
            "SECRET": minio_secret,
            "ML_API_URL": ml_api_url,
        }
        env_vars.update(BATCH_CONFIG)

        # Store in XCom for next task
        return env_vars

    get_env_task = PythonOperator(
        task_id="get_environment_vars",
        python_callable=get_environment_vars,
    )

    # Task: Run batch processing with environment from XCom
    def run_batch_with_env(**context):
        """Run Docker container with environment variables from XCom."""
        import docker

        # Get environment variables from previous task
        env_vars = context["ti"].xcom_pull(task_ids="get_environment_vars")

        # Create Docker client
        client = docker.from_env()

        # Run container
        container = client.containers.run(
            image="batch-processor:latest",
            environment=env_vars,
            network="dataeng-q3-2025_ml-network",
            detach=False,
            remove=True,
            stdout=True,
            stderr=True,
        )

        logger.info(f"Batch processing output: {container.decode('utf-8')}")
        return "success"

    run_batch_processing = PythonOperator(
        task_id="run_batch_processing",
        python_callable=run_batch_with_env,
    )

    # Task: Log completion
    def log_completion(**context):
        """Log pipeline completion with execution metadata."""
        # Airflow 3.x uses 'logical_date' instead of 'execution_date'
        logical_date = context.get("logical_date") or context.get("data_interval_start")
        run_id = context["run_id"]
        logger.info(f"Batch pipeline completed successfully for {logical_date}")
        logger.info(f"Run ID: {run_id}")
        return "success"

    log_completion_task = PythonOperator(
        task_id="log_completion",
        python_callable=log_completion,
    )

    # Define task dependencies
    get_env_task >> run_batch_processing >> log_completion_task  # type: ignore[expression-value]
