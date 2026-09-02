import logging
import os
import sys
import time


def setup_logger(
    name: str = "k4_reco_val",
    log_dir: str = "logs",
    console_level: int = logging.INFO,
    file_level: int = logging.DEBUG,
) -> logging.Logger:
    """Configures and returns a Logger instance with stdout and file handlers.

    Prevents duplicate handler instantiation if invoked multiple times across imports.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if already initialized
    if logger.hasHandlers():
        return logger

    os.makedirs(log_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_filepath = os.path.join(log_dir, f"{name}_{timestamp}.log")

    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s [%(filename)s:%(lineno)d] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Stream to stdout
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Stream to log file on disk
    file_handler = logging.FileHandler(log_filepath, mode="w")
    file_handler.setLevel(file_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.debug(f"Logger '{name}' initialized. Output log path: {log_filepath}")
    return logger
