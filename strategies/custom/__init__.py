"""
Custom strategies package
Dynamically imports available strategies to support multiple platforms
"""

# Import available strategies with graceful fallback
__all__ = []

try:
    from .kforce import KForceStrategy
    __all__.append('KForceStrategy')
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
    from .infosys import InfosysStrategy
    __all__.append('InfosysStrategy')
except ImportError:
    pass
