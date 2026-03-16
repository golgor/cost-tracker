from datetime import datetime

from sqlmodel import Field, SQLModel

from app.domain.models import UserBase

# SQLModel.metadata serves as the declarative base for Alembic migrations.
# Table models (XxxRow) inherit from domain models with table=True.
# Domain models are defined in app/domain/models.py without table=True.


class UserRow(UserBase, table=True):
    """ORM model for User — inherits from domain base, adds DB fields."""

    __tablename__ = "users"

    id: int | None = Field(default=None, primary_key=True)
    oidc_sub: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# Re-export SQLModel for Alembic env.py
__all__ = ["SQLModel", "UserRow"]
