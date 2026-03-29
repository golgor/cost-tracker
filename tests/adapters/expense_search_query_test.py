"""Tests for keyword search in get_filtered_expenses query."""

import pytest
from sqlmodel import Session

from app.adapters.sqlalchemy.orm_models import ExpenseNoteRow, ExpenseRow
from app.adapters.sqlalchemy.queries.dashboard_queries import get_filtered_expenses
from app.domain.models import ExpenseStatus
from tests.conftest import create_test_expense, create_test_user


@pytest.fixture
def search_setup(db_session: Session):
    """Two users, a handful of expenses with descriptions and notes."""
    user1 = create_test_user(db_session, "search_u1", "u1@test.com", "Alice")
    user2 = create_test_user(db_session, "search_u2", "u2@test.com", "Bob")

    netflix = create_test_expense(
        db_session, "14.99", user1.id, user1.id, description="Netflix subscription"
    )
    grocery = create_test_expense(
        db_session, "55.00", user1.id, user2.id, description="Grocery run at Lidl"
    )
    electric = create_test_expense(
        db_session, "80.00", user1.id, user1.id, description="Electric bill"
    )

    # Add a note to grocery mentioning "receipt" (to test notes JOIN)
    note = ExpenseNoteRow(
        expense_id=grocery.id,
        author_id=user1.id,
        content="Got receipt from Lidl cashier",
    )
    db_session.add(note)

    # Add two notes to electric (to test DISTINCT — should return only one row)
    db_session.add(ExpenseNoteRow(expense_id=electric.id, author_id=user1.id, content="from bill"))
    db_session.add(
        ExpenseNoteRow(expense_id=electric.id, author_id=user2.id, content="bill confirmed")
    )
    db_session.flush()

    return {
        "user1": user1,
        "user2": user2,
        "netflix": netflix,
        "grocery": grocery,
        "electric": electric,
    }


class TestSearchByDescription:
    def test_ilike_matches_case_insensitively(self, db_session: Session, search_setup):
        results = get_filtered_expenses(db_session, search_query="NETFLIX")
        assert len(results) == 1
        assert results[0].description == "Netflix subscription"

    def test_partial_match_works(self, db_session: Session, search_setup):
        results = get_filtered_expenses(db_session, search_query="net")
        assert len(results) == 1
        assert results[0].description == "Netflix subscription"

    def test_no_match_returns_empty_list(self, db_session: Session, search_setup):
        results = get_filtered_expenses(db_session, search_query="spotify")
        assert results == []


class TestSearchByNotes:
    def test_matches_note_content(self, db_session: Session, search_setup):
        # "receipt" only appears in grocery note, not in description
        results = get_filtered_expenses(db_session, search_query="receipt")
        assert len(results) == 1
        assert results[0].description == "Grocery run at Lidl"

    def test_note_ilike_case_insensitive(self, db_session: Session, search_setup):
        results = get_filtered_expenses(db_session, search_query="LIDL")
        assert len(results) == 1


class TestDistinct:
    def test_expense_with_multiple_matching_notes_returned_once(
        self, db_session: Session, search_setup
    ):
        # "bill" matches two notes on electric AND the description
        results = get_filtered_expenses(db_session, search_query="bill")
        electric_results = [r for r in results if r.description == "Electric bill"]
        assert len(electric_results) == 1  # DISTINCT ensures no duplicates


class TestSearchCombinedWithFilters:
    def test_search_combined_with_status_filter(self, db_session: Session, search_setup):
        # Mark netflix as settled
        netflix = search_setup["netflix"]
        netflix_row = db_session.get(ExpenseRow, netflix.id)
        assert netflix_row is not None
        netflix_row.status = ExpenseStatus.SETTLED
        db_session.flush()

        # Search "netflix" with status=PENDING → no results
        pending_results = get_filtered_expenses(
            db_session, search_query="netflix", status="PENDING"
        )
        assert pending_results == []

        # Search "netflix" with status=SETTLED → 1 result
        settled_results = get_filtered_expenses(
            db_session, search_query="netflix", status="SETTLED"
        )
        assert len(settled_results) == 1

    def test_search_combined_with_payer_filter(self, db_session: Session, search_setup):
        user2 = search_setup["user2"]
        # grocery is paid by user2; netflix and electric by user1
        results = get_filtered_expenses(db_session, search_query="lidl", payer_id=user2.id)
        assert len(results) == 1
        assert results[0].description == "Grocery run at Lidl"

    def test_search_with_no_query_returns_all(self, db_session: Session, search_setup):
        results = get_filtered_expenses(db_session, search_query=None)
        assert len(results) == 3

    def test_empty_string_search_returns_all(self, db_session: Session, search_setup):
        # Passing empty string is falsy — treated the same as None (no search filter)
        results = get_filtered_expenses(db_session, search_query="")
        assert len(results) == 3
