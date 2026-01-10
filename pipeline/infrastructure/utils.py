
import requests
import time
import logging
from typing import Callable, Optional
from functools import wraps

logger = logging.getLogger(__name__)


def _retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0):
    """
    Decorator for exponential backoff retry logic.
    
    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds for exponential backoff
        
    Returns:
        Decorated function that returns (result, None) on success or (None, original_args) on failure
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> tuple[Optional[list[dict]], Optional[list[dict]]]:
            delay = initial_delay
            transactions = args[0] if args else None
            batch_id = args[1] if len(args) > 1 else kwargs.get('batch_id', 'unknown')
            
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"Batch {batch_id}: Retry succeeded on attempt {attempt + 1}")
                    
                    return result, None
                    
                except requests.exceptions.RequestException as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Batch {batch_id}: Attempt {attempt + 1}/{max_retries} failed - {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= 2  # Exponential backoff
                    else:
                        logger.error(
                            f"Batch {batch_id}: All {max_retries} attempts failed - {e}. "
                            f"Moving {len(transactions) if transactions else 0} transactions to failed queue."
                        )
                        return None, transactions
            
            return None, transactions
        
        return wrapper
    return decorator