import time
import functools
import random

def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Retry decorator with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts == max_attempts:
                        print(f"[Retry] [FAIL] '{func.__name__}' failed after {max_attempts} attempts: {e}")
                        raise
                    
                    # Exponential backoff with jitter
                    sleep_time = current_delay + random.uniform(0, 0.1 * current_delay)
                    print(f"[Retry] [WARN] '{func.__name__}' failed (Attempt {attempts}/{max_attempts}). Retrying in {sleep_time:.2f}s... Error: {e}")
                    time.sleep(sleep_time)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

def async_retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Async retry decorator with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            while attempts < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts == max_attempts:
                        print(f"[Retry] [FAIL] '{func.__name__}' failed after {max_attempts} attempts: {e}")
                        raise
                    
                    sleep_time = current_delay + random.uniform(0, 0.1 * current_delay)
                    print(f"[Retry] [WARN] '{func.__name__}' failed (Attempt {attempts}/{max_attempts}). Retrying in {sleep_time:.2f}s... Error: {e}")
                    import asyncio
                    await asyncio.sleep(sleep_time)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator
