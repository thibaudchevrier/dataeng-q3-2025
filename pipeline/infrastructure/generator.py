
import logging
from typing import Iterator
import polars as pl
from core.data_validation import validate_transaction_records

logger = logging.getLogger(__name__)


def __validate_transaction_dataframe(df: pl.DataFrame) -> pl.DataFrame:
    # Check for required columns
    required_cols = {'id', 'description', 'amount', 'timestamp', 'merchant', 'operation_type', 'side'}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    # Check for null values
    null_counts = df.null_count()
    total_nulls = sum([null_counts[col][0] for col in null_counts.columns])
    if total_nulls > 0:
        logger.warning(f"Found {total_nulls} null values in data - these rows will be filtered")
        df = df.drop_nulls()
        logger.info(f"After filtering nulls: {len(df)} transactions remain")
    return df


def load_and_validate_transactions(
    s3_path: str,
    storage_options: dict,
    batch_size: int = 100
) -> Iterator[tuple[list[dict], list[dict]]]:
    """
    Load transactions from S3/MinIO and yield validated batches.
    
    This function:
    1. Reads CSV from S3 using Polars
    2. Validates each transaction with Pydantic (auto-assigns UUID)
    3. Yields batches of validated transactions
    4. Collects invalid transactions for reporting
    
    Args:
        s3_path: S3 path to CSV file
        storage_options: S3/MinIO credentials
        batch_size: Number of transactions per batch
        
    Returns:
        Tuple of (validated_batches_generator, invalid_transactions_list)
    """
    logger.info(f"Reading data from {s3_path}")
    
    # Read CSV with Polars
    df = pl.read_csv(
        s3_path,
        separator=";",
        decimal_comma=True,
        storage_options=storage_options
    )
    
    logger.info(f"Loaded {len(df)} raw transactions from CSV")

    for sub_df in __validate_transaction_dataframe(df).iter_slices(n_rows=batch_size):
        yield validate_transaction_records(sub_df.to_dicts())