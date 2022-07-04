import logging
import logging.handlers
import os
import sys
import pathlib
# from pathlib import Path

import coloredlogs


# def get_logger(*args, **kwargs) -> logging.Logger:
#     """Stub method for logging.getLogger."""
#     return logging.getLogger(*args, **kwargs)


# def _set_debug_loggers() -> None:
#     """
#     Set loggers to the DEBUG level according to the value from the DEBUG_LOGGERS env var.

#     When the env var is a list of logger names delimited by a comma,
#     each of the listed loggers will be set to the debug level.

#     If this list is prefixed with a "!", all of the loggers except the listed ones will be set to the debug level.

#     Otherwise if the env var begins with a "*",
#     the root logger is set to the debug level and the contents are parsed like the above.
#     """
#     level_filter = os.environ.get("DEBUG_LOGGERS")
#     if level_filter:
#         if level_filter.startswith("*"):
#             logging.getLogger().setLevel(logging.DEBUG)
#             level_filter = level_filter.strip("*")

#         if level_filter.startswith("!"):
#             logging.getLogger().setLevel(logging.DEBUG)
#             for logger_name in level_filter.strip("!, ").split(","):
#                 logging.getLogger(logger_name.strip()).setLevel(logging.DEBUG)

#         else:
#             for logger_name in level_filter.strip().split(","):
#                 logging.getLogger(logger_name.strip()).setLevel(logging.DEBUG)


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