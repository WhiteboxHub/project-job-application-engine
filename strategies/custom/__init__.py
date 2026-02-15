"""
Custom job application strategies.

This module contains platform-specific automation strategies.
Currently supports:
- KForce
"""

__all__ = []

try:
    from .kforce import KForceStrategy
    __all__.append('KForceStrategy')
except ImportError:
    pass
