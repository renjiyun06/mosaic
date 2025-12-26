"""Init command implementation"""
import json
import secrets
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from ..utils import get_instance_path, is_initialized


def init_command(path: str = None):
    """Initialize a new Mosaic instance

    Args:
        path: Instance directory path (default: ~/.mosaic)
    """

    # 1. Get instance path
    instance_path = get_instance_path(path)

    # 2. Check if already initialized
    if is_initialized(instance_path):
        print(
            f"Error: Already initialized at {instance_path}",
            file=sys.stderr,
        )
        print(
            f"To reinitialize, remove: "
            f"{instance_path / '.mosaic_instance'}",
            file=sys.stderr,
        )
        sys.exit(1)

    # 3. Create directory structure
    print(f"Initializing Mosaic instance at {instance_path}")

    instance_path.mkdir(parents=True, exist_ok=True)
    (instance_path / "data").mkdir(exist_ok=True)
    (instance_path / "logs").mkdir(exist_ok=True)
    (instance_path / "users").mkdir(exist_ok=True)

    # 4. Generate config.toml
    print("Generating configuration...")

    secret_key = secrets.token_urlsafe(32)
    instance_id = str(uuid4())

    config_content = f"""# Mosaic Instance Configuration
# Generated at: {datetime.utcnow().isoformat()}
# Instance ID: {instance_id}

# Application configuration
app_name = "Mosaic"
app_version = "0.1.0"
debug = false

# Database configuration
database_url = "sqlite:///{instance_path}/data/mosaic.db"

# Authentication configuration
# Auto-generated secret key for JWT (DO NOT SHARE)
secret_key = "{secret_key}"
algorithm = "HS256"
access_token_expire_minutes = 1440  # 24 hours

# Email service configuration
# Leave smtp_user and smtp_password empty for development mode
# (verification codes will be printed to console)
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_user = ""
smtp_password = ""
smtp_from = "noreply@mosaic.dev"
smtp_from_name = "Mosaic"

# Verification code configuration
verification_code_expire_minutes = 10
verification_code_length = 6

# CORS configuration (array)
cors_origins = ["http://localhost:3000"]

# Server configuration
server_host = "0.0.0.0"
server_port = 8000

# Logging configuration
logging_backend_log = "{instance_path}/logs/backend.log"
logging_runtime_log = "{instance_path}/logs/runtime.log"
logging_level = "INFO"  # DEBUG, INFO, WARNING, ERROR

# Runtime configuration
runtime_max_threads = 4  # Number of threads for running mosaic instances
runtime_zmq_pull_port = 5555  # ZMQ PULL port for receiving messages
runtime_zmq_pub_port = 5556  # ZMQ PUB port for publishing messages
"""

    config_file = instance_path / "config.toml"
    config_file.write_text(config_content)

    # 5. Create flag file
    flag_data = {
        "version": "0.1.0",
        "instance_id": instance_id,
        "initialized_at": datetime.utcnow().isoformat(),
        "instance_path": str(instance_path),
    }

    flag_file = instance_path / ".mosaic_instance"
    with open(flag_file, "w") as f:
        json.dump(flag_data, f, indent=2)

    # 6. Initialize database
    print("Initializing database...")

    # Create database tables directly without using settings
    from sqlmodel import create_engine, SQLModel
    from ...backend.models import User, EmailVerification  # Import models

    # Create engine with explicit database URL
    db_url = f"sqlite:///{instance_path}/data/mosaic.db"
    engine = create_engine(db_url, echo=False)

    # Create all tables
    SQLModel.metadata.create_all(engine)

    # 7. Success message
    print("")
    print("✓ Mosaic instance initialized successfully!")
    print("")
    print(f"Location: {instance_path}")
    print("")
    print("Next steps:")
    print(f"  1. (Optional) Edit {instance_path}/config.toml")
    print("     - Configure SMTP for email verification")
    print("     - Adjust CORS origins for your frontend")
    print("")
    print("  2. Start the backend:")
    if path:
        print(f"     mosaic start {path}")
    else:
        print("     mosaic start")
    print("")
    print("  3. Access API documentation:")
    print(f"     http://localhost:8000/docs")
    print("")
    print(f"Configuration: {config_file}")
    print(f"Database: {instance_path}/data/mosaic.db")
    print(f"Logs: {instance_path}/logs/")
