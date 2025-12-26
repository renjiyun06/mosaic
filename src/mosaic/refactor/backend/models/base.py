"""Base data model class"""
from datetime import datetime
from sqlmodel import SQLModel, Field


class BaseModel(SQLModel):
    """Base class for all data tables with common fields"""

    created_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
    )
    deleted_at: datetime | None = Field(default=None, index=True)

    @property
    def is_deleted(self) -> bool:
        """Check if record is soft-deleted"""
        return self.deleted_at is not None

    def soft_delete(self):
        """Mark record as soft-deleted"""
        self.deleted_at = datetime.now()
        self.updated_at = datetime.now()
