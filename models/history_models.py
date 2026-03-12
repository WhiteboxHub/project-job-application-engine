"""
History Models — minimal stub.
Application and Metric are referenced in strategy files and models/__init__.py.
"""


class Application:
    """Minimal stub for backward compatibility with strategy files."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class Metric:
    """Minimal stub for backward compatibility with models/__init__.py."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
