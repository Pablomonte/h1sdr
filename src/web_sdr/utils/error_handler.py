"""
Centralized Error Handling for H1SDR v2.0

Provides comprehensive error handling with:
- Error categorization (recoverable vs fatal)
- Automatic retry logic with exponential backoff
- Error reporting and logging
- Graceful degradation strategies
"""

import asyncio
import logging
import traceback
from typing import Optional, Callable, Any, TypeVar, Dict
from enum import Enum
from datetime import datetime
import functools

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorSeverity(Enum):
    """Error severity levels"""
    DEBUG = "debug"           # Non-critical, informational
    INFO = "info"             # Expected errors (e.g., timeout)
    WARNING = "warning"       # Recoverable errors
    ERROR = "error"           # Serious errors, degraded functionality
    CRITICAL = "critical"     # Fatal errors, system shutdown required


class ErrorCategory(Enum):
    """Error categories for handling strategies"""
    HARDWARE = "hardware"           # SDR device errors
    NETWORK = "network"             # WebSocket/HTTP errors
    PROCESSING = "processing"       # DSP/plugin processing errors
    CONFIGURATION = "configuration" # Config/validation errors
    RESOURCE = "resource"           # Memory/CPU/disk errors
    UNKNOWN = "unknown"             # Uncategorized errors


class SDRError(Exception):
    """Base exception for SDR errors"""
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.ERROR,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        recoverable: bool = True,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.category = category
        self.recoverable = recoverable
        self.original_exception = original_exception
        self.timestamp = datetime.now()

    def __str__(self):
        return f"[{self.severity.value.upper()}] {self.category.value}: {self.message}"


class HardwareError(SDRError):
    """SDR hardware-related errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.HARDWARE,
            **kwargs
        )


class NetworkError(SDRError):
    """Network/communication errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.WARNING,
            **kwargs
        )


class ProcessingError(SDRError):
    """DSP/processing errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.PROCESSING,
            severity=ErrorSeverity.WARNING,
            **kwargs
        )


class ConfigurationError(SDRError):
    """Configuration/validation errors"""
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.ERROR,
            recoverable=False,
            **kwargs
        )


class ErrorHandler:
    """
    Centralized error handler with retry logic and reporting

    Features:
    - Automatic retry with exponential backoff
    - Error categorization and severity assessment
    - Error history tracking
    - Graceful degradation strategies
    """

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.error_history: Dict[str, list] = {}

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize an exception"""
        error_type = type(error).__name__.lower()

        if any(keyword in error_type for keyword in ['usb', 'rtl', 'sdr', 'device']):
            return ErrorCategory.HARDWARE
        elif any(keyword in error_type for keyword in ['socket', 'connection', 'timeout']):
            return ErrorCategory.NETWORK
        elif any(keyword in error_type for keyword in ['fft', 'processing', 'numpy']):
            return ErrorCategory.PROCESSING
        elif any(keyword in error_type for keyword in ['config', 'validation', 'value']):
            return ErrorCategory.CONFIGURATION
        elif any(keyword in error_type for keyword in ['memory', 'resource']):
            return ErrorCategory.RESOURCE
        else:
            return ErrorCategory.UNKNOWN

    def assess_severity(self, error: Exception, category: ErrorCategory) -> ErrorSeverity:
        """Assess error severity based on type and category"""
        if isinstance(error, SDRError):
            return error.severity

        # Hardware errors are usually critical
        if category == ErrorCategory.HARDWARE:
            return ErrorSeverity.CRITICAL

        # Network errors are usually recoverable
        if category == ErrorCategory.NETWORK:
            return ErrorSeverity.WARNING

        # Processing errors depend on context
        if category == ErrorCategory.PROCESSING:
            return ErrorSeverity.WARNING

        # Configuration errors are serious
        if category == ErrorCategory.CONFIGURATION:
            return ErrorSeverity.ERROR

        return ErrorSeverity.ERROR

    def log_error(
        self,
        error: Exception,
        context: str = "",
        severity: Optional[ErrorSeverity] = None
    ):
        """Log an error with appropriate severity"""
        category = self.categorize_error(error)
        if severity is None:
            severity = self.assess_severity(error, category)

        # Build log message
        message = f"{context}: {error}" if context else str(error)

        # Add to error history
        error_key = f"{category.value}:{type(error).__name__}"
        if error_key not in self.error_history:
            self.error_history[error_key] = []

        self.error_history[error_key].append({
            'timestamp': datetime.now(),
            'message': message,
            'severity': severity.value,
            'traceback': traceback.format_exc()
        })

        # Keep only last 100 errors per category
        if len(self.error_history[error_key]) > 100:
            self.error_history[error_key] = self.error_history[error_key][-100:]

        # Log with appropriate level
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(f"[{category.value}] {message}", exc_info=True)
        elif severity == ErrorSeverity.ERROR:
            logger.error(f"[{category.value}] {message}", exc_info=True)
        elif severity == ErrorSeverity.WARNING:
            logger.warning(f"[{category.value}] {message}")
        elif severity == ErrorSeverity.INFO:
            logger.info(f"[{category.value}] {message}")
        else:
            logger.debug(f"[{category.value}] {message}")

    async def retry_async(
        self,
        func: Callable[..., Any],
        *args,
        max_retries: Optional[int] = None,
        context: str = "",
        **kwargs
    ) -> Any:
        """
        Retry an async function with exponential backoff

        Args:
            func: Async function to retry
            *args: Positional arguments for func
            max_retries: Override default max_retries
            context: Context string for logging
            **kwargs: Keyword arguments for func

        Returns:
            Result of func

        Raises:
            Last exception if all retries failed
        """
        max_retries = max_retries or self.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt < max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    self.log_error(
                        e,
                        f"{context} (attempt {attempt + 1}/{max_retries + 1})",
                        ErrorSeverity.WARNING
                    )
                    logger.info(f"Retrying in {delay:.1f}s...")
                    await asyncio.sleep(delay)
                else:
                    self.log_error(
                        e,
                        f"{context} (all {max_retries + 1} attempts failed)",
                        ErrorSeverity.ERROR
                    )

        raise last_error

    def retry_sync(
        self,
        func: Callable[..., Any],
        *args,
        max_retries: Optional[int] = None,
        context: str = "",
        **kwargs
    ) -> Any:
        """
        Retry a sync function with exponential backoff

        Similar to retry_async but for synchronous functions
        """
        import time

        max_retries = max_retries or self.max_retries
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e

                if attempt < max_retries:
                    delay = self.base_delay * (2 ** attempt)
                    self.log_error(
                        e,
                        f"{context} (attempt {attempt + 1}/{max_retries + 1})",
                        ErrorSeverity.WARNING
                    )
                    logger.info(f"Retrying in {delay:.1f}s...")
                    time.sleep(delay)
                else:
                    self.log_error(
                        e,
                        f"{context} (all {max_retries + 1} attempts failed)",
                        ErrorSeverity.ERROR
                    )

        raise last_error

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        total_errors = sum(len(errors) for errors in self.error_history.values())

        by_category = {}
        for key, errors in self.error_history.items():
            category = key.split(':')[0]
            if category not in by_category:
                by_category[category] = 0
            by_category[category] += len(errors)

        return {
            'total_errors': total_errors,
            'by_category': by_category,
            'unique_error_types': len(self.error_history)
        }


# Global error handler instance
error_handler = ErrorHandler()


def handle_errors(
    context: str = "",
    severity: Optional[ErrorSeverity] = None,
    reraise: bool = True
):
    """
    Decorator for automatic error handling

    Usage:
        @handle_errors("Processing spectrum")
        async def process_spectrum(data):
            ...
    """
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    error_handler.log_error(e, context or func.__name__, severity)
                    if reraise:
                        raise
                    return None
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    error_handler.log_error(e, context or func.__name__, severity)
                    if reraise:
                        raise
                    return None
            return sync_wrapper
    return decorator


def safe_execute(
    func: Callable[..., T],
    *args,
    default: Optional[T] = None,
    context: str = "",
    **kwargs
) -> Optional[T]:
    """
    Safely execute a function, returning default on error

    Usage:
        result = safe_execute(risky_function, arg1, arg2, default=0)
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_handler.log_error(e, context or func.__name__, ErrorSeverity.WARNING)
        return default
