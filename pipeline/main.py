import logging
import requests
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple, Optional, Callable
import time
from functools import wraps, partial
from datetime import datetime
from utils.data_loader import load_and_validate_transactions
from utils.database import get_db_session, bulk_insert_transactions, bulk_upsert_predictions

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
    
    # Database configuration
    database_url = os.getenv('DATABASE_URL', 'postgresql://qonto:qonto_password@localhost:5432/transactions')
    
    # Configure S3/MinIO credentials
    os.environ['KEY'] = 'minioadmin'
    os.environ['SECRET'] = 'minioadmin'
    os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:9000'
    
    row_batch_size = int(os.getenv('ROW_BATCH_SIZE', '5000'))
    api_batch_size = int(os.getenv('API_BATCH_SIZE', '100'))
    api_max_workers = int(os.getenv('API_MAX_WORKERS', '5'))
    row_dbatch_size = int(os.getenv('ROW_DB_BATCH_SIZE', '1000'))
    
    # Read and validate CSV from MinIO
    s3_path = "s3://transactions/transactions_fr.csv"
    storage_options = {
        "key": os.environ['KEY'],
        "secret": os.environ['SECRET'],
        "client_kwargs": {
            "endpoint_url": os.environ['AWS_ENDPOINT_URL']
        }
    }

    # Process validated batches with parallel workers
    total_processed = 0
    all_predictions = []
    failed_transactions = []
    all_invalid_transactions = []  # Keep track of all invalid transactions

    # Use database context manager
    with get_db_session(database_url) as session:
        # Load and validate transactions - returns generator and invalid transactions
        for batch_id, (valid_transactions, invalid_transactions) in enumerate(load_and_validate_transactions(
            s3_path=s3_path,
            storage_options=storage_options,
            batch_size=row_batch_size
        )):

            # Log invalid transactions
            if invalid_transactions:
                all_invalid_transactions.extend(invalid_transactions)
                logger.error(f"Batch {batch_id}: Found {len(invalid_transactions)} invalid transactions during validation")
                for error in invalid_transactions[:5]:  # Show first 5
                    logger.error(f"  - {error}")
            
            if not valid_transactions:
                logger.warning(f"Batch {batch_id}: No valid transactions to process")
                continue
            
            logger.info(f"Batch {batch_id}: Processing {len(valid_transactions)} transactions with {api_max_workers} parallel workers, API batch size: {api_batch_size}")
            
            # Process API batches in parallel using ThreadPoolExecutor (INSIDE the loop)
            with ThreadPoolExecutor(max_workers=api_max_workers) as executor:
                # Map predict_batch function over API batches in parallel
                results = executor.map(
                    lambda args: predict_batch(args[1], args[0]), 
                    enumerate((valid_transactions[i:i + api_batch_size] for i in range(0, len(valid_transactions), api_batch_size)))
                )
                
                for result in results:
                    predictions, failed_batch = result
                    
                    if predictions:
                        all_predictions.extend(predictions)
                        total_processed += len(predictions)
                    
                    if failed_batch:
                        failed_transactions.extend(failed_batch)
                        logger.warning(f"Batch {batch_id}: {len(failed_batch)} transactions added to failed queue")
            
            logger.info(f"Batch {batch_id}: Completed. Total progress: {total_processed}/{total_processed + len(failed_transactions)} successful")

            # Insert transactions to database (idempotent)
            bulk_insert_transactions(session, valid_transactions)
            
            # Persist predictions to database (upsert)
            if all_predictions:
                bulk_upsert_predictions(session, all_predictions)
                logger.info(f"Persisted {len(all_predictions)} predictions to database")
                all_predictions = []  # Clear after writing
    
    # Final summary after ALL batches processed (outside context manager)
    logger.info(f"Batch pipeline completed - {total_processed} predictions received")
    
    if failed_transactions:
        logger.error(f"FAILED: {len(failed_transactions)} transactions failed after all retries")
    
    if all_invalid_transactions:
        logger.error(f"INVALID: {len(all_invalid_transactions)} transactions failed validation")
    
    if not failed_transactions and not all_invalid_transactions:
        logger.info("SUCCESS: All transactions processed successfully")




if __name__ == "__main__":
    main()
