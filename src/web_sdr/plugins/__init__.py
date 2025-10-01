"""
WebSDR Plugins - Modular processing components

This package contains plugin implementations for the v2.0 plugin supervisor system.
Each plugin processes IQ data independently and reports results via the supervisor.
"""

from .base_plugin import BasePlugin
from .spectrum_plugin import SpectrumPlugin
from .waterfall_plugin import WaterfallPlugin
from .demodulator_plugin import DemodulatorPlugin

__all__ = [
    'BasePlugin',
    'SpectrumPlugin',
    'WaterfallPlugin',
    'DemodulatorPlugin',
]
