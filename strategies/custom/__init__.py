"""
Custom job application strategies.

<<<<<<< HEAD
Supports 3 active job sites:
- LanceSoft
- Insight Global
- Infosys
=======
This module contains platform-specific automation strategies.
Currently supports:
- KForce
- Capgemini
>>>>>>> bavish_dev
"""

__all__ = []

try:
<<<<<<< HEAD
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
=======
    from .kforce import KForceStrategy
    __all__.append('KForceStrategy')
except ImportError:
    pass

try:
    from .capgemini import CapgeminiStrategy
    __all__.append('CapgeminiStrategy')
except ImportError:
    pass
>>>>>>> bavish_dev
