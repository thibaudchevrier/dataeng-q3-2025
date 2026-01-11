"""
Pydantic data models for transaction processing.

This module defines Pydantic models for transactions and predictions,
providing automatic validation, type checking, and UUID generation.
"""

from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, field_validator


class Transaction(BaseModel):
    """
    Transaction model with validation.

    Used for both CSV/Kafka input (validates and assigns UUID).
    Ignores incoming 'id' field and always generates a new UUID.

    Attributes
    ----------
    id : str
        Unique transaction identifier (auto-generated UUID).
    description : str
        Transaction description text.
    amount : float
        Transaction amount.
    timestamp : str
        ISO format timestamp of transaction.
    merchant : str | None
        Merchant name (optional).
    operation_type : str
        Type of operation (e.g., 'debit', 'credit').
    side : str
        Transaction side indicator.
    processing_type : str
        Type of processing ('batch' or 'streaming').
    run_id : str
        Unique identifier for the processing run.
    """

    id: str  # Will be replaced with UUID
    description: str
    amount: float
    timestamp: str  # Will be converted to datetime
    merchant: str | None
    operation_type: str
    side: str

    # Lineage tracking fields
    processing_type: str
    run_id: str

    @field_validator("id", mode="before")
    @classmethod
    def replace_id_with_uuid(cls, _) -> str:
        """
        Replace incoming id with a fresh UUID.

        Parameters
        ----------
        _ : Any
            Incoming id value (ignored).

        Returns
        -------
        str
            Newly generated UUID string.

        Notes
        -----
        Always generates a new UUID regardless of input value.
        Ensures unique transaction identifiers across all sources.
        """
        return str(uuid4())

    @field_validator("timestamp")
    @classmethod
    def parse_timestamp(cls, v: str) -> str:
        """
        Parse timestamp string to ISO format for database.

        Parameters
        ----------
        v : str
            Timestamp string in various formats.

        Returns
        -------
        str
            ISO format timestamp string.

        Raises
        ------
        ValueError
            If timestamp format is not recognized.

        Notes
        -----
        Supports formats: 'YYYY-MM-DD HH:MM:SS' and 'YYYY-MM-DDTHH:MM:SS'.
        Converts to ISO format for consistent database storage.
        """
        if isinstance(v, str):
            # Handle various timestamp formats
            try:
                # Try parsing common formats
                dt = datetime.strptime(v, "%Y-%m-%d %H:%M:%S")
                return dt.isoformat()
            except ValueError:
                try:
                    dt = datetime.strptime(v, "%Y-%m-%dT%H:%M:%S")
                    return dt.isoformat()
                except ValueError as exc:
                    raise ValueError(f"Invalid timestamp format: {v}") from exc
        return v

    class Config:
        """Pydantic model configuration for Transaction class."""

        # Allow extra fields for forward compatibility
        extra = "ignore"
