"""
Create logger named agentsociety as singleton for ray.
"""

import logging

__all__ = ["get_logger", "set_logger_level"]


def get_logger():
    logger = logging.getLogger("agentsociety")
    # check if there is already a handler, avoid duplicate output
    if not logger.hasHandlers():
        logger.setLevel(logging.INFO)
        # set propagate to False, avoid duplicate output
        logger.propagate = False
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def set_logger_level(level: str):
    """Set the logger level"""
    get_logger().setLevel(level)
