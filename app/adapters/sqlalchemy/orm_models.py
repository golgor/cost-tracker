from sqlmodel import SQLModel

# SQLModel.metadata serves as the declarative base for Alembic migrations.
# Table models (XxxRow) inherit from domain models with table=True.
# Domain models are defined in app/domain/models.py without table=True.
#
# Example pattern (Story 1.4+):
#   from app.domain.models import ExpenseBase
#   class ExpenseRow(ExpenseBase, table=True):
#       __tablename__ = "expenses"
#       id: int | None = Field(default=None, primary_key=True)
#       ...

# Re-export SQLModel for Alembic env.py
__all__ = ["SQLModel"]
