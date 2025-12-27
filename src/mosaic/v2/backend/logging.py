"""Logging configuration for Mosaic backend"""

import logging
from pathlib import Path
from logging.handlers import TimedRotatingFileHandler


class ProjectOnlyFilter(logging.Filter):
    """Filter to only allow logs from mosaic.* modules"""

    def filter(self, record):
        """Filter out non-mosaic modules

        Args:
            record: Log record to filter

        Returns:
            True if the record is from mosaic.* modules, False otherwise
        """
        return record.name.startswith('mosaic.')


def setup_logging(instance_path: Path) -> None:
    """Setup logging configuration for Mosaic backend

    Creates three log files in the instance logs directory:
    - debug.log: DEBUG+ logs from mosaic.* modules only
    - info.log: INFO+ logs from all modules
    - error.log: ERROR+ logs from all modules

    Additionally, INFO+ logs from all modules are output to console (stdout).

    All logs are rotated daily at midnight, keeping 30 days of history.
    Log format includes timestamp, level, module name, file, line number, and message.

    Args:
        instance_path: Path to the Mosaic instance directory
    """
    # Create logs directory
    logs_dir = instance_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    # Define log format
    log_format = '%(asctime)s.%(msecs)03d - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels

    # Clear existing handlers to avoid duplicate logs
    root_logger.handlers.clear()

    # ==================== DEBUG Handler ====================
    # Only mosaic.* modules, DEBUG and above
    debug_handler = TimedRotatingFileHandler(
        filename=logs_dir / "debug.log",
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(formatter)
    debug_handler.addFilter(ProjectOnlyFilter())
    root_logger.addHandler(debug_handler)

    # ==================== INFO Handler ====================
    # All modules, INFO and above
    info_handler = TimedRotatingFileHandler(
        filename=logs_dir / "info.log",
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(formatter)
    root_logger.addHandler(info_handler)

    # ==================== ERROR Handler ====================
    # All modules, ERROR and above
    error_handler = TimedRotatingFileHandler(
        filename=logs_dir / "error.log",
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    # ==================== Console Handler ====================
    # All modules, INFO and above, output to console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Log initialization success
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized for instance: {instance_path}")
