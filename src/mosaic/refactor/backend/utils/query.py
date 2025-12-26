"""Database query helpers"""
from datetime import datetime
from typing import Type, TypeVar
from sqlmodel import Session, select
from ..models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


def get_active_query(model: Type[T]):
    """Get query for non-deleted records (soft delete filter)

    Args:
        model: Data model class

    Returns:
        Query object with soft delete filter applied

    Example:
        >>> query = get_active_query(User)
        >>> users = session.exec(query).all()
    """
    return select(model).where(model.deleted_at.is_(None))


def soft_delete(session: Session, instance: BaseModel) -> None:
    """Soft delete a record

    Args:
        session: Database session
        instance: Model instance to delete

    Example:
        >>> user = session.get(User, 1)
        >>> soft_delete(session, user)
        >>> session.commit()
    """
    instance.deleted_at = datetime.now()
    instance.updated_at = datetime.now()
    session.add(instance)
