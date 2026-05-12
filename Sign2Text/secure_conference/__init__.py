"""Secure conference package for Echo-Sign."""

__all__ = ["create_app", "socketio"]


def __getattr__(name):
    if name in __all__:
        from .app_factory import create_app, socketio

        return {"create_app": create_app, "socketio": socketio}[name]
    raise AttributeError(name)
