"""Application-wide exception classes."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base exception for all application errors."""
    pass


class ConfigurationError(ApplicationError):
    """Raised when configuration is invalid."""
    pass


class DatabaseError(ApplicationError):
    """Base exception for database-related errors."""
    pass


class ConnectionPoolError(DatabaseError):
    """Raised when database connection pool has issues."""
    pass


class RepositoryError(DatabaseError):
    """Raised when repository operation fails."""
    pass


class CacheError(ApplicationError):
    """Base exception for cache-related errors."""
    pass


class CacheNotInitializedError(CacheError):
    """Raised when trying to use cache before initialization."""
    pass


class ServiceError(ApplicationError):
    """Base exception for service-level errors."""
    pass


class BroadcastError(ServiceError):
    """Raised when broadcast operation fails."""
    pass


class LotteryError(ServiceError):
    """Base exception for lottery operations."""
    pass


class InsufficientParticipantsError(LotteryError):
    """Raised when there are not enough participants for lottery."""
    pass


class ValidationError(ApplicationError):
    """Raised when data validation fails."""
    pass


class FileValidationError(ValidationError):
    """Raised when file validation fails."""
    pass


class RateLimitError(ApplicationError):
    """Raised when rate limit is exceeded."""
    pass


class AuthenticationError(ApplicationError):
    """Raised when authentication fails."""
    pass


class AuthorizationError(ApplicationError):
    """Raised when authorization fails."""
    pass

