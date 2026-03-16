# Domain models using SQLModel (without table=True for pure data + validation)
#
# Allowed imports: sqlmodel, pydantic, typing, decimal, datetime, enum (external libs)
# Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
#
# Pattern (Story 1.4+):
#   class ExpenseBase(SQLModel):
#       """Domain model — validation + business data. No table."""
#       amount: Decimal = Field(ge=0)
#       description: str = Field(max_length=255)
#       ...
#
#   class ExpenseCreate(ExpenseBase):
#       """Input schema for creating expense."""
#       pass
#
#   class ExpensePublic(ExpenseBase):
#       """Output schema — includes DB-generated fields."""
#       id: int
#       created_at: datetime

from datetime import datetime

from sqlmodel import Field, SQLModel  # noqa: F401


class UserBase(SQLModel):
    """Domain base for User — validation + business data. No table."""

    oidc_sub: str = Field(index=True, unique=True)
    email: str = Field(max_length=255)
    display_name: str = Field(max_length=255)


class UserPublic(UserBase):
    """Output schema for User — includes DB-generated fields."""

    id: int
    created_at: datetime
    updated_at: datetime
