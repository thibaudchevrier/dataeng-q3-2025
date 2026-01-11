"""
Batch processing pipeline for transaction data.

This module implements a batch processing pipeline that loads transactions
from S3/MinIO, validates them, performs ML fraud predictions in parallel,
and persists results to PostgreSQL database.
"""

import logging
import os
from datetime import datetime
from infrastructure import BaseService, load_and_validate_transactions, get_db_session
from core import orchestrate_service

from typing import Iterator

from infrastructure.service import BaseService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BatchService(BaseService):
    """
    Batch processing service for transaction pipelines.
    
    Extends BaseService to implement batch-specific data loading
    via load_and_validate_transactions generator. Provides read()
    method for orchestration layer.
    
    Methods
    -------
    read(batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]
        Load and validate transactions in batches from S3/MinIO.
    """

    def read(self, batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]:
        """
        Load and validate transactions in batches.
        
        Parameters
        ----------
        batch_size : int
            Number of transactions to load per batch.
            
        Yields
        ------
        tuple[list[dict], list[dict]]
            Tuple containing:
            - List of valid transactions
            - List of invalid transactions
            
        Notes
        -----
        Delegates to load_and_validate_transactions generator.
        Uses s3_path and storage_options from parent class.
        """
        return load_and_validate_transactions(
            s3_path=self.s3_path,
            storage_options=self.storage_options,
            batch_size=batch_size
        )


def main():
    """
    Execute batch processing pipeline.
    
    This function orchestrates the complete batch processing workflow:
    - Loads configuration from environment variables
    - Creates database session
    - Initializes BatchService with S3/MinIO credentials
    - Runs orchestrate_service for parallel processing
    
    Environment Variables
    ---------------------
    ML_API_URL : str
        ML API endpoint (default: 'http://localhost:8000').
    ROW_BATCH_SIZE : int
        Transactions per batch from source (default: 5000).
    API_BATCH_SIZE : int
        Transactions per API request (default: 100).
    API_MAX_WORKERS : int
        Parallel API workers (default: 5).
    DB_ROW_BATCH_SIZE : int
        Threshold for bulk database writes (default: 1000).
    DATABASE_URL : str
        PostgreSQL connection string (required).
    KEY : str
        MinIO access key (required).
    SECRET : str
        MinIO secret key (required).
    ENDPOINT_URL : str
        MinIO endpoint URL (required).
        
    Notes
    -----
    Generates unique pipeline_run_id for tracking execution.
    Logs configuration and progress throughout execution.
    """
    logger.info("Starting batch pipeline")
    
    # Generate unique pipeline run ID
    pipeline_run_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Pipeline Run ID: {pipeline_run_id}")
    
    ml_api_url = os.getenv('ML_API_URL', 'http://localhost:8000')
    row_batch_size = int(os.getenv('ROW_BATCH_SIZE', '5000'))
    api_batch_size = int(os.getenv('API_BATCH_SIZE', '100'))
    api_max_workers = int(os.getenv('API_MAX_WORKERS', '5'))
    db_row_batch_size = int(os.getenv('DB_ROW_BATCH_SIZE', '1000'))
    
    # Read and validate CSV from MinIO
    s3_path = "s3://transactions/transactions_fr.csv"
    storage_options = {
        "key": os.environ['KEY'],
        "secret": os.environ['SECRET'],
        "client_kwargs": {
            "endpoint_url": os.environ['ENDPOINT_URL']
        }
    }

    with get_db_session(os.environ['DATABASE_URL']) as session:
        orchestrate_service(
            service=BatchService(
                s3_path=s3_path,
                storage_options=storage_options,
                ml_api_url=ml_api_url,
                db_session=session
            ),
            row_batch_size=row_batch_size,
            api_batch_size=api_batch_size,
            api_max_workers=api_max_workers,
            db_row_batch_size=db_row_batch_size
        )



if __name__ == "__main__":
    main()
