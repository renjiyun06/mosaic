"""CLI utility functions"""
import json
import os
import signal
from pathlib import Path
from typing import Optional


def get_instance_path(path: Optional[str] = None) -> Path:
    """Get instance path, default to ~/.mosaic

    Args:
        path: Custom path (relative or absolute), None for default

    Returns:
        Resolved absolute path
    """
    if path is None:
        return Path.home() / ".mosaic"
    return Path(path).resolve()


def is_initialized(instance_path: Path) -> bool:
    """Check if instance is initialized

    Args:
        instance_path: Instance directory path

    Returns:
        True if .mosaic_instance exists
    """
    return (instance_path / ".mosaic_instance").exists()


def get_instance_info(instance_path: Path) -> dict:
    """Get instance metadata

    Args:
        instance_path: Instance directory path

    Returns:
        Instance metadata dict

    Raises:
        FileNotFoundError: If not initialized
    """
    flag_file = instance_path / ".mosaic_instance"
    if not flag_file.exists():
        raise FileNotFoundError(
            f"Instance not initialized at {instance_path}"
        )

    with open(flag_file, "r") as f:
        return json.load(f)


def load_config(instance_path: Path) -> dict:
    """Load config.toml

    Args:
        instance_path: Instance directory path

    Returns:
        Configuration dict
    """
    import tomli

    config_file = instance_path / "config.toml"
    with open(config_file, "rb") as f:
        return tomli.load(f)


def get_pid_file(instance_path: Path) -> Path:
    """Get PID file path

    Args:
        instance_path: Instance directory path

    Returns:
        PID file path
    """
    return instance_path / ".mosaic.pid"


def is_running(instance_path: Path) -> Optional[int]:
    """Check if instance is running

    Args:
        instance_path: Instance directory path

    Returns:
        PID if running, None otherwise
    """
    pid_file = get_pid_file(instance_path)

    if not pid_file.exists():
        return None

    try:
        pid = int(pid_file.read_text().strip())
        # Check if process exists
        os.kill(pid, 0)  # Signal 0 just checks existence
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        # PID file invalid or process doesn't exist
        pid_file.unlink(missing_ok=True)
        return None
