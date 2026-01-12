"""Base service module for transaction processing.

This module provides a base service class that encapsulates common
operations for transaction processing pipelines, including ML predictions
and database persistence.
"""

from sqlalchemy.orm import Session

from .api import predict_batch
from .database import db_write_results


class BaseService:
    """
    Base service class for transaction processing pipelines.

    This class encapsulates core operations (predictions, database writes)
    that are common across batch and streaming processing pipelines.
    Subclasses should implement the `read()` method for data loading and
    may add source-specific attributes (e.g., S3 path, Kafka consumer).

    Attributes
    ----------
    ml_api_url : str
        URL for ML classification API.
    db_session : Session
        SQLAlchemy database session for persistence.

    Methods
    -------
    predict(transactions: list[dict]) -> tuple[list[dict], list[dict]]
        Get classification predictions from ML API.
    bulk_write(transactions: list[dict], predictions: list[dict]) -> None
        Persist transactions and predictions to database.
    read(batch_size: int) -> Iterator[tuple[list[dict], list[dict]]]
        Load and yield transaction batches. Must be implemented by subclasses.

    Notes
    -----
    This is an abstract base class. Subclasses must implement `read()` method
    for their specific data sources (S3, Kafka, etc.).
    """

    def __init__(self, ml_api_url: str, db_session: Session) -> None:
        """
        Initialize BaseService with ML API and database configuration.

        Parameters
        ----------
        ml_api_url : str
            ML API endpoint URL for classification predictions.
        db_session : Session
            SQLAlchemy session for database operations.

        Notes
        -----
        Subclasses may accept additional parameters for source-specific
        configuration (e.g., S3 credentials, Kafka consumer).
        """
        self.ml_api_url = ml_api_url
        self.db_session = db_session

    def predict(self, transactions: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Get classification predictions from ML API for transaction batch.

        Parameters
        ----------
        transactions : list[dict]
            List of validated transaction dictionaries.

        Returns
        -------
        tuple[list[dict], list[dict]]
            Tuple containing:
            - List of prediction dictionaries
            - List of failed transactions (if any)

        Notes
        -----
        Delegates to predict_batch() with automatic retry logic.
        """
        return predict_batch(transactions, self.ml_api_url)

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

        Notes
        -----
        Performs bulk insert/upsert operations for efficiency.
        Delegates to db_write_results() for database operations.
        """
        db_write_results(self.db_session, transactions, predictions)
