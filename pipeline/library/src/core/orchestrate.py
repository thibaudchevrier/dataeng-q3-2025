"""Service orchestration module for batch processing.

This module provides orchestration logic for processing transaction batches
with parallel API calls, error handling, and bulk database operations.
Coordinates data flow between validation, prediction, and persistence layers.
"""

import functools
import logging
from concurrent.futures import ThreadPoolExecutor

from .protocol import ServiceProtocol

logger = logging.getLogger(__name__)


def orchestrate_service(
    service: ServiceProtocol, row_batch_size: int, api_batch_size: int, api_max_workers: int, db_row_batch_size: int
) -> tuple[int, list[dict], list[dict]]:
    """
    Orchestrate batch processing of transactions through the pipeline.

    This function coordinates the entire batch processing workflow:
    - Loading and validating transactions in batches
    - Parallel API calls for classification predictions
    - Bulk database writes for results
    - Error tracking and reporting

    Parameters
    ----------
    service : ServiceProtocol
        Service instance implementing read, predict, and bulk_write methods.
    row_batch_size : int
        Number of transactions to process in each batch from source.
    api_batch_size : int
        Number of transactions to send to ML API in each request.
    api_max_workers : int
        Maximum number of parallel workers for API calls.
    db_row_batch_size : int
        Threshold for bulk database writes.

    Returns
    -------
    tuple[int, list[dict], list[dict]]
        Tuple containing:
        - Total number of successfully processed transactions
        - List of failed transactions (after retries)
        - List of invalid transactions (validation failures)

    Notes
    -----
    Uses ThreadPoolExecutor for parallel API calls within each batch.
    Automatically handles retries via service.predict decorator.
    Performs bulk database writes when threshold is reached.
    """
    total_processed = 0
    all_predictions = []
    all_valid_transactions = []
    failed_transactions = []
    all_invalid_transactions = []  # Keep track of all invalid transactions

    # Load and validate transactions - returns generator and invalid transactions
    for batch_id, (valid_transactions, invalid_transactions) in enumerate(service.read(row_batch_size)):
        # Log invalid transactions
        if invalid_transactions:
            all_invalid_transactions.extend(invalid_transactions)
            logger.error(f"Batch {batch_id}: Found {len(invalid_transactions)} invalid transactions during validation")
            for error in invalid_transactions[:5]:  # Show first 5
                logger.error(f"  - {error}")

        if not valid_transactions:
            logger.warning(f"Batch {batch_id}: No valid transactions to process")
            continue

        logger.info(
            f"Batch {batch_id}: Processing {len(valid_transactions)} transactions "
            f"with {api_max_workers} parallel workers, API batch size: {api_batch_size}"
        )

        # Process API batches in parallel using ThreadPoolExecutor (INSIDE the loop)
        with ThreadPoolExecutor(max_workers=api_max_workers) as executor:
            # Map predict_batch function over API batches in parallel
            results = executor.map(
                lambda args: functools.partial(service.predict)(args[1]),
                enumerate(
                    valid_transactions[i : i + api_batch_size]
                    for i in range(0, len(valid_transactions), api_batch_size)
                ),
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
                    service.bulk_write(all_valid_transactions, all_predictions)

        logger.info(
            f"Batch {batch_id}: Completed. Total progress: {total_processed}/"
            f"{total_processed + len(failed_transactions)} successful"
        )

    service.bulk_write(all_valid_transactions, all_predictions)

    # Final summary after ALL batches processed (outside context manager)
    logger.info(f"Batch pipeline completed - {total_processed} predictions received")

    if failed_transactions:
        logger.error(f"FAILED: {len(failed_transactions)} transactions failed after all retries")

    if all_invalid_transactions:
        logger.error(f"INVALID: {len(all_invalid_transactions)} transactions failed validation")

    if not failed_transactions and not all_invalid_transactions:
        logger.info("SUCCESS: All transactions processed successfully")

    return total_processed, failed_transactions, all_invalid_transactions
