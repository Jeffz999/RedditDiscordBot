from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any

class SubredditCache:
    """A time-based cache for storing subreddit posts."""
    
    def __init__(self, timeout: int):
        """Initialize cache with timeout in seconds."""
        self._cache: Dict[str, Any] = {}
        self._timestamps: Dict[str, datetime] = {}
        self.timeout = timeout

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache if it exists and hasn't expired.
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            Cached value if exists and fresh, None otherwise
        """
        if key not in self._cache:
            return None
            
        timestamp = self._timestamps[key]
        
        # Use timezone-aware comparison
        if datetime.now(timezone.utc) - timestamp > timedelta(seconds=self.timeout):
            # Clean up expired entry
            self._remove(key)
            return None
            
        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """
        Set a value in the cache with current timestamp.
        
        Args:
            key: Cache key to set
            value: Value to cache
        """
        self._cache[key] = value
        # Store timezone-aware UTC timestamp
        self._timestamps[key] = datetime.now(timezone.utc)
        
    def _remove(self, key: str) -> None:
        """
        Remove an entry from both cache and timestamps.
        
        Args:
            key: Cache key to remove
        """
        del self._cache[key]
        del self._timestamps[key]
        
    def clear(self) -> None:
        """Clear all entries from the cache."""
        self._cache.clear()
        self._timestamps.clear()