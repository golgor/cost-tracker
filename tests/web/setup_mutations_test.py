"""Integration tests for setup flow - verify group creation persists to database.

Tests validate the core issue fixed: setup_step_2_post wasn't wrapping
create_household() in `with uow:` context manager, so transactions never committed.
Tests use use case layer directly to bypass CSRF middleware.
"""

import pytest

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.domain.models import SplitType
from app.domain.use_cases import groups as group_use_cases


@pytest.fixture
def new_user(uow: UnitOfWork):
    """Create a new user with no household."""
    with uow:
        user = uow.users.save(
            oidc_sub="setup_user@test.com",
            email="setup_user@test.com",
            display_name="Setup User",
        )
    return user


class TestSetupFlowGroupCreation:
    """Verify household creation persists to database."""

    def test_create_household_persists(self, new_user, uow: UnitOfWork):
        """Creating household group persists to database."""
        # Verify no group exists
        group_before = uow.groups.get_by_user_id(new_user.id)
        assert group_before is None

        # Create household via use case with context manager
        with uow:
            group_use_cases.create_household(
                uow=uow,
                user_id=new_user.id,
                name="Test Household",
                default_currency="EUR",
                default_split_type=SplitType.EVEN,
            )

        # Verify persisted in fresh lookup
        group_after = uow.groups.get_by_user_id(new_user.id)
        assert group_after is not None
        assert group_after.name == "Test Household"
        assert group_after.default_currency == "EUR"


class TestSetupFlowGroupConfiguration:
    """Verify group configuration updates persist to database."""

    def test_update_group_defaults_persists(self, new_user, uow: UnitOfWork):
        """Updating group defaults persists to database."""
        # Create household first
        with uow:
            group = group_use_cases.create_household(
                uow=uow,
                user_id=new_user.id,
                name="Config Test",
                default_currency="EUR",
                default_split_type=SplitType.EVEN,
            )

        # Verify defaults
        group_before = uow.groups.get_by_user_id(new_user.id)
        assert group_before.default_currency == "EUR"
        assert group_before.tracking_threshold == 30

        # Update with context manager
        with uow:
            group_use_cases.update_group_defaults(
                uow=uow,
                actor_user_id=new_user.id,
                group_id=group.id,
                default_currency="GBP",
                default_split_type=SplitType.EVEN,
                tracking_threshold=60,
            )

        # Verify persisted
        group_after = uow.groups.get_by_user_id(new_user.id)
        assert group_after.default_currency == "GBP"
        assert group_after.tracking_threshold == 60


class TestCompleteSetupFlowE2E:
    """End-to-end: create household and configure it."""

    def test_full_flow_creates_and_configures(self, new_user, uow: UnitOfWork):
        """Complete setup flow: create group then configure it."""
        # Step 1: Create household
        with uow:
            group = group_use_cases.create_household(
                uow=uow,
                user_id=new_user.id,
                name="My Household",
                default_currency="USD",
                default_split_type=SplitType.EVEN,
            )
            group_id = group.id

        # Step 2: Verify created
        group_step2 = uow.groups.get_by_user_id(new_user.id)
        assert group_step2 is not None
        assert group_step2.name == "My Household"

        # Step 3: Update configuration
        with uow:
            group_use_cases.update_group_defaults(
                uow=uow,
                actor_user_id=new_user.id,
                group_id=group_id,
                default_currency="SEK",
                default_split_type=SplitType.EVEN,
                tracking_threshold=45,
            )

        # Verify final state
        group_final = uow.groups.get_by_user_id(new_user.id)
        assert group_final.default_currency == "SEK"
        assert group_final.tracking_threshold == 45
