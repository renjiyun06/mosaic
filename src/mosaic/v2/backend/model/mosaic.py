"""Mosaic-related data models"""
from sqlmodel import Field
from .base import BaseModel


class Mosaic(BaseModel, table=True):
    """Mosaic instance table"""

    __tablename__ = "mosaics"

    user_id: int = Field(index=True, description="Reference to users.id")
    name: str = Field(max_length=100)
    description: str | None = Field(default=None, max_length=500)
