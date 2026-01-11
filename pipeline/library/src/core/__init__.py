"""
Core business logic layer for transaction processing.

This package provides core domain logic including:
- Pydantic models for transactions and predictions
- Transaction validation with automatic UUID generation
- Service orchestration for batch and streaming pipelines
"""

from .data_validation import validate_transaction_records
from .orchestrate import orchestrate_service

__all__ = ["validate_transaction_records", "orchestrate_service"]