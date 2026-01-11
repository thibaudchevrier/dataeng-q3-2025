"""
Transaction validation module.

This module provides Pydantic-based validation for transaction records,
ensuring data quality and automatically generating UUIDs for valid
transactions.
"""

import logging

from .model import Transaction
from pydantic import ValidationError as PydanticValidationError


logger = logging.getLogger(__name__)


def validate_transaction_records(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Validate a list of transaction records using Pydantic.

    Parameters
    ----------
    records : list[dict]
        List of transaction records as dictionaries to validate.

    Returns
    -------
    tuple[list[dict], list[dict]]
        Tuple containing:
        - List of validated transaction dictionaries (with auto-generated UUIDs).
        - List of invalid transaction error dictionaries.
        
    Notes
    -----
    The Transaction model auto-generates UUIDs via default_factory.
    Validation errors are logged for debugging purposes.
    """
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

    return validated_transactions, invalid_transactions