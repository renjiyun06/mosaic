import asyncio
import click
from click import option
from rich.console import Console

from mosaic.core.client import AdminClient
from mosaic.cli.base import CustomGroup, CustomCommand

console = Console()
admin_client = AdminClient()

@click.group(name="event", cls=CustomGroup)
def event():
    """manage the mosaic events"""