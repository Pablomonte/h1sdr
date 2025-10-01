"""
Base Plugin Interface

All WebSDR plugins must inherit from this class and implement the process() method.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict
import logging

logger = logging.getLogger(__name__)


class BasePlugin(ABC):
    """
    Abstract base class for WebSDR plugins

    Plugins are executed in parallel by the PluginSupervisor and must be
    thread-safe and non-blocking. Plugin failures are isolated and don't
    affect other plugins or the acquisition loop.
    """

    def __init__(self, name: str, enabled: bool = True):
        """
        Initialize base plugin

        Args:
            name: Unique plugin name
            enabled: Whether plugin is enabled
        """
        self.name = name
        self.enabled = enabled
        self.logger = logging.getLogger(f"h1sdr.plugins.{name}")

        # Statistics
        self.call_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_processing_time = 0.0

    @abstractmethod
    async def process(self, data: Any) -> Dict[str, Any]:
        """
        Process data and return results

        This method MUST be implemented by all plugins.
        It should be async and non-blocking.

        Args:
            data: Input data (typically complex IQ samples)

        Returns:
            Dictionary with processing results

        Raises:
            Exception: Any processing errors (caught by supervisor)
        """
        pass

    def enable(self):
        """Enable this plugin"""
        self.enabled = True
        self.logger.info(f"Plugin '{self.name}' enabled")

    def disable(self):
        """Disable this plugin"""
        self.enabled = False
        self.logger.info(f"Plugin '{self.name}' disabled")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get plugin statistics

        Returns:
            Dictionary with plugin performance stats
        """
        total_calls = self.call_count
        success_rate = (self.success_count / total_calls) if total_calls > 0 else 0.0
        avg_time = (self.total_processing_time / total_calls) if total_calls > 0 else 0.0

        return {
            'name': self.name,
            'enabled': self.enabled,
            'call_count': self.call_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'success_rate': success_rate,
            'avg_processing_time_ms': avg_time * 1000,
            'total_processing_time_s': self.total_processing_time
        }

    def reset_stats(self):
        """Reset plugin statistics"""
        self.call_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_processing_time = 0.0
        self.logger.info(f"Plugin '{self.name}' stats reset")

    def __repr__(self):
        return f"<{self.__class__.__name__}(name='{self.name}', enabled={self.enabled})>"
