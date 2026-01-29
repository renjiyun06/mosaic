"""
Coze Integration Exception Classes
===================================

Custom exception hierarchy for Coze platform integration errors.
"""


class CozeError(Exception):
    """Base exception for all Coze integration errors."""
    pass


class CozeConnectionError(CozeError):
    """Browser connection to Coze platform failed."""
    pass


class CozeSkillNotFoundError(CozeError):
    """Requested skill not found on Coze platform."""
    pass


class CozeInstallationError(CozeError):
    """Skill installation operation failed."""
    pass


class CozeInvocationError(CozeError):
    """Skill invocation operation failed."""
    pass


class CozeTaskError(CozeError):
    """Task execution failed or returned error status."""
    pass
