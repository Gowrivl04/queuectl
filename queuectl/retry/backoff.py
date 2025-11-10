"""Retry backoff utilities."""
from datetime import datetime, timedelta
import random

from ..utils.time import utc_now


class Backoff:
    """Exponential backoff with jitter."""
    
    def __init__(
        self,
        base: float = 2.0,
        max_delay: int = 3600,  # 1 hour
        jitter_factor: float = 0.1
    ):
        self.base = base
        self.max_delay = max_delay
        self.jitter_factor = jitter_factor

    def compute_next_attempt(self, attempts: int) -> datetime:
        """Compute next attempt time using exponential backoff with jitter."""
        delay = min(self.max_delay, self.base ** attempts)
        
        # Add jitter to prevent thundering herd
        jitter = delay * self.jitter_factor
        delay += random.uniform(-jitter, jitter)
        
        return utc_now() + timedelta(seconds=max(1, delay))