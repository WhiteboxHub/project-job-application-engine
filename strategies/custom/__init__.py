"""
Custom job application strategies.

This module contains platform-specific automation strategies.
Currently supports:
- KForce (Custom Guest Flow)
- Capgemini (SAP SuccessFactors)
- Insight Global (Legacy Portal)
- LanceSoft (JobDiva Portal)
- Wipro (Custom Talent Portal)
"""

__all__ = []

try:
    from .kforce import KForceStrategy
    __all__.append('KForceStrategy')
except ImportError:
    pass

try:
    from .capgemini import CapgeminiStrategy
    __all__.append('CapgeminiStrategy')
except ImportError:
    pass

try:
    from .insight_global import InsightGlobalStrategy
    __all__.append('InsightGlobalStrategy')
except ImportError:
    pass

try:
    from .lancesoft import LanceSoftStrategy
    __all__.append('LanceSoftStrategy')
except ImportError:
    pass

try:
    from .wipro import WiproStrategy
    __all__.append('WiproStrategy')
except ImportError:
    pass
