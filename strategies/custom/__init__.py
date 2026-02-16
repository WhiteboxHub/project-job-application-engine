"""
Custom job application strategies.

This module contains platform-specific automation strategies.
Currently supports:
- KForce
- Capgemini
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
