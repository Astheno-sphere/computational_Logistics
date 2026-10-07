from settings import settings
settings.force_reload()

from handle.application import app

__all__ = ["app"]
