"""ASGI entry point: uvicorn salesforge.main:app"""

import logging

from .api import create_app
from .settings import get_settings

logging.basicConfig(level=get_settings().log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = create_app()
