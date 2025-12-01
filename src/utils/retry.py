"""
Retry logic with exponential backoff and jitter
"""
import time
import random
import logging
from typing import Callable, Type, Tuple, Any
from functools import wraps

from src.utils.exceptions import AgentException, LLMAPIError, TimeoutError

logger = logging.getLogger(__name__)


def exponential_backoff_with_jitter(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 32.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retriable_exceptions: Tuple[Type[Exception], ...] = (LLMAPIError, TimeoutError, ConnectionError)
):
    """
    Decorator for exponential backoff retry with jitter
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds (default: 1s)
        max_delay: Maximum delay cap in seconds (default: 32s)
        exponential_base: Base for exponential calculation (default: 2)
        jitter: Add randomness to prevent thundering herd (default: True)
        retriable_exceptions: Tuple of exceptions that should trigger retry
    
    Retry delays (without jitter):
    - Attempt 1: 1s
    - Attempt 2: 2s
    - Attempt 3: 4s
    - Attempt 4: 8s
    - etc.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Log success if this was a retry
                    if attempt > 0:
                        logger.info(
                            f"{func.__name__} succeeded on attempt {attempt + 1}/{max_retries + 1}"
                        )
                    
                    return result
                    
                except retriable_exceptions as e:
                    last_exception = e
                    
                    # Don't retry if we've exhausted attempts
                    if attempt >= max_retries:
                        logger.error(
                            f"{func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        break
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter (randomness) to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())  # 50-150% of delay
                    
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    time.sleep(delay)
                    
                except Exception as e:
                    # Non-retriable exception - fail immediately
                    logger.error(f"{func.__name__} failed with non-retriable error: {e}")
                    raise
            
            # All retries exhausted
            raise last_exception
        
        return wrapper
    return decorator


def retry_with_fallback(
    fallback_func: Callable = None,
    max_retries: int = 2,
    base_delay: float = 1.0
):
    """
    Decorator that retries on failure, then calls fallback if all retries fail
    
    Args:
        fallback_func: Function to call if all retries fail
        max_retries: Number of retry attempts
        base_delay: Initial delay between retries
    
    Example:
        @retry_with_fallback(fallback_func=get_default_insights, max_retries=2)
        def generate_insights(...):
            # Try to generate insights with LLM
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        @exponential_backoff_with_jitter(max_retries=max_retries, base_delay=base_delay)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if fallback_func:
                    logger.warning(
                        f"{func.__name__} failed, using fallback: {fallback_func.__name__}"
                    )
                    return fallback_func(*args, **kwargs)
                else:
                    raise
        
        return wrapper
    return decorator
