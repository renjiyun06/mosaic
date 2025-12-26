"""工具函数"""
from .email import EmailService
from .query import get_active_query, soft_delete

__all__ = ["EmailService", "get_active_query", "soft_delete"]
