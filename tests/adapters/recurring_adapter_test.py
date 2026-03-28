"""Tests for SqlAlchemyRecurringDefinitionAdapter persistence behavior."""

from datetime import date
from decimal import Decimal

import pytest
from sqlmodel import Session, select

from app.adapters.sqlalchemy.orm_models import RecurringDefinitionRow
from app.adapters.sqlalchemy.recurring_adapter import SqlAlchemyRecurringDefinitionAdapter
from app.domain.errors import RecurringDefinitionNotFoundError
from app.domain.models import RecurringDefinitionPublic, RecurringFrequency, SplitType


def _make_adapter(session: Session) -> SqlAlchemyRecurringDefinitionAdapter:
    return SqlAlchemyRecurringDefinitionAdapter(session)


def _make_definition(
    group_id: int,
    payer_id: int,
    name: str = "Netflix",
    amount: str = "14.99",
    frequency: RecurringFrequency = RecurringFrequency.MONTHLY,
    **kwargs,
) -> RecurringDefinitionPublic:
    return RecurringDefinitionPublic.model_construct(
        id=0,
        group_id=group_id,
        name=name,
        amount=Decimal(amount),
        frequency=frequency,
        next_due_date=kwargs.get("next_due_date", date(2026, 4, 1)),
        payer_id=payer_id,
        split_type=kwargs.get("split_type", SplitType.EVEN),
        split_config=kwargs.get("split_config"),
        category=kwargs.get("category"),
        auto_generate=kwargs.get("auto_generate", False),
        is_active=kwargs.get("is_active", True),
        currency=kwargs.get("currency", "EUR"),
        interval_months=kwargs.get("interval_months"),
    )


class TestSqlAlchemyRecurringDefinitionAdapter:
    """Persistence behavior tests for SqlAlchemyRecurringDefinitionAdapter."""

    def test_save_creates_row(self, db_session: Session):
        """save() inserts a new recurring_definitions row."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_save", "rd_save@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        before = len(db_session.exec(select(RecurringDefinitionRow)).all())
        adapter.save(_make_definition(group.id, user.id))
        db_session.commit()

        after = len(db_session.exec(select(RecurringDefinitionRow)).all())
        assert after == before + 1

    def test_save_stores_correct_values(self, db_session: Session):
        """save() persists all provided field values correctly."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_values", "rd_values@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        defn = adapter.save(
            _make_definition(
                group.id,
                user.id,
                name="Car Insurance",
                amount="340.00",
                frequency=RecurringFrequency.SEMI_ANNUALLY,
                next_due_date=date(2026, 4, 15),
                category="insurance",
                auto_generate=True,
                currency="SEK",
            ),
        )
        db_session.commit()

        row = db_session.exec(
            select(RecurringDefinitionRow).where(RecurringDefinitionRow.id == defn.id)
        ).first()
        assert row is not None
        assert row.name == "Car Insurance"
        assert row.amount == Decimal("340.00")
        assert row.frequency == RecurringFrequency.SEMI_ANNUALLY
        assert row.next_due_date == date(2026, 4, 15)
        assert row.category == "insurance"
        assert row.auto_generate is True
        assert row.currency == "SEK"
        assert row.deleted_at is None

    def test_get_by_id_returns_public_model(self, db_session: Session):
        """get_by_id() returns RecurringDefinitionPublic, not RecurringDefinitionRow."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_getbyid", "rd_getbyid@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        saved = adapter.save(_make_definition(group.id, user.id))
        db_session.commit()

        retrieved = adapter.get_by_id(saved.id)

        assert retrieved is not None
        assert type(retrieved).__name__ == "RecurringDefinitionPublic"
        assert retrieved.id == saved.id

    def test_get_by_id_returns_none_for_missing(self, db_session: Session):
        """get_by_id() returns None for non-existent ID."""
        adapter = _make_adapter(db_session)
        assert adapter.get_by_id(99999) is None

    def test_list_by_group_excludes_deleted_by_default(self, db_session: Session):
        """list_by_group() excludes soft-deleted definitions by default."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_list_excl", "rd_list_excl@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        defn_active = adapter.save(
            _make_definition(group.id, user.id, name="Active")
        )
        defn_to_delete = adapter.save(
            _make_definition(group.id, user.id, name="ToDelete")
        )
        db_session.commit()

        adapter.soft_delete(defn_to_delete.id)
        db_session.commit()

        results = adapter.list_by_group(group.id)
        ids = [d.id for d in results]

        assert defn_active.id in ids
        assert defn_to_delete.id not in ids

    def test_list_by_group_include_deleted(self, db_session: Session):
        """list_by_group(include_deleted=True) includes soft-deleted rows."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_list_incl", "rd_list_incl@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        defn = adapter.save(
            _make_definition(group.id, user.id, name="WillDelete")
        )
        db_session.commit()

        adapter.soft_delete(defn.id)
        db_session.commit()

        results = adapter.list_by_group(group.id, include_deleted=True)
        ids = [d.id for d in results]
        assert defn.id in ids

    def test_list_by_group_active_only(self, db_session: Session):
        """list_by_group(active_only=True) excludes paused definitions."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_list_active", "rd_list_active@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        defn_active = adapter.save(
            _make_definition(group.id, user.id, name="Active", is_active=True)
        )
        defn_paused = adapter.save(
            _make_definition(group.id, user.id, name="Paused", is_active=False)
        )
        db_session.commit()

        results = adapter.list_by_group(group.id, active_only=True)
        ids = [d.id for d in results]

        assert defn_active.id in ids
        assert defn_paused.id not in ids

    def test_update_changes_fields(self, db_session: Session):
        """update() modifies only the provided fields."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_update", "rd_update@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        defn = adapter.save(
            _make_definition(group.id, user.id, amount="14.99", currency="EUR"),
        )
        db_session.commit()

        updated = adapter.update(
            defn.id,
            amount=Decimal("19.99"),
            currency="SEK",
        )
        db_session.commit()

        assert updated.amount == Decimal("19.99")
        assert updated.currency == "SEK"
        assert updated.name == defn.name  # unchanged

    def test_update_raises_for_missing_definition(self, db_session: Session):
        """update() raises RecurringDefinitionNotFoundError for non-existent ID."""
        adapter = _make_adapter(db_session)
        with pytest.raises(RecurringDefinitionNotFoundError):
            adapter.update(99999, name="New Name")

    def test_soft_delete_sets_deleted_at(self, db_session: Session):
        """soft_delete() sets deleted_at without removing the row."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_softdel", "rd_softdel@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        defn = adapter.save(_make_definition(group.id, user.id))
        db_session.commit()

        adapter.soft_delete(defn.id)
        db_session.commit()

        row = db_session.exec(
            select(RecurringDefinitionRow).where(RecurringDefinitionRow.id == defn.id)
        ).first()
        assert row is not None
        assert row.deleted_at is not None

    def test_soft_delete_raises_for_missing_definition(self, db_session: Session):
        """soft_delete() raises RecurringDefinitionNotFoundError for non-existent ID."""
        adapter = _make_adapter(db_session)
        with pytest.raises(RecurringDefinitionNotFoundError):
            adapter.soft_delete(99999)

    def test_soft_delete_raises_for_already_deleted(self, db_session: Session):
        """soft_delete() raises RecurringDefinitionNotFoundError for already-deleted row."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(db_session, "auth0|rd_del2x", "rd_del2x@example.com")
        group = create_test_group(db_session, user.id)
        adapter = _make_adapter(db_session)

        defn = adapter.save(_make_definition(group.id, user.id))
        db_session.commit()

        adapter.soft_delete(defn.id)
        db_session.commit()

        with pytest.raises(RecurringDefinitionNotFoundError):
            adapter.soft_delete(defn.id)
