"""Tests for SqlAlchemyAuditAdapter persistence behavior and UoW atomicity."""

from sqlalchemy.orm import Session
from sqlmodel import select

from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.orm_models import AuditRow
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork


class TestSqlAlchemyAuditAdapter:
    """Persistence behavior tests for SqlAlchemyAuditAdapter."""

    def test_log_creates_row_in_database(self, db_session: Session):
        """log() inserts a new row into audit_logs."""
        adapter = SqlAlchemyAuditAdapter(db_session)
        before = len(db_session.exec(select(AuditRow)).all())

        adapter.log(
            action="test_action",
            actor_id=1,
            entity_type="group",
            entity_id=5,
            details={"key": "value"},
        )
        db_session.commit()

        after = len(db_session.exec(select(AuditRow)).all())
        assert after == before + 1

    def test_log_stores_correct_values(self, db_session: Session):
        """log() stores all provided field values correctly."""
        adapter = SqlAlchemyAuditAdapter(db_session)

        adapter.log(
            action="group_updated",
            actor_id=42,
            entity_type="group",
            entity_id=100,
            details={"currency": "EUR"},
        )
        db_session.commit()

        row = db_session.exec(select(AuditRow).where(AuditRow.action == "group_updated")).first()
        assert row is not None
        assert row.actor_id == 42
        assert row.entity_type == "group"
        assert row.entity_id == 100
        assert row.details == {"currency": "EUR"}

    def test_log_occurred_at_is_timezone_aware(self, db_session: Session):
        """occurred_at is stored with timezone info."""
        adapter = SqlAlchemyAuditAdapter(db_session)

        adapter.log(
            action="tz_check",
            actor_id=1,
            entity_type="user",
            entity_id=1,
        )
        db_session.commit()

        row = db_session.exec(select(AuditRow).where(AuditRow.action == "tz_check")).first()
        assert row is not None
        assert row.occurred_at.tzinfo is not None

    def test_multiple_logs_are_independent(self, db_session: Session):
        """Multiple log() calls create separate rows."""
        adapter = SqlAlchemyAuditAdapter(db_session)

        adapter.log(action="event_a", actor_id=1, entity_type="group", entity_id=1)
        adapter.log(action="event_b", actor_id=2, entity_type="group", entity_id=2)
        db_session.commit()

        rows = db_session.exec(
            select(AuditRow).where(AuditRow.action.in_(["event_a", "event_b"]))
        ).all()
        assert len(rows) == 2


class TestUnitOfWorkAuditAtomicity:
    """Tests verifying that audit entries share the same transaction as business changes."""

    def test_audit_log_committed_with_business_change(self, uow: UnitOfWork):
        """Audit entry is persisted when the UoW commits a business change."""
        user = uow.users.save(
            oidc_sub="auth0|atomic_commit",
            email="atomic@example.com",
            display_name="Atomic User",
        )
        uow.audit.log(
            action="user_created",
            actor_id=user.id,
            entity_type="user",
            entity_id=user.id,
        )
        uow.commit()

        # Both user and audit row should exist
        retrieved_user = uow.users.get_by_id(user.id)
        assert retrieved_user is not None

        audit_rows = uow.session.exec(
            select(AuditRow).where(AuditRow.action == "user_created")
        ).all()
        assert len(audit_rows) == 1

    def test_audit_log_rolled_back_with_business_change(self, uow: UnitOfWork):
        """Audit entry is rolled back when the UoW rolls back a business change."""
        user = uow.users.save(
            oidc_sub="auth0|atomic_rollback",
            email="rollback@example.com",
            display_name="Rollback User",
        )
        uow.audit.log(
            action="user_created_rollback_test",
            actor_id=user.id if user.id else 0,
            entity_type="user",
            entity_id=user.id if user.id else 0,
        )
        # Rollback without committing
        uow.rollback()

        # Neither user nor audit row should be visible in a fresh query
        audit_rows = uow.session.exec(
            select(AuditRow).where(AuditRow.action == "user_created_rollback_test")
        ).all()
        assert len(audit_rows) == 0

    def test_uow_audit_attribute_is_sqlalchemy_adapter(self, uow: UnitOfWork):
        """UnitOfWork.audit is wired to SqlAlchemyAuditAdapter."""
        assert isinstance(uow.audit, SqlAlchemyAuditAdapter)
