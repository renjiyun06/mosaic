"""CLI utility functions"""

import json
from pathlib import Path


def get_instance_path(path: str | None = None) -> Path:
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


def is_running(instance_path: Path) -> bool:
    """Check if instance is running by checking PID file existence

    Args:
        instance_path: Instance directory path

    Returns:
        True if PID file exists, False otherwise
    """
    pid_file = get_pid_file(instance_path)
    return pid_file.exists()
