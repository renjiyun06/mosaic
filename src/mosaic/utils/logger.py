import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

def setup_logging() -> None:
    log_dir = Path.home() / ".mosaic" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    debug_handler = RotatingFileHandler(
        log_dir / "debug.log",
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    root_logger.addHandler(debug_handler)

    info_handler = RotatingFileHandler(
        log_dir / "info.log",
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    root_logger.addHandler(info_handler)

    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

setup_logging()