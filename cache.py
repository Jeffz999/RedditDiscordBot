from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone

class SubredditCache:
    """A time-based cache for storing subreddit posts."""
    
    def __init__(self, timeout: int):
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self.timeout = timeout
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if it exists and hasn't expired."""
        if key not in self._cache:
            return None
            
        timestamp = self._timestamps[key]
        # Use timezone-aware comparison
        if datetime.now(timezone.utc) - timestamp > timedelta(seconds=self.timeout):
            del self._cache[key]
            del self._timestamps[key]
            return None
            
        return self._cache[key]
    
    def set(self, key: str, value: Any) -> None:
        """Set a value in the cache with current timestamp."""
        self._cache[key] = value
        # Store timezone-aware UTC timestamp
        self._timestamps[key] = datetime.now(timezone.utc)