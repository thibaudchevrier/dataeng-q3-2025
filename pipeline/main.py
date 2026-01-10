import logging
import polars as pl
import requests
from uuid import uuid4
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Tuple, Optional, Callable
import time
from functools import wraps
from datetime import datetime
from utils.database import Database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds for exponential backoff
        
    Returns:
        Decorated function that returns (result, None) on success or (None, original_args) on failure
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Tuple[Optional[List[Dict]], Optional[List[Dict]]]:
            delay = initial_delay
            transactions = args[0] if args else None
            batch_id = args[1] if len(args) > 1 else kwargs.get('batch_id', 'unknown')
            
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"Batch {batch_id}: Retry succeeded on attempt {attempt + 1}")
                    
                    return result, None
                    
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Batch {batch_id}: Attempt {attempt + 1}/{max_retries} failed - {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        logger.error(
                            f"Batch {batch_id}: All {max_retries} attempts failed - {e}. "
                            f"Moving {len(transactions) if transactions else 0} transactions to failed queue."
                        )
                        return None, transactions
            
            return None, transactions
        
        return wrapper
    return decorator


@retry_with_backoff(max_retries=int(os.getenv('MAX_RETRIES', '3')), initial_delay=1.0)
def predict_batch(transactions: List[Dict], batch_id: int) -> List[Dict]:
    """
    Send a batch of transactions to the ML API for prediction.
    
    Args:
        transactions: List of transaction dictionaries
        batch_id: Batch identifier for logging
        
    Returns:
        List of predictions from the API
    """
    response = requests.post(
        "http://localhost:8000/predict",
        json=transactions,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    predictions = response.json()
    logger.debug(f"Batch {batch_id}: Successfully processed {len(predictions)} transactions")
    return predictions


def main():
    logger.info("Starting batch pipeline")
    
    # Generate unique pipeline run ID
    pipeline_run_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    logger.info(f"Pipeline Run ID: {pipeline_run_id}")
    
    # Initialize database connection
    db_url = os.getenv(
        'DATABASE_URL',
        'postgresql://qonto:qonto_password@localhost:5432/transactions'
    )
    db = Database(db_url)
    logger.info("Database connection established")
    
    # Configure S3/MinIO credentials as environment variables
    # s3fs uses these standard AWS environment variables
    os.environ['KEY'] = 'minioadmin'
    os.environ['SECRET'] = 'minioadmin'
    os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:9000'
    batch_size = int(os.getenv('BATCH_SIZE', '100'))
    max_workers = int(os.getenv('MAX_WORKERS', '5'))
    
    # Read CSV directly from MinIO using S3 path
    s3_path = "s3://transactions/transactions_fr.csv"
    logger.info(f"Reading data from MinIO: {s3_path}")
    
    df = pl.read_csv(
        s3_path,
        separator=";",
        decimal_comma=True,
        storage_options={
            "key": os.environ['KEY'],
            "secret": os.environ['SECRET'],
            "client_kwargs": {
                "endpoint_url": os.environ['AWS_ENDPOINT_URL']
            }
        }
    )
    
    logger.info(f"Successfully loaded {len(df)} transactions")
    
    # Generate UUIDs for transactions
    df = df.with_columns(pl.Series("id", [str(uuid4()) for _ in range(len(df))]))
    
    # Process in batches with parallel workers
    total_processed = 0
    all_predictions = []
    failed_transactions = []
    
    logger.info(f"Processing transactions with {max_workers} parallel workers, batch size: {batch_size}")
    
    # Process batches in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Create generator of (batch_id, transactions) tuples
        batch_generator = enumerate(chunk.to_dicts() for chunk in df.iter_slices(n_rows=batch_size))
        
        # Map predict_batch function over all batches in parallel
        for batch_id, result in enumerate(executor.map(
            lambda args: predict_batch(args[1], args[0]),
            batch_generator
        )):
            predictions, failed_batch = result
            
            if predictions:
                all_predictions.extend(predictions)
                total_processed += len(predictions)
                logger.info(f"Progress: {total_processed}/{len(df)} transactions processed")
            
            if failed_batch:
                failed_transactions.extend(failed_batch)
                logger.warning(f"Batch {batch_id}: {len(failed_batch)} transactions added to failed queue")
    
    # Summary
    logger.info(f"Batch pipeline completed - {total_processed} predictions received")
    
    if failed_transactions:
        logger.error(f"FAILED: {len(failed_transactions)} transactions failed after all retries")
        logger.error(f"Failed transaction IDs: {[t['id'] for t in failed_transactions[:10]]}...")
        # TODO: Write failed transactions to a dead letter queue or file for later reprocessing
    else:
        logger.info("SUCCESS: All transactions processed successfully")
    
    if all_predictions:
        logger.info(f"Sample prediction: {all_predictions[0]}")
    
    return all_predictions, failed_transactions




if __name__ == "__main__":
    main()
