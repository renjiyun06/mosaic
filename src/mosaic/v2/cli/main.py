"""Mosaic CLI entry point"""

import click
from rich.console import Console

from .command.init import init
from .command.start import start
from .command.stop import stop

console = Console()


@click.group(
    name="mosaic",
    help="Mosaic - Event-driven distributed multi-agent system framework",
)
def main():
    """Main CLI entry point"""
    pass


# Register commands
main.add_command(init)
main.add_command(start)
main.add_command(stop)


if __name__ == "__main__":
    main()
