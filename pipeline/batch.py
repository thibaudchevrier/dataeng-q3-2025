import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from infrastructure import get_db_session, db_write_results, load_and_validate_transactions, predict_batch

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
    db_row_batch_size = int(os.getenv('DB_ROW_BATCH_SIZE', '1000'))
    
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
    all_valid_transactions = []
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
                    transactions, predictions = result
                    
                    if predictions:
                        all_valid_transactions.extend(transactions)
                        all_predictions.extend(predictions)
                        total_processed += len(predictions)
                    else:
                        failed_transactions.extend(transactions)
                        logger.warning(f"Batch {batch_id}: {len(transactions)} transactions added to failed queue")

                    if len(all_predictions) >= db_row_batch_size or len(all_valid_transactions) >= db_row_batch_size:
                        # Write results to database in bulk
                        db_write_results(session, all_valid_transactions, all_predictions)
            
            logger.info(f"Batch {batch_id}: Completed. Total progress: {total_processed}/{total_processed + len(failed_transactions)} successful")

        db_write_results(session, all_valid_transactions, all_predictions)

    
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
