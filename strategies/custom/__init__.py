"""
Custom strategies package
"""

from strategies.custom.experis import ExperisStrategy
from strategies.custom.kforce import KForceStrategy
from strategies.custom.lancesoft import LanceSoftStrategy
from strategies.custom.wipro import WiproStrategy

__all__ = [
    "LanceSoftStrategy",
    "WiproStrategy",
    "KForceStrategy",
    "ExperisStrategy",
]
