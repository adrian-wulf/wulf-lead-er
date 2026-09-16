"""Web GUI module for wulf-web-leader."""

__all__ = ["app"]


def __getattr__(name: str):
    if name == "app":
        from wulf_web_leader.web.app import app
        return app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
