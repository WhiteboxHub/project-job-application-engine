"""
Custom job application strategies.

Supports 5 job sites:
- LanceSoft
- Insight Global
- Infosys
- Capgemini
- KForce
"""

__all__ = []

# Existing strategies from merge_three_sites
try:
    from .lancesoft import LanceSoftStrategy
    __all__.append('LanceSoftStrategy')
except ImportError as e:
    print(f"Warning: Could not import LanceSoftStrategy: {e}")

try:
    from .insight_global import InsightGlobalStrategy
    __all__.append('InsightGlobalStrategy')
except ImportError as e:
    print(f"Warning: Could not import InsightGlobalStrategy: {e}")

try:
    from .infosys import InfosysStrategy
    __all__.append('InfosysStrategy')
except ImportError as e:
    print(f"Warning: Could not import InfosysStrategy: {e}")

# New strategies from bavish_dev
try:
    from .capgemini import CapgeminiStrategy
    __all__.append('CapgeminiStrategy')
except ImportError as e:
    print(f"Warning: Could not import CapgeminiStrategy: {e}")

try:
    from .kforce import KForceStrategy
    __all__.append('KForceStrategy')
except ImportError as e:
    print(f"Warning: Could not import KForceStrategy: {e}")
