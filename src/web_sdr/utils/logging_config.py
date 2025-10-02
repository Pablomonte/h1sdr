"""
Structured Logging Configuration for H1SDR v2.0

Provides:
- Per-component log levels
- Structured log format with context
- Optional file output
- Performance-aware logging (minimal overhead)
- Log rotation and management
"""

import logging
import logging.handlers
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import os


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter for structured logging

    Output format:
    [TIMESTAMP] [LEVEL] [COMPONENT] Message | context_key=value ...
    """

    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context

    def format(self, record: logging.LogRecord) -> str:
        # Base format
        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        level = record.levelname
        component = record.name

        # Shorten component name for readability
        if component.startswith('src.web_sdr.'):
            component = component.replace('src.web_sdr.', '')

        message = record.getMessage()

        # Build base log line
        log_line = f"[{timestamp}] [{level:8}] [{component:30}] {message}"

        # Add context if available
        if self.include_context and hasattr(record, 'context'):
            context_str = " | ".join(
                f"{k}={v}" for k, v in record.context.items()
            )
            log_line += f" | {context_str}"

        # Add exception info if present
        if record.exc_info:
            log_line += f"\n{self.formatException(record.exc_info)}"

        return log_line


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for machine-readable logs

    Useful for log aggregation and analysis
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'component': record.name,
            'message': record.getMessage(),
            'process': record.process,
            'thread': record.thread,
        }

        # Add context if available
        if hasattr(record, 'context'):
            log_data['context'] = record.context

        # Add exception if present
        if record.exc_info:
            log_data['exception'] = {
                'type': record.exc_info[0].__name__,
                'message': str(record.exc_info[1]),
                'traceback': self.formatException(record.exc_info)
            }

        return json.dumps(log_data)


class ContextAdapter(logging.LoggerAdapter):
    """
    Logger adapter that adds context to log records

    Usage:
        logger = ContextAdapter(logging.getLogger(__name__), {'request_id': '123'})
        logger.info("Processing request")
        # Output: ... | request_id=123
    """

    def process(self, msg, kwargs):
        # Merge adapter context with call-time context
        context = self.extra.copy()
        if 'context' in kwargs:
            context.update(kwargs.pop('context'))

        if context:
            # Add context to record
            if 'extra' not in kwargs:
                kwargs['extra'] = {}
            kwargs['extra']['context'] = context

        return msg, kwargs


class LoggingConfig:
    """
    Centralized logging configuration

    Features:
    - Per-component log levels
    - Console and file output
    - Log rotation
    - Structured format
    """

    DEFAULT_LEVELS = {
        # Root logger
        '': logging.INFO,

        # Core components
        'controllers.sdr_controller_v2': logging.INFO,
        'pipeline.plugin_supervisor': logging.INFO,
        'plugins': logging.INFO,

        # DSP components
        'dsp.spectrum_processor': logging.INFO,
        'dsp.demodulators': logging.INFO,
        'dsp.fft_processor': logging.INFO,

        # Web/API
        'main_v2': logging.INFO,
        'services': logging.INFO,

        # Utilities
        'utils.error_handler': logging.WARNING,
        'utils.logging_config': logging.WARNING,

        # External libraries (reduce noise)
        'rtlsdr': logging.WARNING,
        'asyncio': logging.WARNING,
        'websockets': logging.WARNING,
        'uvicorn': logging.INFO,
        'uvicorn.access': logging.WARNING,  # Reduce access log noise
    }

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        console_level: Optional[int] = None,
        file_level: Optional[int] = None,
        enable_json: bool = False,
        component_levels: Optional[Dict[str, int]] = None
    ):
        self.log_dir = log_dir or Path("logs")
        self.console_level = console_level or logging.INFO
        self.file_level = file_level or logging.DEBUG
        self.enable_json = enable_json
        self.component_levels = component_levels or self.DEFAULT_LEVELS.copy()

    def setup(self):
        """Setup logging configuration"""
        # Create log directory if needed
        if self.log_dir:
            self.log_dir.mkdir(parents=True, exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level

        # Remove existing handlers
        root_logger.handlers.clear()

        # Console handler (always enabled)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.console_level)
        console_handler.setFormatter(StructuredFormatter(include_context=True))
        root_logger.addHandler(console_handler)

        # File handler (if log_dir specified)
        if self.log_dir:
            # Main log file with rotation
            log_file = self.log_dir / "h1sdr.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5
            )
            file_handler.setLevel(self.file_level)
            file_handler.setFormatter(StructuredFormatter(include_context=True))
            root_logger.addHandler(file_handler)

            # JSON log file (optional, for analysis)
            if self.enable_json:
                json_file = self.log_dir / "h1sdr.jsonl"
                json_handler = logging.handlers.RotatingFileHandler(
                    json_file,
                    maxBytes=10 * 1024 * 1024,  # 10 MB
                    backupCount=3
                )
                json_handler.setLevel(logging.DEBUG)
                json_handler.setFormatter(JSONFormatter())
                root_logger.addHandler(json_handler)

        # Set per-component levels
        self._configure_component_levels()

        # Log startup
        logger = logging.getLogger(__name__)
        logger.info("=" * 70)
        logger.info("H1SDR v2.0 Logging Initialized")
        logger.info("=" * 70)
        logger.info(f"Console level: {logging.getLevelName(self.console_level)}")
        if self.log_dir:
            logger.info(f"Log directory: {self.log_dir.absolute()}")
            logger.info(f"File level: {logging.getLevelName(self.file_level)}")
            logger.info(f"JSON logging: {'enabled' if self.enable_json else 'disabled'}")
        logger.info(f"Component-specific levels: {len(self.component_levels)}")
        logger.info("=" * 70)

    def _configure_component_levels(self):
        """Configure per-component log levels"""
        for component, level in self.component_levels.items():
            if component:  # Skip empty string (root logger)
                # Handle both full and partial component names
                full_name = f"src.web_sdr.{component}" if not component.startswith('src.') else component
                logger = logging.getLogger(full_name)
                logger.setLevel(level)

                # Also set short name
                logger = logging.getLogger(component)
                logger.setLevel(level)

    def set_component_level(self, component: str, level: int):
        """Dynamically change component log level"""
        self.component_levels[component] = level
        self._configure_component_levels()

        logger = logging.getLogger(__name__)
        logger.info(f"Changed log level for '{component}' to {logging.getLevelName(level)}")

    def get_component_level(self, component: str) -> int:
        """Get current log level for component"""
        return self.component_levels.get(component, logging.INFO)

    def list_components(self) -> Dict[str, str]:
        """List all configured components and their log levels"""
        return {
            component: logging.getLevelName(level)
            for component, level in self.component_levels.items()
        }


# Global logging config instance
_logging_config: Optional[LoggingConfig] = None


def setup_logging(
    log_dir: Optional[Path] = None,
    console_level: Optional[str] = None,
    file_level: Optional[str] = None,
    enable_json: bool = False,
    component_levels: Optional[Dict[str, str]] = None
) -> LoggingConfig:
    """
    Setup logging for H1SDR v2.0

    Args:
        log_dir: Directory for log files (None = console only)
        console_level: Console log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        file_level: File log level
        enable_json: Enable JSON log output for analysis
        component_levels: Dict of component->level overrides

    Returns:
        LoggingConfig instance

    Usage:
        from src.web_sdr.utils.logging_config import setup_logging

        # Console only
        setup_logging()

        # With file output
        setup_logging(log_dir=Path("logs"), enable_json=True)

        # Custom levels
        setup_logging(
            console_level="DEBUG",
            component_levels={
                "controllers": "DEBUG",
                "plugins": "INFO"
            }
        )
    """
    global _logging_config

    # Convert string levels to int
    console_level_int = getattr(logging, console_level.upper()) if console_level else None
    file_level_int = getattr(logging, file_level.upper()) if file_level else None

    # Convert component levels
    component_levels_int = None
    if component_levels:
        component_levels_int = {
            comp: getattr(logging, level.upper())
            for comp, level in component_levels.items()
        }

    _logging_config = LoggingConfig(
        log_dir=log_dir,
        console_level=console_level_int,
        file_level=file_level_int,
        enable_json=enable_json,
        component_levels=component_levels_int
    )

    _logging_config.setup()
    return _logging_config


def get_logger(name: str, context: Optional[Dict[str, Any]] = None) -> logging.Logger:
    """
    Get a logger with optional context

    Args:
        name: Logger name (usually __name__)
        context: Optional context dict to include in all logs

    Returns:
        Logger instance (or ContextAdapter if context provided)

    Usage:
        # Simple logger
        logger = get_logger(__name__)
        logger.info("Processing data")

        # Logger with context
        logger = get_logger(__name__, {'plugin': 'SpectrumPlugin'})
        logger.info("Processing spectrum")  # Includes plugin=SpectrumPlugin
    """
    logger = logging.getLogger(name)

    if context:
        return ContextAdapter(logger, context)

    return logger


def get_logging_config() -> Optional[LoggingConfig]:
    """Get global logging config instance"""
    return _logging_config
