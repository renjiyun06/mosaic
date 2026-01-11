"""Terminal management module for workspace mode.

This module provides PTY (pseudo-terminal) support for interactive terminal sessions
in workspace mode. It handles terminal lifecycle, I/O operations, and message routing.

Components:
- TerminalManager: Global manager for all terminal sessions
- PTYSession: Individual PTY process wrapper
"""

from .manager import TerminalManager
from .pty_session import PTYSession

__all__ = ['TerminalManager', 'PTYSession']
