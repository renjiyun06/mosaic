"""Init command implementation"""

import json
from datetime import datetime

import click
from rich.console import Console

from ..util import get_instance_path, is_initialized

console = Console()


@click.command(name="init", help="Initialize a new Mosaic instance")
@click.argument(
    "path",
    type=click.Path(),
    required=False,
)
def init(path: str = None):
    """Initialize a new Mosaic instance

    Args:
        path: Instance directory path (default: ~/.mosaic)
    """
    # Get instance path
    instance_path = get_instance_path(path)

    # Check if already initialized
    if is_initialized(instance_path):
        console.print(
            f"[red]Error: Already initialized at {instance_path}[/red]"
        )
        raise click.Abort()

    # Check if directory exists and is not empty
    if instance_path.exists():
        # Check if directory is not empty
        if any(instance_path.iterdir()):
            console.print(
                f"[red]Error: Directory is not empty: {instance_path}[/red]"
            )
            raise click.Abort()

    # 1. Create directory structure
    console.print(f"Initializing Mosaic instance at {instance_path}")
    console.print("")

    instance_path.mkdir(parents=True, exist_ok=True)
    (instance_path / "data").mkdir(exist_ok=True)
    (instance_path / "logs").mkdir(exist_ok=True)
    (instance_path / "users").mkdir(exist_ok=True)

    # 2. Generate config.toml with default settings
    console.print("Generating configuration...")

    config_content = """[server]
host = "0.0.0.0"
port = 18888

[cors]
allow_origins = ["http://localhost:3000", "http://localhost:3001"]
allow_credentials = true
allow_methods = ["*"]
allow_headers = ["*"]

[email]
smtp_host = "smtp.example.com"
smtp_port = 465
use_ssl = true
sender_email = "noreply@example.com"
sender_password = "your-auth-code-here"
sender_name = "Mosaic System"
"""

    config_file = instance_path / "config.toml"
    config_file.write_text(config_content)

    # 3. Create .mosaic_instance flag file
    flag_data = {
        "initialized_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "instance_path": str(instance_path),
        "database_path": str(instance_path / "data" / "mosaic.db"),
    }

    flag_file = instance_path / ".mosaic_instance"
    with open(flag_file, "w") as f:
        json.dump(flag_data, f, indent=2)

    # 4. Initialize database
    console.print("Initializing database...")

    from sqlmodel import create_engine, SQLModel

    # Import all models to register them
    from ...backend.model import (
        User,
        EmailVerification,
        Mosaic,
        Node,
        Connection,
        Subscription,
        Session,
        SessionRouting,
        Event,
        Message,
    )

    # Create database engine
    db_path = instance_path / "data" / "mosaic.db"
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, echo=False)

    # Create all tables
    SQLModel.metadata.create_all(engine)

    # 5. Display success message
    console.print("")
    console.print("[green]✓ Mosaic instance initialized successfully![/green]")
    console.print("")
    console.print(f"Location: {instance_path}")
    console.print("")
    console.print("Next steps:")
    console.print("  1. (Optional) Edit configuration:")
    console.print(f"     {config_file}")
    console.print("")
    console.print("  2. Start the backend server:")
    if path:
        console.print(f"     mosaic start {path}")
    else:
        console.print("     mosaic start")
    console.print("")
    console.print("Database: {}/data/mosaic.db".format(instance_path))
    console.print("Logs: {}/logs/".format(instance_path))
