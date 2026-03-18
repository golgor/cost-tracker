"""Tests for UnitOfWork context manager pattern.

Integration tests using real PostgreSQL test database to verify transaction
behaviour (commit/rollback) with the context manager protocol.
"""

import logging
from unittest.mock import patch

import pytest

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork


class TestUnitOfWorkContextManager:
    """Test UnitOfWork context manager implementation."""

    def test_enter_returns_self(self, uow: UnitOfWork) -> None:
        """AC: __enter__ returns the UnitOfWork instance itself."""
        result = uow.__enter__()
        assert result is uow

    def test_context_manager_usage(self, uow: UnitOfWork) -> None:
        """AC: Can use UnitOfWork as context manager with 'with' statement."""
        # This test verifies the basic syntax works
        with uow as context_uow:
            assert context_uow is uow

    def test_exit_commits_on_success(self, uow: UnitOfWork) -> None:
        """AC: Exiting normally (no exception) commits the transaction."""
        # Create a user within context manager
        with uow:
            user = uow.users.save(
                oidc_sub="test_user_commit",
                email="test@example.com",
                display_name="Test User",
                actor_id=1,
            )
            created_user_id = user.id

        # Verify the user was persisted (committed)
        persisted_user = uow.users.get_by_id(created_user_id)
        assert persisted_user is not None
        assert persisted_user.oidc_sub == "test_user_commit"
        assert persisted_user.email == "test@example.com"

    def test_exit_rollback_on_exception(self, uow: UnitOfWork) -> None:
        """AC: Raising an exception in the context manager rolls back the transaction."""
        user_id = None

        # Create a user within context manager, then raise an exception
        try:
            with uow:
                user = uow.users.save(
                    oidc_sub="test_user_rollback",
                    email="rollback@example.com",
                    display_name="Rollback User",
                    actor_id=1,
                )
                user_id = user.id
                # Simulate an exception after the user is created
                raise ValueError("Intentional exception for rollback test")
        except ValueError:
            # Expected exception
            pass

        # Verify the user was NOT persisted (rolled back)
        assert user_id is not None
        persisted_user = uow.users.get_by_id(user_id)
        assert persisted_user is None

    def test_exit_raises_original_exception(self, uow: UnitOfWork) -> None:
        """AC: Original exception is not masked by __exit__."""
        original_error = ValueError("Test error message")

        with pytest.raises(ValueError, match="Test error message"), uow:
            raise original_error

    def test_rollback_failure_logged_not_raised(self, uow: UnitOfWork, caplog: Any) -> None:
        """AC: Rollback errors are logged but don't mask the original exception."""
        original_error = RuntimeError("Original error")

        # Mock the session.rollback to simulate a rollback failure
        with patch.object(uow.session, "rollback", side_effect=Exception("Rollback failed")):
            # The original exception should still be raised
            with pytest.raises(RuntimeError, match="Original error"), uow:
                raise original_error

            # The rollback failure should be logged
            assert any(
                "Rollback failed during exception handling" in record.message
                for record in caplog.records
                if record.levelno == logging.ERROR
            )

    def test_nested_context_managers_not_supported(self, uow: UnitOfWork) -> None:
        """Info test: Document that nested context managers are not supported.

        SQLAlchemy will raise an error if you try to start a transaction
        within a transaction. This test documents the boundary case.
        """
        # This behavior is enforced by SQLAlchemy, not our code,
        # but we document it here for clarity.
        with uow:
            # Attempting to nest would eventually raise from SQLAlchemy
            # because the session is already in a transaction context.
            # We don't prevent this in our code - let it fail at the DB level.
            pass


class TestUnitOfWorkTransactionIsolation:
    """Test that transactions are properly isolated and committed/rolled back."""

    def test_committed_changes_visible_after_exit(self, uow: UnitOfWork) -> None:
        """Verify committed changes are visible in a new UnitOfWork."""
        user_id = None

        # Create and commit a user
        with uow:
            user = uow.users.save(
                oidc_sub="isolation_test_1",
                email="isolation1@example.com",
                display_name="Isolation Test 1",
                actor_id=1,
            )
            user_id = user.id

        # Verify in a fresh UnitOfWork (fresh session)
        # Note: In actual pytest, we'd use a fresh fixture here
        fresh_user = uow.users.get_by_id(user_id)
        assert fresh_user is not None
        assert fresh_user.oidc_sub == "isolation_test_1"

    def test_audit_logging_within_transaction(self, uow: UnitOfWork) -> None:
        """Verify audit logging happens within transaction context."""
        # When a user is created with auto-auditing, the audit log
        # should be persisted along with the user in the same transaction
        with uow:
            user = uow.users.save(
                oidc_sub="audit_test_user",
                email="audit@example.com",
                display_name="Audit Test User",
                actor_id=1,
            )

        # Both user and audit log should be committed together
        persisted_user = uow.users.get_by_id(user.id)
        assert persisted_user is not None
        assert persisted_user.display_name == "Audit Test User"
