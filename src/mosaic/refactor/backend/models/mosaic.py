"""Mosaic-related data models"""
from sqlmodel import Field
from .base import BaseModel


class Mosaic(BaseModel, table=True):
    """Mosaic instance table"""

    __tablename__ = "mosaics"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
