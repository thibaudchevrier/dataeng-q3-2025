"""
Simple database utilities for PostgreSQL operations.
"""
import logging
from typing import List, Dict
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, String, Float, DateTime, Integer, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime

logger = logging.getLogger(__name__)

Base = declarative_base()


class Transaction(Base):
    """Transaction table model"""
    __tablename__ = 'transactions'
    
    id = Column(String, primary_key=True)  # UUID from Pydantic
    description = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    timestamp = Column(DateTime, nullable=False)
    merchant = Column(String, nullable=False)
    operation_type = Column(String, nullable=False)
    side = Column(String, nullable=False)
    
    # Relationship to predictions
    predictions = relationship("Prediction", back_populates="transaction")


class Prediction(Base):
    """Prediction table model"""
    __tablename__ = 'predictions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_id = Column(String, ForeignKey('transactions.id'), unique=True, nullable=False)
    category = Column(String, nullable=False)
    confidence_score = Column(Float, default=1.0)
    model_version = Column(String, default='v1.0')
    predicted_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to transaction
    transaction = relationship("Transaction", back_populates="predictions")


@contextmanager
def get_db_session(database_url: str):
    """
    Context manager for database session.
    
    Usage:
        with get_db_session(url) as session:
            bulk_insert_transactions(session, transactions)
    """
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        echo=False
    )
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("Database connection established")
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()
        logger.info("Database connection closed")


def bulk_insert_transactions(session: Session, transactions: List[Dict]):
    """
    Insert transactions with ON CONFLICT DO NOTHING (idempotent).
    Re-running won't create duplicates.
    """
    if not transactions:
        return
    
    stmt = insert(Transaction).values(transactions)
    stmt = stmt.on_conflict_do_nothing(index_elements=['id'])
    
    session.execute(stmt)
    logger.info(f"Inserted {len(transactions)} transactions (skipped duplicates)")


def bulk_upsert_predictions(session: Session, predictions: List[Dict]):
    """
    UPSERT predictions: insert new ones, update existing ones.
    If transaction_id exists, update with latest prediction.
    """
    if not predictions:
        return
    
    # Prepare data - ensure transaction_id is a string (UUID)
    for pred in predictions:
        if 'transaction_id' in pred and not isinstance(pred['transaction_id'], str):
            pred['transaction_id'] = str(pred['transaction_id'])
    
    stmt = insert(Prediction).values(predictions)
    stmt = stmt.on_conflict_do_update(
        index_elements=['transaction_id'],
        set_={
            'category': stmt.excluded.category,
            'confidence_score': stmt.excluded.confidence_score,
            'model_version': stmt.excluded.model_version,
            'predicted_at': stmt.excluded.predicted_at
        }
    )
    
    session.execute(stmt)
    logger.info(f"Upserted {len(predictions)} predictions")
