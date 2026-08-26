"""Centralized logging configuration for the key4hep reconstruction validation framework.

All Python modules use :func:`setup_logger` to obtain a named logger that writes:

- **Console** (stdout) at ``INFO`` level — clean, human-readable messages.
- **Log file** at ``DEBUG`` level — full detail for post-run debugging.

The log directory defaults to the ``K4_LOG_DIR`` environment variable if set,
otherwise falls back to ``logs/`` relative to the current working directory.
This allows pipeline stages to redirect logs to a persistent location (e.g.
``$WORKAREA/logs/``) without any code changes.

Example::

    export K4_LOG_DIR="$WORKAREA/logs"
    python3 plotting.py ...     # writes logs/plotting_20240101_120000.log
"""

import logging
import os
import sys
import time

# Default log directory; overridable via environment variable
_DEFAULT_LOG_DIR = os.environ.get("K4_LOG_DIR", "logs")


def setup_logger(
    name: str = "k4_reco_val",
    log_dir: str = _DEFAULT_LOG_DIR,
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """Configures and returns a named Logger with console and file handlers.

    Calling this multiple times with the same ``name`` is safe — handlers
    are only added once.

    Args:
        name: Logger name (used as the log filename prefix).
        log_dir: Directory for log files. Defaults to :data:`_DEFAULT_LOG_DIR`.
        console_level: Minimum level for console output (default: INFO).
        file_level: Minimum level for log file output (default: DEBUG).

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.hasHandlers():
        return logger

    os.makedirs(log_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_filepath = os.path.join(log_dir, f"{name}_{timestamp}.log")

    console_formatter = logging.Formatter(
        fmt="%(levelname)-8s %(message)s",
    )
    file_formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)-8s [%(name)s:%(filename)s:%(lineno)d] %(message)s",
        datefmt="%H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_filepath, mode="w")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    logger.debug(f"Logger '{name}' initialized. Log file: {log_filepath}")
    return logger
