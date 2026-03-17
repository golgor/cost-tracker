"""Tests for SqlAlchemyAuditAdapter persistence behavior and UoW atomicity."""

from sqlalchemy.orm import Session
from sqlmodel import select

from app.adapters.sqlalchemy.audit_adapter import SqlAlchemyAuditAdapter
from app.adapters.sqlalchemy.group_adapter import SqlAlchemyGroupAdapter
from app.adapters.sqlalchemy.orm_models import AuditRow
from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.adapters.sqlalchemy.user_adapter import SqlAlchemyUserAdapter
from app.domain.models import MemberRole, SplitType


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
            changes={"name": {"old": None, "new": "Home"}},
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
            changes={"default_currency": {"old": "EUR", "new": "SEK"}},
        )
        db_session.commit()

        row = db_session.exec(select(AuditRow).where(AuditRow.action == "group_updated")).first()
        assert row is not None
        assert row.actor_id == 42
        assert row.entity_type == "group"
        assert row.entity_id == 100
        assert row.changes == {"default_currency": {"old": "EUR", "new": "SEK"}}

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

    def test_log_without_changes(self, db_session: Session):
        """log() stores None when no changes are provided."""
        adapter = SqlAlchemyAuditAdapter(db_session)

        adapter.log(
            action="login",
            actor_id=7,
            entity_type="user",
            entity_id=7,
        )
        db_session.commit()

        row = db_session.exec(
            select(AuditRow).where(AuditRow.actor_id == 7, AuditRow.action == "login")
        ).first()
        assert row is not None
        assert row.changes is None

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
        """Audit entry is auto-created and persisted when the UoW commits a business change."""
        user = uow.users.save(
            oidc_sub="auth0|atomic_commit",
            email="atomic@example.com",
            display_name="Atomic User",
        )
        uow.commit()

        # Both user and audit row should exist
        retrieved_user = uow.users.get_by_id(user.id)
        assert retrieved_user is not None

        audit_rows = uow.session.exec(
            select(AuditRow).where(AuditRow.action == "user_created")
        ).all()
        assert len(audit_rows) == 1
        assert audit_rows[0].changes["oidc_sub"] == {"old": None, "new": "auth0|atomic_commit"}

    def test_audit_log_rolled_back_with_business_change(self, uow: UnitOfWork):
        """Auto-audit entry is rolled back when the UoW rolls back a business change."""
        uow.users.save(
            oidc_sub="auth0|atomic_rollback",
            email="rollback@example.com",
            display_name="Rollback User",
        )
        # Rollback without committing — both user and auto-audit row should vanish
        uow.rollback()

        # Neither user nor audit row should be visible in a fresh query
        audit_rows = uow.session.exec(
            select(AuditRow).where(AuditRow.action == "user_created")
        ).all()
        assert len(audit_rows) == 0

    def test_uow_audit_attribute_is_sqlalchemy_adapter(self, uow: UnitOfWork):
        """UnitOfWork.audit is wired to SqlAlchemyAuditAdapter."""
        assert isinstance(uow.audit, SqlAlchemyAuditAdapter)


class TestAdapterAutoAudit:
    """Tests verifying that adapter mutating methods auto-create audit rows."""

    def test_group_save_creates_audit_row(self, db_session: Session):
        """group_adapter.save() auto-audits with snapshot of new group fields."""
        audit = SqlAlchemyAuditAdapter(db_session)
        adapter = SqlAlchemyGroupAdapter(db_session, audit)

        group = adapter.save(
            "Home",
            actor_id=99,
            default_currency="SEK",
            default_split_type=SplitType.EVEN,
            tracking_threshold=45,
        )
        db_session.commit()

        rows = db_session.exec(
            select(AuditRow).where(
                AuditRow.action == "group_created",
                AuditRow.entity_id == group.id,
            )
        ).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.actor_id == 99
        assert row.entity_type == "group"
        assert row.changes is not None
        assert row.changes["name"] == {"old": None, "new": "Home"}
        assert row.changes["default_currency"] == {"old": None, "new": "SEK"}
        assert row.changes["tracking_threshold"] == {"old": None, "new": 45}

    def test_group_update_creates_audit_row_with_old_and_new(self, db_session: Session):
        """group_adapter.update() auto-audits with old→new changes for modified fields."""
        audit = SqlAlchemyAuditAdapter(db_session)
        adapter = SqlAlchemyGroupAdapter(db_session, audit)

        group = adapter.save("Home", actor_id=1, default_currency="EUR")
        db_session.commit()

        adapter.update(group.id, actor_id=1, default_currency="SEK", tracking_threshold=60)
        db_session.commit()

        rows = db_session.exec(
            select(AuditRow).where(
                AuditRow.action == "group_updated",
                AuditRow.entity_id == group.id,
            )
        ).all()
        assert len(rows) == 1
        changes = rows[0].changes
        assert changes is not None
        assert changes["default_currency"] == {"old": "EUR", "new": "SEK"}
        assert changes["tracking_threshold"] == {"old": 30, "new": 60}
        # Unchanged fields should not appear
        assert "name" not in changes

    def test_group_update_no_audit_when_nothing_changed(self, db_session: Session):
        """group_adapter.update() does not create an audit row if no fields changed."""
        audit = SqlAlchemyAuditAdapter(db_session)
        adapter = SqlAlchemyGroupAdapter(db_session, audit)

        group = adapter.save("Home", actor_id=1)
        db_session.commit()

        # Update with same values (name is not passed, so nothing changes)
        adapter.update(group.id, actor_id=1)
        db_session.commit()

        rows = db_session.exec(select(AuditRow).where(AuditRow.action == "group_updated")).all()
        assert len(rows) == 0

    def test_add_member_creates_audit_row(self, db_session: Session):
        """group_adapter.add_member() auto-audits with membership fields."""
        audit = SqlAlchemyAuditAdapter(db_session)
        user_adapter = SqlAlchemyUserAdapter(db_session, audit)
        group_adapter = SqlAlchemyGroupAdapter(db_session, audit)

        user = user_adapter.save(
            oidc_sub="auth0|auto_audit_member",
            email="audit-member@example.com",
            display_name="Audit Member",
        )
        group = group_adapter.save("Household", actor_id=user.id)
        db_session.commit()

        group_adapter.add_member(
            group.id,
            user.id,
            MemberRole.ADMIN,
            actor_id=user.id,
        )
        db_session.commit()

        rows = db_session.exec(
            select(AuditRow).where(
                AuditRow.action == "member_added",
                AuditRow.entity_id == group.id,
            )
        ).all()
        assert len(rows) == 1
        changes = rows[0].changes
        assert changes is not None
        assert changes["user_id"] == {"old": None, "new": user.id}
        assert changes["group_id"] == {"old": None, "new": group.id}
        assert changes["role"] == {"old": None, "new": "admin"}

    def test_auto_audit_shares_transaction_with_business_data(self, uow: UnitOfWork):
        """Auto-audit rows are rolled back together with business changes."""
        uow.groups.save("Rollback Test", actor_id=1)
        # Don't commit — rollback instead
        uow.rollback()

        rows = uow.session.exec(select(AuditRow).where(AuditRow.action == "group_created")).all()
        assert len(rows) == 0

    def test_user_save_creates_audit_row_on_new_user(self, db_session: Session):
        """user_adapter.save() auto-audits with snapshot when creating a new user."""
        audit = SqlAlchemyAuditAdapter(db_session)
        adapter = SqlAlchemyUserAdapter(db_session, audit)

        user = adapter.save(
            oidc_sub="auth0|audit_new_user",
            email="newuser@example.com",
            display_name="New User",
        )
        db_session.commit()

        rows = db_session.exec(
            select(AuditRow).where(
                AuditRow.action == "user_created",
                AuditRow.entity_id == user.id,
            )
        ).all()
        assert len(rows) == 1
        changes = rows[0].changes
        assert changes is not None
        assert changes["oidc_sub"] == {"old": None, "new": "auth0|audit_new_user"}
        assert changes["email"] == {"old": None, "new": "newuser@example.com"}
        assert changes["display_name"] == {"old": None, "new": "New User"}
        assert rows[0].actor_id == user.id

    def test_user_save_creates_audit_row_on_update(self, db_session: Session):
        """user_adapter.save() auto-audits with old→new changes when updating an existing user."""
        audit = SqlAlchemyAuditAdapter(db_session)
        adapter = SqlAlchemyUserAdapter(db_session, audit)

        user = adapter.save(
            oidc_sub="auth0|audit_update_user",
            email="old@example.com",
            display_name="Old Name",
        )
        db_session.commit()

        adapter.save(
            oidc_sub="auth0|audit_update_user",
            email="new@example.com",
            display_name="New Name",
        )
        db_session.commit()

        rows = db_session.exec(
            select(AuditRow).where(
                AuditRow.action == "user_updated",
                AuditRow.entity_id == user.id,
            )
        ).all()
        assert len(rows) == 1
        changes = rows[0].changes
        assert changes is not None
        assert changes["email"] == {"old": "old@example.com", "new": "new@example.com"}
        assert changes["display_name"] == {"old": "Old Name", "new": "New Name"}
        # oidc_sub didn't change, so it shouldn't appear
        assert "oidc_sub" not in changes

    def test_user_save_no_audit_when_nothing_changed(self, db_session: Session):
        """user_adapter.save() does not create an audit row if no fields changed on update."""
        audit = SqlAlchemyAuditAdapter(db_session)
        adapter = SqlAlchemyUserAdapter(db_session, audit)

        adapter.save(
            oidc_sub="auth0|audit_noop_user",
            email="same@example.com",
            display_name="Same Name",
        )
        db_session.commit()

        # Save again with identical values
        adapter.save(
            oidc_sub="auth0|audit_noop_user",
            email="same@example.com",
            display_name="Same Name",
        )
        db_session.commit()

        rows = db_session.exec(select(AuditRow).where(AuditRow.action == "user_updated")).all()
        assert len(rows) == 0
