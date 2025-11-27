"""
API layer for FootProp AI Backend.

Contains FastAPI routes and authentication.
"""

# Lazy import to avoid requiring FastAPI when importing other modules
def __getattr__(name):
    if name == "app":
        from .main import app
        return app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ["app"]

