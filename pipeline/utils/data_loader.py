import polars as pl
from typing import Iterator, Tuple, List, Dict
import logging
from models.schemas import Transaction
from pydantic import ValidationError as PydanticValidationError

logger = logging.getLogger(__name__)


def validate_transaction_dataframe(df: pl.DataFrame) -> pl.DataFrame:
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
) -> Iterator[Tuple[List[Dict], List[Dict]]]:
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

    for sub_df in validate_transaction_dataframe(df).iter_slices(n_rows=batch_size):
    
        # Convert to list of dicts for validation
        records = sub_df.to_dicts()
        
        # Validate and auto-assign UUIDs
        validated_transactions = []
        invalid_transactions = []
        
        logger.info("Validating transactions...")
        
        for record in records:
            try:            
                # Transaction model auto-generates UUID via default_factory
                validated_transactions.append(Transaction(**record).model_dump())
                
            except PydanticValidationError as e:
                # Collect validation errors
                invalid_transactions.append(record)
                logger.error(f"Validation failed for record: {e}")
        
        logger.info(f"Validation complete: {len(validated_transactions)} valid, {len(invalid_transactions)} invalid")
        
        if invalid_transactions:
            logger.warning(f"Found {len(invalid_transactions)} invalid transactions")
            # Log a sample of errors
            for error in invalid_transactions[:5]:
                logger.warning(f"  - {error.error_message}")
        
        
        yield validated_transactions, invalid_transactions