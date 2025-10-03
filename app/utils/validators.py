"""
Request validation utilities with size limits and sanitization
"""
import re
from typing import Optional
from pydantic import validator


class ValidationLimits:
    """Validation limits for request fields"""
    
    MESSAGE_MIN_LENGTH = 1
    MESSAGE_MAX_LENGTH = 500
    QUERY_MIN_LENGTH = 3
    QUERY_MAX_LENGTH = 200
    CAPTION_MAX_LENGTH = 1000
    NAME_MAX_LENGTH = 100
    USERNAME_MAX_LENGTH = 50
    
    MAX_CONVERSATION_HISTORY = 50
    MAX_MUTUALS = 100
    MAX_RESULTS = 50
    
    UUID_PATTERN = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    
    MAX_URL_LENGTH = 2048
    ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']


def validate_uuid(value: str, field_name: str = "ID") -> str:
    """Validate UUID format"""
    if not value:
        raise ValueError(f"{field_name} is required")
    
    if not re.match(ValidationLimits.UUID_PATTERN, value.lower()):
        raise ValueError(f"Invalid {field_name} format. Must be a valid UUID")
    
    return value.lower()


def validate_message(value: str, min_length: int = None, max_length: int = None) -> str:
    """Validate message content"""
    if not value or not value.strip():
        raise ValueError("Message cannot be empty")
    
    min_len = min_length or ValidationLimits.MESSAGE_MIN_LENGTH
    max_len = max_length or ValidationLimits.MESSAGE_MAX_LENGTH
    
    value = value.strip()
    
    if len(value) < min_len:
        raise ValueError(f"Message must be at least {min_len} characters")
    
    if len(value) > max_len:
        raise ValueError(f"Message must be no more than {max_len} characters")
    
    return value


def validate_query(value: str) -> str:
    """Validate search query"""
    if not value or not value.strip():
        raise ValueError("Query cannot be empty")
    
    value = value.strip()
    
    if len(value) < ValidationLimits.QUERY_MIN_LENGTH:
        raise ValueError(f"Query must be at least {ValidationLimits.QUERY_MIN_LENGTH} characters")
    
    if len(value) > ValidationLimits.QUERY_MAX_LENGTH:
        raise ValueError(f"Query must be no more than {ValidationLimits.QUERY_MAX_LENGTH} characters")
    
    return value


def validate_image_url(value: Optional[str]) -> Optional[str]:
    """Validate image URL"""
    if not value:
        return None
    
    value = value.strip()
    
    if len(value) > ValidationLimits.MAX_URL_LENGTH:
        raise ValueError(f"Image URL is too long (max {ValidationLimits.MAX_URL_LENGTH} characters)")
    
    if not value.startswith(('http://', 'https://')):
        raise ValueError("Image URL must start with http:// or https://")
    
    has_valid_ext = any(value.lower().endswith(ext) for ext in ValidationLimits.ALLOWED_IMAGE_EXTENSIONS)
    if not has_valid_ext and '?' not in value:  # Allow query params
        pass
    
    return value


def validate_limit(value: int, max_value: int = None) -> int:
    """Validate result limit"""
    max_val = max_value or ValidationLimits.MAX_RESULTS
    
    if value < 1:
        raise ValueError("Limit must be at least 1")
    
    if value > max_val:
        raise ValueError(f"Limit cannot exceed {max_val}")
    
    return value


def sanitize_text(text: str) -> str:
    """
    Sanitize text input by removing/escaping dangerous characters
    """
    if not text:
        return text
    
    text = text.replace('\x00', '')
    
    text = ''.join(char for char in text if char == '\n' or char == '\t' or not char.iscntrl())
    
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()


def validate_username(value: Optional[str]) -> Optional[str]:
    """Validate username format"""
    if not value:
        return None
    
    value = value.strip()
    
    if len(value) > ValidationLimits.USERNAME_MAX_LENGTH:
        raise ValueError(f"Username must be no more than {ValidationLimits.USERNAME_MAX_LENGTH} characters")
    
    if not re.match(r'^[a-zA-Z0-9_-]+$', value):
        raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
    
    return value


def validate_name(value: Optional[str]) -> Optional[str]:
    """Validate display name"""
    if not value:
        return None
    
    value = value.strip()
    
    if len(value) > ValidationLimits.NAME_MAX_LENGTH:
        raise ValueError(f"Name must be no more than {ValidationLimits.NAME_MAX_LENGTH} characters")
    
    return sanitize_text(value)


class RequestValidator:
    """Helper class for common validation patterns"""
    
    @staticmethod
    def validate_pagination(limit: Optional[int], offset: Optional[int] = 0):
        """Validate pagination parameters"""
        if limit is not None:
            if limit < 1:
                raise ValueError("Limit must be at least 1")
            if limit > ValidationLimits.MAX_RESULTS:
                raise ValueError(f"Limit cannot exceed {ValidationLimits.MAX_RESULTS}")
        
        if offset is not None and offset < 0:
            raise ValueError("Offset cannot be negative")
        
        return limit or 20, offset or 0
    
    @staticmethod
    def validate_boolean_flag(value: any, default: bool = False) -> bool:
        """Validate and normalize boolean flags"""
        if value is None:
            return default
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        
        if isinstance(value, int):
            return value != 0
        
        return default

