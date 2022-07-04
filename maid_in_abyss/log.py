import logging
import logging.handlers
import os
import pathlib
import sys

import coloredlogs


def setup() -> None:
    """Set up loggers."""
    format_string = "%(asctime)s | %(name)-20s | %(levelname)-8s | %(message)s"
    log_format = logging.Formatter(format_string)
    root_logger = logging.getLogger()

    # Set up file logging
    log_file = pathlib.Path("logs/maid_in_abyss.log")
    log_file.parent.mkdir(exist_ok=True)

    # File handler rotates logs every 5 MB
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * (2**20),
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)

    if "COLOREDLOGS_LEVEL_STYLES" not in os.environ:
        coloredlogs.DEFAULT_LEVEL_STYLES = {
            **coloredlogs.DEFAULT_LEVEL_STYLES,
            "critical": {"background": "red"},
            "debug": coloredlogs.DEFAULT_LEVEL_STYLES["info"],
        }

    if "COLOREDLOGS_LOG_FORMAT" not in os.environ:
        coloredlogs.DEFAULT_LOG_FORMAT = format_string

    coloredlogs.install(level=logging.DEBUG, stream=sys.stdout)

    root_logger.setLevel(logging.DEBUG)
    # Silence irrelevant loggers
    logging.getLogger("databases").setLevel(logging.WARNING)
    logging.getLogger("disnake").setLevel(logging.WARNING)
    logging.getLogger("websockets").setLevel(logging.ERROR)

    # _set_debug_loggers()

    root_logger.info("Logging initialization complete")
