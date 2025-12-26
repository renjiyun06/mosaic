"""Mosaic CLI entry point"""
import sys
import argparse
from .commands.init import init_command
from .commands.start import start_command
from .commands.stop import stop_command


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        prog="mosaic",
        description=(
            "Mosaic - Event-driven distributed multi-agent "
            "system framework"
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        help="Available commands",
    )

    # Init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new Mosaic instance",
    )
    init_parser.add_argument(
        "path",
        nargs="?",
        help="Instance directory path (default: ~/.mosaic)",
    )

    # Start command
    start_parser = subparsers.add_parser(
        "start",
        help="Start Mosaic backend server",
    )
    start_parser.add_argument(
        "path",
        nargs="?",
        help="Instance directory path (default: ~/.mosaic)",
    )
    start_parser.add_argument(
        "--daemon",
        "-d",
        action="store_true",
        help="Run in background",
    )

    # Stop command
    stop_parser = subparsers.add_parser(
        "stop",
        help="Stop Mosaic backend server",
    )
    stop_parser.add_argument(
        "path",
        nargs="?",
        help="Instance directory path (default: ~/.mosaic)",
    )
    stop_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force kill if graceful shutdown fails",
    )

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "init":
        init_command(args.path)
    elif args.command == "start":
        start_command(args.path, args.daemon)
    elif args.command == "stop":
        stop_command(args.path, args.force)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
