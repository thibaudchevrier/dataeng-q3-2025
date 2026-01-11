"""
Base service module for transaction processing.

This module provides a base service class that encapsulates common
operations for transaction processing pipelines, including ML predictions
and database persistence.
"""

from .api import predict_batch
from .database import db_write_results
from sqlalchemy.orm import Session


class BaseService:
    """
    Base service class for transaction processing pipelines.
    
    This class encapsulates core operations (predictions, database writes)
    that are common across batch and streaming processing pipelines.
    Subclasses should implement the `read()` method for data loading.
    
    Attributes
    ----------
    s3_path : str
        S3/MinIO path to transaction data source.
    storage_options : dict
        Storage configuration for S3 access (credentials, endpoint).
    ml_api_url : str
        URL for ML fraud detection API.
    db_session : Session
        SQLAlchemy database session for persistence.
        
    Methods
    -------
    predict(transactions: list[dict]) -> tuple[list[dict], list[dict]]
        Get fraud predictions from ML API.
    bulk_write(transactions: list[dict], predictions: list[dict]) -> None
        Persist transactions and predictions to database.
    """

    def __init__(self, s3_path: str, storage_options: dict, ml_api_url: str, db_session: Session) -> None:
        """
        Initialize BaseService with configuration.
        
        Parameters
        ----------
        s3_path : str
            S3/MinIO path to transaction data.
        storage_options : dict
            S3 configuration (credentials, endpoint URL).
        ml_api_url : str
            ML API endpoint URL.
        db_session : Session
            SQLAlchemy session for database operations.
        """
        self.s3_path = s3_path
        self.storage_options = storage_options
        self.ml_api_url = ml_api_url
        self.db_session = db_session


    def predict(self, transactions: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Get fraud predictions from ML API for transaction batch.
        
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