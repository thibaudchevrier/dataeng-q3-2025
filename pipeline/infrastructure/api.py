
import requests
import logging
from .utils import _retry_with_backoff
import os

logger = logging.getLogger(__name__)


@_retry_with_backoff(max_retries=int(os.getenv('MAX_RETRIES', '3')), initial_delay=1.0)
def predict_batch(transactions: list[dict], batch_id: int) -> list[dict]:
    """
    Send a batch of transactions to the ML API for prediction.
    
    Args:
        transactions: List of transaction dictionaries
        batch_id: Batch identifier for logging
        
    Returns:
        List of predictions from the API
    """
    response = requests.post(
        "http://localhost:8000/predict",
        json=transactions,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    predictions = response.json()
    logger.debug(f"Batch {batch_id}: Successfully processed {len(predictions)} transactions")
    return predictions