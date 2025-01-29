class RedditMonitorError(Exception):
    """Base exception for Reddit Monitor errors."""
    pass

class CacheError(RedditMonitorError):
    """Raised when there's an error with the cache."""
    pass

class RedditAPIError(RedditMonitorError):
    """Raised when there's an error with Reddit API interactions."""
    pass