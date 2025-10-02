"""
Configuration Management for H1SDR v2.0

Provides:
- Runtime configuration updates
- Configuration validation
- Configuration persistence
- Environment-based configuration
- Configuration history/rollback
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from pydantic import ValidationError

logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validates configuration values"""

    @staticmethod
    def validate_frequency(value: float) -> bool:
        """Validate SDR frequency (RTL-SDR range: 24-1766 MHz)"""
        return 24e6 <= value <= 1766e6

    @staticmethod
    def validate_sample_rate(value: float) -> bool:
        """Validate sample rate (RTL-SDR: up to 3.2 MSPS, recommended 2.4 MSPS)"""
        valid_rates = [0.25e6, 1.024e6, 1.4e6, 1.8e6, 1.92e6, 2.048e6, 2.4e6, 2.56e6, 2.8e6, 3.2e6]
        # Allow within 1% tolerance
        return any(abs(value - rate) / rate < 0.01 for rate in valid_rates)

    @staticmethod
    def validate_gain(value: float) -> bool:
        """Validate gain (0.0 = auto, or specific values)"""
        if value == 0.0:
            return True
        # RTL-SDR typical gains (device-dependent)
        valid_gains = [0.9, 1.4, 2.7, 3.7, 7.7, 8.7, 12.5, 14.4, 15.7, 16.6,
                       19.7, 20.7, 22.9, 25.4, 28.0, 29.7, 32.8, 33.8, 36.4,
                       37.2, 38.6, 40.2, 42.1, 43.4, 43.9, 44.5, 48.0, 49.6]
        # Allow ±0.5 dB tolerance
        return any(abs(value - g) < 0.5 for g in valid_gains)

    @staticmethod
    def validate_fft_size(value: int) -> bool:
        """Validate FFT size (must be power of 2)"""
        return value > 0 and (value & (value - 1)) == 0

    @staticmethod
    def validate_port(value: int) -> bool:
        """Validate TCP port"""
        return 1024 <= value <= 65535


class ConfigChange:
    """Represents a configuration change"""

    def __init__(
        self,
        key: str,
        old_value: Any,
        new_value: Any,
        timestamp: Optional[datetime] = None,
        source: str = "unknown"
    ):
        self.key = key
        self.old_value = old_value
        self.new_value = new_value
        self.timestamp = timestamp or datetime.now()
        self.source = source

    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'old_value': str(self.old_value),
            'new_value': str(self.new_value),
            'timestamp': self.timestamp.isoformat(),
            'source': self.source
        }


class ConfigManager:
    """
    Manages runtime configuration with validation and persistence

    Features:
    - Runtime config updates with validation
    - Configuration change history
    - Persistence to file
    - Rollback support
    - Change callbacks for reactive updates
    """

    def __init__(
        self,
        config_obj: Any,
        config_file: Optional[Path] = None,
        max_history: int = 100
    ):
        self.config = config_obj
        self.config_file = config_file or Path("config_runtime.json")
        self.max_history = max_history

        # Change history
        self.history: List[ConfigChange] = []

        # Validation rules
        self.validators: Dict[str, Callable] = {
            'rtlsdr_default_freq': ConfigValidator.validate_frequency,
            'rtlsdr_sample_rate': ConfigValidator.validate_sample_rate,
            'rtlsdr_default_gain': ConfigValidator.validate_gain,
            'fft_size': ConfigValidator.validate_fft_size,
            'port': ConfigValidator.validate_port,
        }

        # Change callbacks (for reactive updates)
        self.callbacks: Dict[str, List[Callable]] = {}

        # Load persisted config if exists
        self._load_persisted_config()

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return getattr(self.config, key, default)

    def set(
        self,
        key: str,
        value: Any,
        source: str = "api",
        validate: bool = True,
        persist: bool = True
    ) -> bool:
        """
        Set configuration value with validation

        Args:
            key: Configuration key
            value: New value
            source: Source of change (api, user, system, etc.)
            validate: Whether to validate value
            persist: Whether to persist to file

        Returns:
            True if successful, False otherwise
        """
        # Check if key exists
        if not hasattr(self.config, key):
            logger.error(f"Configuration key '{key}' does not exist")
            return False

        # Get old value
        old_value = getattr(self.config, key)

        # Validate if requested
        if validate and key in self.validators:
            validator = self.validators[key]
            if not validator(value):
                logger.error(f"Validation failed for '{key}' = {value}")
                return False

        # Update value
        try:
            setattr(self.config, key, value)
        except Exception as e:
            logger.error(f"Failed to set '{key}' = {value}: {e}")
            return False

        # Record change
        change = ConfigChange(key, old_value, value, source=source)
        self.history.append(change)
        if len(self.history) > self.max_history:
            self.history.pop(0)

        logger.info(f"Config changed: {key} = {value} (was {old_value}) [source: {source}]")

        # Trigger callbacks
        if key in self.callbacks:
            for callback in self.callbacks[key]:
                try:
                    callback(key, old_value, value)
                except Exception as e:
                    logger.error(f"Callback error for '{key}': {e}")

        # Persist if requested
        if persist:
            self._persist_config()

        return True

    def bulk_set(
        self,
        updates: Dict[str, Any],
        source: str = "api",
        validate: bool = True
    ) -> Dict[str, bool]:
        """
        Update multiple configuration values

        Returns:
            Dict mapping keys to success status
        """
        results = {}
        for key, value in updates.items():
            results[key] = self.set(
                key, value,
                source=source,
                validate=validate,
                persist=False  # Persist once at end
            )

        # Persist all changes
        if any(results.values()):
            self._persist_config()

        return results

    def rollback(self, steps: int = 1) -> bool:
        """
        Rollback configuration changes

        Args:
            steps: Number of changes to roll back

        Returns:
            True if successful
        """
        if not self.history:
            logger.warning("No configuration history to rollback")
            return False

        steps = min(steps, len(self.history))

        # Apply rollbacks in reverse
        for _ in range(steps):
            change = self.history.pop()
            try:
                setattr(self.config, change.key, change.old_value)
                logger.info(f"Rolled back: {change.key} = {change.old_value}")
            except Exception as e:
                logger.error(f"Rollback failed for '{change.key}': {e}")
                return False

        # Persist rolled-back state
        self._persist_config()

        return True

    def register_callback(self, key: str, callback: Callable):
        """
        Register a callback for configuration changes

        Args:
            key: Configuration key to watch
            callback: Function(key, old_value, new_value)
        """
        if key not in self.callbacks:
            self.callbacks[key] = []
        self.callbacks[key].append(callback)
        logger.debug(f"Registered callback for '{key}'")

    def get_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get configuration change history"""
        history = self.history[-limit:] if limit else self.history
        return [change.to_dict() for change in history]

    def export_config(self, file_path: Optional[Path] = None) -> Path:
        """Export current configuration to file"""
        file_path = file_path or Path("config_export.json")

        config_dict = {}
        for key in dir(self.config):
            if not key.startswith('_') and not key.startswith('Config'):
                value = getattr(self.config, key)
                # Only export JSON-serializable values
                if isinstance(value, (str, int, float, bool, list)):
                    config_dict[key] = value

        with open(file_path, 'w') as f:
            json.dump(config_dict, f, indent=2)

        logger.info(f"Configuration exported to {file_path}")
        return file_path

    def import_config(
        self,
        file_path: Path,
        validate: bool = True,
        dry_run: bool = False
    ) -> Dict[str, bool]:
        """
        Import configuration from file

        Args:
            file_path: Path to JSON config file
            validate: Whether to validate values
            dry_run: If True, don't actually apply changes

        Returns:
            Dict mapping keys to success status
        """
        if not file_path.exists():
            logger.error(f"Config file not found: {file_path}")
            return {}

        with open(file_path, 'r') as f:
            config_dict = json.load(f)

        if dry_run:
            logger.info(f"Dry run: would import {len(config_dict)} settings")
            return {k: True for k in config_dict.keys()}

        return self.bulk_set(
            config_dict,
            source=f"import:{file_path.name}",
            validate=validate
        )

    def get_all(self) -> Dict[str, Any]:
        """Get all configuration values"""
        config_dict = {}
        for key in dir(self.config):
            if not key.startswith('_') and not key.startswith('Config'):
                value = getattr(self.config, key)
                # Only include simple types
                if isinstance(value, (str, int, float, bool, list)):
                    config_dict[key] = value
        return config_dict

    def _persist_config(self):
        """Persist current configuration to file"""
        try:
            self.export_config(self.config_file)
        except Exception as e:
            logger.error(f"Failed to persist configuration: {e}")

    def _load_persisted_config(self):
        """Load persisted configuration on startup"""
        if not self.config_file.exists():
            logger.debug("No persisted config file found")
            return

        try:
            results = self.import_config(
                self.config_file,
                validate=True,
                dry_run=False
            )
            successful = sum(1 for v in results.values() if v)
            logger.info(f"Loaded {successful}/{len(results)} settings from {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to load persisted config: {e}")


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(
    config_obj: Any = None,
    config_file: Optional[Path] = None
) -> ConfigManager:
    """
    Get or create global config manager

    Args:
        config_obj: Configuration object (only used on first call)
        config_file: Path to persistence file

    Returns:
        ConfigManager instance
    """
    global _config_manager

    if _config_manager is None:
        if config_obj is None:
            raise ValueError("config_obj required for first call")
        _config_manager = ConfigManager(config_obj, config_file)

    return _config_manager
