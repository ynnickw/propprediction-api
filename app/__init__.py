"""
FootProp AI Backend Application

Main application package for AI-driven sports betting predictions.
"""

# Lazy import to avoid requiring FastAPI when importing other modules
def __getattr__(name):
    if name == "app":
        from .api.main import app
        return app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

__all__ = ["app"]

