"""
Custom strategies package
"""

from strategies.custom.insight_global import InsightGlobalStrategy
from strategies.custom.kforce import KForceStrategy
from strategies.custom.lancesoft import LanceSoftStrategy
from strategies.custom.wipro import WiproStrategy

__all__ = [
    "InsightGlobalStrategy",
    "LanceSoftStrategy",
    "WiproStrategy",
    "KForceStrategy",
]
