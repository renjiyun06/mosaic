"""Stop command implementation"""
import os
import signal
import sys
import time
from ..utils import (
    get_instance_path,
    is_initialized,
    is_running,
    get_pid_file,
)


def stop_command(path: str = None, force: bool = False):
    """Stop Mosaic backend server

    Args:
        path: Instance directory path (default: ~/.mosaic)
        force: Force kill if graceful shutdown fails
    """

    # 1. Get instance path
    instance_path = get_instance_path(path)

    # 2. Check if initialized
    if not is_initialized(instance_path):
        print(
            f"Error: Not initialized at {instance_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 3. Check if running
    pid = is_running(instance_path)
    if not pid:
        print(f"Instance not running at {instance_path}")
        return

    # 4. Stop process
    print(f"Stopping Mosaic (PID: {pid})...")

    try:
        # Try graceful shutdown first (SIGTERM)
        os.kill(pid, signal.SIGTERM)

        # Wait up to 10 seconds for graceful shutdown
        for _ in range(10):
            time.sleep(1)
            try:
                os.kill(pid, 0)  # Check if still exists
            except ProcessLookupError:
                # Process stopped
                break
        else:
            # Still running after 10 seconds
            if force:
                print("Graceful shutdown failed, force killing...")
                os.kill(pid, signal.SIGKILL)
            else:
                print(
                    "Warning: Process still running after 10s",
                    file=sys.stderr,
                )
                print(
                    "Use --force to force kill",
                    file=sys.stderr,
                )
                sys.exit(1)

        # Clean up PID file
        get_pid_file(instance_path).unlink(missing_ok=True)

        print("✓ Server stopped")

    except ProcessLookupError:
        print("Process already stopped")
        get_pid_file(instance_path).unlink(missing_ok=True)
    except PermissionError:
        print(
            f"Error: Permission denied to stop process {pid}",
            file=sys.stderr,
        )
        sys.exit(1)
