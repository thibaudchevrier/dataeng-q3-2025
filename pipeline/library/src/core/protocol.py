"""
Service protocol definition for batch processing pipeline.

This module defines the ServiceProtocol interface that all service
implementations must satisfy. Ensures consistent contract for data
reading, prediction, and persistence operations.
"""

from collections.abc import Iterator
from typing import Protocol


class ServiceProtocol(Protocol):
    """
    Protocol defining the interface for batch processing services.

    This protocol specifies the required methods for any service implementation
    that processes transaction batches through the pipeline. Services must
    implement read (data loading), predict (ML inference), and bulk_write
    (persistence) operations.

    Methods
    -------
    read(batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]
        Load and validate transactions from source, yielding batches.
    predict(transactions: list[dict]) -> list[dict]
        Get fraud predictions from ML API for transaction batch.
    bulk_write(transactions: list[dict], predictions: list[dict]) -> None
        Persist transactions and predictions to database.

    Notes
    -----
    This is a Protocol class (PEP 544) for structural subtyping.
    Any class implementing these methods satisfies this protocol.
    """

    def read(self, batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]:
        """
        Load and validate transactions from data source in batches.

        Parameters
        ----------
        batch_size : int
            Number of transactions to load per batch.

        Yields
        ------
        tuple[list[dict], list[dict]]
            Tuple containing:
            - List of valid transactions (passed validation)
            - List of invalid transactions (failed validation)
        """
        ...

    def predict(self, transactions: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Get fraud predictions from ML API for transaction batch.

        Parameters
        ----------
        transactions : list[dict]
            List of valid transaction dictionaries to predict.

        Returns
        -------
        tuple[list[dict], list[dict]]
            Tuple containing:
            - List of prediction dictionaries with fraud scores
            - List of failed transactions (if any)
        """
        ...

    def bulk_write(self, transactions: list[dict], predictions: list[dict]) -> None:
        """
        Persist transactions and predictions to database.

        Parameters
        ----------
        transactions : list[dict]
            List of transaction dictionaries to store.
        predictions : list[dict]
            List of prediction dictionaries corresponding to transactions.

        Returns
        -------
        None
        """
        ...
