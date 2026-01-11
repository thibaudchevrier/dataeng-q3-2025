
import requests
import logging
from .utils import _retry_with_backoff
import os

logger = logging.getLogger(__name__)


@_retry_with_backoff(max_retries=int(os.getenv('MAX_RETRIES', '3')), initial_delay=1.0)
def predict_batch(transactions: list[dict], ml_api_url: str, batch_id: int = 0) -> tuple[list[dict], list[dict]]:
    """
    Send a batch of transactions to the ML API for prediction.
    
    Args:
        transactions: List of transaction dictionaries
        ml_api_url: ML API URL (e.g., 'http://ml-api:8000')
        batch_id: Batch identifier for logging
        
    Returns:
        List of predictions from the API
    """
    response = requests.post(
        f"{ml_api_url}/predict",
        json=transactions,
        headers={"Content-Type": "application/json"},
        timeout=30
    )
    response.raise_for_status()
    predictions = response.json()
    logger.debug(f"Batch {batch_id}: Successfully processed {len(predictions)} transactions")
    return transactions, predictions