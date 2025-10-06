"""
Rate limiting utilities for API endpoints
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict
from app.utils.logger import logger


class RateLimiter:
    """In-memory rate limiter for API endpoints"""
    
    def __init__(self):
        self._requests: Dict[str, list] = defaultdict(list)
        self._cleanup_interval = timedelta(hours=1)
        self._last_cleanup = datetime.utcnow()
    
    def _cleanup_old_requests(self):
        """Remove old request records to prevent memory buildup"""
        now = datetime.utcnow()
        
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff_time = now - timedelta(days=1)
        
        for key in list(self._requests.keys()):
            self._requests[key] = [
                (ts, count) for ts, count in self._requests[key]
                if ts > cutoff_time
            ]
            
            if not self._requests[key]:
                del self._requests[key]
        
        self._last_cleanup = now
        logger.info(f"Rate limiter cleanup completed. Active keys: {len(self._requests)}")
    
    def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_minutes: int = 60
    ) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit
        
        Args:
            key: Unique identifier (user_id, IP, etc.)
            limit: Maximum requests allowed in window
            window_minutes: Time window in minutes
            
        Returns:
            Tuple of (is_allowed, current_count, time_until_reset_seconds)
        """
        self._cleanup_old_requests()
        
        now = datetime.utcnow()
        cutoff_time = now - timedelta(minutes=window_minutes)
        
        recent_requests = [
            (ts, count) for ts, count in self._requests[key]
            if ts > cutoff_time
        ]
        
        total_count = sum(count for _, count in recent_requests)
        
        is_allowed = total_count < limit
        
        time_until_reset = 0
        if recent_requests:
            oldest_request_time = recent_requests[0][0]
            reset_time = oldest_request_time + timedelta(minutes=window_minutes)
            time_until_reset = max(0, int((reset_time - now).total_seconds()))
        
        if is_allowed:
            self._requests[key].append((now, 1))
        
        return is_allowed, total_count, time_until_reset
    
    def increment(self, key: str):
        """Manually increment counter for a key"""
        now = datetime.utcnow()
        self._requests[key].append((now, 1))
    
    def reset(self, key: str):
        """Reset rate limit for a specific key"""
        if key in self._requests:
            del self._requests[key]
            logger.info(f"Rate limit reset for key: {key}")


rate_limiter = RateLimiter()


class RateLimitConfig:
    """Rate limit configurations for different operations"""
    
    NETWORK_QUERY_PER_USER_HOUR = 20  # 20 queries per hour per user
    NETWORK_QUERY_PER_IP_HOUR = 50    # 50 queries per hour per IP
    
    INTRO_REQUEST_PER_USER_DAY = 5    # 5 intro requests per day per user
    INTRO_REQUEST_PER_USER_HOUR = 3   # 3 intro requests per hour per user
    INTRO_RESPONSE_PER_USER_HOUR = 10 # 10 intro responses per hour per user
    
    GHOST_ASK_CREATE_PER_USER_DAY = 3  # 3 ghost asks per day per user
    GHOST_ASK_SEND_PER_USER_HOUR = 20  # 20 send attempts per hour per user
    
    CHAT_MESSAGE_PER_USER_HOUR = 100   # 100 messages per hour per user
    CHAT_MESSAGE_PER_USER_MINUTE = 3  # 3 messages per minute per user
    
    POST_ANALYSIS_PER_USER_HOUR = 30   # 30 analyses per hour per user
    POST_ANALYSIS_PER_USER_DAY = 100   # 100 analyses per day per user


def check_user_rate_limit(
    user_id: str,
    operation: str,
    limit: int,
    window_minutes: int = 60
) -> Tuple[bool, Optional[str]]:
    """
    Check rate limit for a user operation
    
    Args:
        user_id: User ID
        operation: Operation name (e.g., 'network_query', 'ghost_ask')
        limit: Request limit
        window_minutes: Time window in minutes
        
    Returns:
        Tuple of (is_allowed, error_message)
    """
    key = f"user:{user_id}:{operation}"
    is_allowed, current_count, time_until_reset = rate_limiter.check_rate_limit(
        key, limit, window_minutes
    )
    
    if not is_allowed:
        hours = window_minutes / 60
        time_unit = "hour" if hours == 1 else f"{int(hours)} hours"
        minutes_until_reset = time_until_reset // 60
        
        error_msg = (
            f"Rate limit exceeded. You've made {current_count} {operation} requests "
            f"in the last {time_unit}. Limit is {limit}. "
            f"Try again in {minutes_until_reset} minutes."
        )
        
        logger.warning(f"Rate limit exceeded for user {user_id} on {operation}: {current_count}/{limit}")
        return False, error_msg
    
    return True, None


def check_ip_rate_limit(
    ip_address: str,
    operation: str,
    limit: int,
    window_minutes: int = 60
) -> Tuple[bool, Optional[str]]:
    """
    Check rate limit for an IP address
    
    Args:
        ip_address: IP address
        operation: Operation name
        limit: Request limit
        window_minutes: Time window in minutes
        
    Returns:
        Tuple of (is_allowed, error_message)
    """
    key = f"ip:{ip_address}:{operation}"
    is_allowed, current_count, time_until_reset = rate_limiter.check_rate_limit(
        key, limit, window_minutes
    )
    
    if not is_allowed:
        error_msg = (
            f"Rate limit exceeded for your IP. "
            f"Try again in {time_until_reset // 60} minutes."
        )
        
        logger.warning(f"Rate limit exceeded for IP {ip_address} on {operation}: {current_count}/{limit}")
        return False, error_msg
    
    return True, None

