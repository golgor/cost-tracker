"""Tests for recurring definition domain use cases."""

from datetime import date
from decimal import Decimal

import pytest

from app.adapters.sqlalchemy.unit_of_work import UnitOfWork
from app.domain.errors import DomainError, RecurringDefinitionNotFoundError
from app.domain.models import RecurringFrequency, SplitType
from app.domain.use_cases.recurring import (
    create_recurring_definition,
    update_recurring_definition,
)


def _create(uow, group_id, user_id, **kwargs):
    """Helper: create a definition with defaults."""
    defaults = dict(
        name="Netflix",
        amount=Decimal("14.99"),
        frequency=RecurringFrequency.MONTHLY,
        next_due_date=date(2026, 5, 1),
        payer_id=user_id,
    )
    defaults.update(kwargs)
    return create_recurring_definition(uow, group_id=group_id, **defaults)


class TestCreateRecurringDefinition:
    """Tests for create_recurring_definition use case."""

    def test_creates_and_returns_definition(self, uow: UnitOfWork):
        """create_recurring_definition returns a persisted definition with an ID."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_create", "rc_create@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id)
        uow.session.commit()

        assert defn.id > 0
        assert defn.name == "Netflix"
        assert defn.amount == Decimal("14.99")
        assert defn.frequency == RecurringFrequency.MONTHLY
        assert defn.is_active is True

    def test_uses_group_default_currency(self, uow: UnitOfWork):
        """Currency defaults to the group's configured default_currency."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_currency", "rc_currency@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id)
        uow.session.commit()

        assert defn.currency == "EUR"  # group default

    def test_explicit_currency_overrides_group_default(self, uow: UnitOfWork):
        """Explicit currency parameter takes precedence over group default."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_curr_ex", "rc_curr_ex@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id, currency="SEK")
        uow.session.commit()

        assert defn.currency == "SEK"

    def test_every_n_months_requires_interval(self, uow: UnitOfWork):
        """EVERY_N_MONTHS frequency without interval_months raises DomainError."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_nmonths", "rc_nmonths@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        with pytest.raises(DomainError, match="interval_months"):
            _create(
                uow,
                group.id,
                user.id,
                frequency=RecurringFrequency.EVERY_N_MONTHS,
                interval_months=None,
            )

    def test_every_n_months_with_valid_interval(self, uow: UnitOfWork):
        """EVERY_N_MONTHS with interval_months >= 1 succeeds."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_nm_ok", "rc_nm_ok@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(
            uow,
            group.id,
            user.id,
            frequency=RecurringFrequency.EVERY_N_MONTHS,
            interval_months=3,
        )
        uow.session.commit()

        assert defn.interval_months == 3

    def test_interval_months_rejected_for_non_every_n_months(self, uow: UnitOfWork):
        """interval_months set for non-EVERY_N_MONTHS frequency raises DomainError."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_nm_rej", "rc_nm_rej@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        with pytest.raises(DomainError, match="interval_months"):
            _create(uow, group.id, user.id, frequency=RecurringFrequency.MONTHLY, interval_months=3)

    def test_raises_if_group_not_found(self, uow: UnitOfWork):
        """GroupNotFoundError raised when group_id does not exist."""
        from app.domain.errors import GroupNotFoundError

        with pytest.raises(GroupNotFoundError):
            create_recurring_definition(
                uow,
                group_id=99999,
                name="Test",
                amount=Decimal("10.00"),
                frequency=RecurringFrequency.MONTHLY,
                next_due_date=date(2026, 5, 1),
                payer_id=1,
            )

    def test_auto_generate_defaults_to_false(self, uow: UnitOfWork):
        """auto_generate defaults to False when not provided."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_autogen", "rc_autogen@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id)
        uow.session.commit()

        assert defn.auto_generate is False

    def test_split_type_defaults_to_even(self, uow: UnitOfWork):
        """split_type defaults to EVEN when not provided."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_split_def", "rc_split_def@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id)
        uow.session.commit()

        assert defn.split_type == SplitType.EVEN

    def test_optional_category_persisted(self, uow: UnitOfWork):
        """Optional category is persisted when provided."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_cat", "rc_cat@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id, category="subscription")
        uow.session.commit()

        assert defn.category == "subscription"


class TestUpdateRecurringDefinition:
    """Tests for update_recurring_definition use case."""

    def test_update_name(self, uow: UnitOfWork):
        """update_recurring_definition changes the name field."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_upd_name", "rc_upd_name@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id, name="Old Name")
        uow.session.commit()

        updated = update_recurring_definition(
            uow, definition_id=defn.id, name="New Name"
        )
        uow.session.commit()

        assert updated.name == "New Name"

    def test_update_amount(self, uow: UnitOfWork):
        """update_recurring_definition changes the amount field."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_upd_amt", "rc_upd_amt@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id, amount=Decimal("14.99"))
        uow.session.commit()

        updated = update_recurring_definition(
            uow, definition_id=defn.id, amount=Decimal("19.99")
        )
        uow.session.commit()

        assert updated.amount == Decimal("19.99")

    def test_raises_for_missing_definition(self, uow: UnitOfWork):
        """RecurringDefinitionNotFoundError raised when definition_id does not exist."""
        with pytest.raises(RecurringDefinitionNotFoundError):
            update_recurring_definition(uow, definition_id=99999, name="X")

    def test_update_frequency_to_every_n_months_requires_interval(self, uow: UnitOfWork):
        """Changing frequency to EVERY_N_MONTHS without interval_months raises DomainError."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_upd_freq", "rc_upd_freq@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id, frequency=RecurringFrequency.MONTHLY)
        uow.session.commit()

        with pytest.raises(DomainError, match="interval_months"):
            update_recurring_definition(
                uow,
                definition_id=defn.id,
                frequency=RecurringFrequency.EVERY_N_MONTHS,
                interval_months=None,
            )

    def test_update_frequency_to_every_n_months_with_interval(self, uow: UnitOfWork):
        """Changing frequency to EVERY_N_MONTHS with interval_months succeeds."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_upd_nm", "rc_upd_nm@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(uow, group.id, user.id, frequency=RecurringFrequency.MONTHLY)
        uow.session.commit()

        updated = update_recurring_definition(
            uow,
            definition_id=defn.id,
            frequency=RecurringFrequency.EVERY_N_MONTHS,
            interval_months=4,
        )
        uow.session.commit()

        assert updated.frequency == RecurringFrequency.EVERY_N_MONTHS
        assert updated.interval_months == 4

    def test_unchanged_fields_are_preserved(self, uow: UnitOfWork):
        """Fields not passed to update_recurring_definition retain their original values."""
        from tests.conftest import create_test_group, create_test_user

        user = create_test_user(uow.session, "auth0|rc_upd_prsrv", "rc_upd_prsrv@example.com")
        group = create_test_group(uow.session, user.id)
        uow.session.commit()

        defn = _create(
            uow, group.id, user.id, name="Netflix", amount=Decimal("14.99"), category="subscription"
        )
        uow.session.commit()

        updated = update_recurring_definition(
            uow, definition_id=defn.id, name="Netflix Plus"
        )
        uow.session.commit()

        assert updated.amount == Decimal("14.99")
        assert updated.category == "subscription"
