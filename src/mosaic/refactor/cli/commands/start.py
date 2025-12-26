"""Start command implementation"""
import os
import sys
import subprocess
from ..utils import (
    get_instance_path,
    is_initialized,
    load_config,
    is_running,
    get_pid_file,
)


def start_command(path: str = None, daemon: bool = False):
    """Start Mosaic backend server

    Args:
        path: Instance directory path (default: ~/.mosaic)
        daemon: Run in background
    """

    # 1. Get instance path
    instance_path = get_instance_path(path)

    # 2. Check if initialized
    if not is_initialized(instance_path):
        print(
            f"Error: Not initialized at {instance_path}",
            file=sys.stderr,
        )
        print(
            f"Run: mosaic init {path if path else ''}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 3. Check if already running
    pid = is_running(instance_path)
    if pid:
        print(
            f"Error: Instance already running (PID: {pid})",
            file=sys.stderr,
        )
        print(f"Location: {instance_path}", file=sys.stderr)
        sys.exit(1)

    # 4. Load config
    config = load_config(instance_path)

    # 5. Set instance path so config.py can find config.toml
    os.environ["MOSAIC_INSTANCE_PATH"] = str(instance_path)

    # 6. Get server settings from config
    host = config.get("server_host", "0.0.0.0")
    port = config.get("server_port", 8000)

    print(f"Starting Mosaic from {instance_path}")
    print(f"Server: http://{host}:{port}")
    print(f"Docs: http://{host}:{port}/docs")
    print("")

    if daemon:
        # Run in background
        print("Starting in daemon mode...")

        # Start process in background
        log_file = instance_path / "logs" / "backend.log"
        with open(log_file, "a") as f:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "mosaic.refactor.backend.main:app",
                    "--host",
                    host,
                    "--port",
                    str(port),
                ],
                stdout=f,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )

        # Save PID
        pid_file = get_pid_file(instance_path)
        pid_file.write_text(str(process.pid))

        print(f"✓ Server started (PID: {process.pid})")
        print(f"Logs: {log_file}")

    else:
        # Run in foreground
        import uvicorn

        # Save PID (current process)
        pid_file = get_pid_file(instance_path)
        pid_file.write_text(str(os.getpid()))

        try:
            uvicorn.run(
                "mosaic.refactor.backend.main:app",
                host=host,
                port=port,
                reload=config.get("debug", False),
            )
        finally:
            # Clean up PID file
            pid_file.unlink(missing_ok=True)
