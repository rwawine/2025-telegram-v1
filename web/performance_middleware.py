"""Performance middleware for Flask application."""

import time
from flask import request, g
from functools import wraps
import logging

logger = logging.getLogger(__name__)


def init_performance_middleware(app):
    """Initialize performance monitoring middleware."""
    
    @app.before_request
    def before_request():
        g.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            # Log slow requests (>1 second)
            if duration > 1.0:
                logger.warning(f"Slow request: {request.method} {request.path} took {duration:.2f}s")
            
            # Add performance headers for debugging
            response.headers['X-Response-Time'] = f"{duration:.3f}s"
        
        return response


def cache_result(timeout=300):
    """Decorator to cache function results."""
    def decorator(func):
        cache = {}
        cache_times = {}
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Check if cached result is still valid
            if cache_key in cache:
                if time.time() - cache_times[cache_key] < timeout:
                    return cache[cache_key]
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache[cache_key] = result
            cache_times[cache_key] = time.time()
            
            # Clean old cache entries (simple cleanup)
            current_time = time.time()
            expired_keys = [k for k, t in cache_times.items() if current_time - t > timeout]
            for key in expired_keys:
                cache.pop(key, None)
                cache_times.pop(key, None)
            
            return result
        return wrapper
    return decorator
