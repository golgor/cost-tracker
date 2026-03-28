# Refactor: Generic Balance Calculation

## Overview

Refactor the current hardcoded 2-person balance calculation into a generic N-person solution with configurable rounding, transaction optimization, and proper value objects. This refactoring enables future features like uneven splits and multi-currency support while maintaining clean architecture.

---

## Current State

The current implementation in `dashboard_queries.py`:

- Hardcoded for exactly 2 people
- Simple 50/50 split logic
- No transaction optimization
- Uses raw Decimal values
- Limited test coverage

```python
# Current hardcoded logic
def calculate_balance(session, group_id, user_id):
    # Assumes 2 members; will be generalized in future epics
    other_members = [m.user_id for m in members if m.user_id != user_id]
    partner_id = other_members[0] if other_members else None
    # expense.amount / 2 for each expense
```

---

## Target State

Generic N-person balance calculation with:

- Pure domain functions (no infrastructure dependencies)
- Money value object for type safety
- Configurable rounding precision
- Transaction minimization algorithm
- Strategy pattern for future split types
- Comprehensive test coverage

---

## Architecture Decisions

### 1. Domain Layer Pure Functions

**Decision**: Implement as pure domain functions in `app/domain/balance.py`

**Rationale**:

- Balance calculation is pure math, no side effects
- Easy to unit test without database
- Reusable across use cases (dashboard, settlements, API)
- Follows existing pattern in `settlements.py`

**Files**:

- `app/domain/balance.py` - Core calculation functions
- `app/domain/value_objects.py` - Money class
- `app/domain/splits/` - Split strategies

### 2. Money Value Object

**Decision**: Create `Money` class with Decimal + currency

**Rationale**:

- Prevents mixing currencies accidentally
- Encapsulates rounding rules
- Type-safe financial calculations
- JSON serialization support

**Implementation**:

```python
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "EUR"
    # Arithmetic operations with currency validation
```

### 3. Configuration Injection

**Decision**: Pass `BalanceConfig` as explicit parameter (NOT global state)

**Rationale**:

- No hidden dependencies
- Easy to test different configurations
- Follows hexagonal architecture
- Supports per-group configuration in future

**Implementation**:

```python
def calculate_balances(
    expenses: list[ExpensePublic],
    member_ids: list[int],
    config: BalanceConfig,  # Injected
) -> dict[int, MemberBalance]:
```

### 4. Strategy Pattern for Splits

**Decision**: Use Strategy pattern even with only EvenSplitStrategy initially

**Rationale**:

- Epic 4 (uneven splits) becomes trivial to implement
- Documents the extension point
- Clean separation of concerns
- Minimal overhead (one ABC + one class)

**Implementation**:

```python
class SplitStrategy(ABC):
    @abstractmethod
    def calculate_shares(self, expense, member_ids) -> dict[int, Money]: ...

class EvenSplitStrategy(SplitStrategy):
    # 50/50 implementation
```

### 5. Rounding Error Handling

**Decision**: Largest balance absorbs the rounding error

**Rationale**:

- Simple and deterministic
- Only affects one person's balance
- Minimal impact on fairness
- Tie-breaker: payer (first in input list) absorbs

**Example**:

```
€100 / 3 people = €33.33, €33.33, €33.34
Payer gets €33.34 (absorbs the penny)
```

### 6. Transaction Minimization

**Decision**: Greedy algorithm (largest debtor pays largest creditor)

**Rationale**:

- Optimal for 2-person groups
- Acceptable for N-person (produces ≤ N-1 transactions)
- Simple to implement and understand
- Can be replaced with better algorithm later if needed

**Algorithm**:

1. Separate debtors (negative balance) and creditors (positive)
2. Sort both by absolute amount (descending)
3. Match largest debtor with largest creditor
4. Create transaction for min(debt, credit)
5. Update remaining amounts, repeat until all settled

---

## Implementation Details

### File Structure

```
app/domain/
├── __init__.py
├── balance.py                   # Core calculation functions
├── value_objects.py             # Money class
├── splits/                      # Split strategies package
│   ├── __init__.py
│   ├── config.py                # BalanceConfig
│   └── strategies.py            # SplitStrategy, EvenSplitStrategy
└── errors.py                    # Add BalanceCalculationError

tests/domain/
├── balance_test.py              # Comprehensive unit tests
└── splits_test.py               # Strategy tests
```

### Core Data Structures

```python
# app/domain/value_objects.py
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "EUR"
    
    def __add__(self, other: "Money") -> "Money": ...
    def __sub__(self, other: "Money") -> "Money": ...
    def __lt__(self, other: "Money") -> bool: ...

# app/domain/balance.py
@dataclass(frozen=True)
class MemberBalance:
    user_id: int
    amount_paid: Money
    fair_share: Money
    net_balance: Money  # Positive = owed, Negative = owes

@dataclass(frozen=True)
class SettlementTransaction:
    from_user_id: int   # debtor
    to_user_id: int     # creditor
    amount: Money

# app/domain/splits/config.py
@dataclass(frozen=True)
class BalanceConfig:
    rounding_precision: Decimal = Decimal("0.01")  # cents
    rounding_mode: str = "ROUND_HALF_EVEN"         # banker's rounding
```

### Core Functions

```python
# app/domain/balance.py

def calculate_balances(
    expenses: list[ExpensePublic],
    member_ids: list[int],
    config: BalanceConfig,
    strategy: SplitStrategy | None = None,
) -> dict[int, MemberBalance]:
    """Calculate balances for all members.
    
    Args:
        expenses: List of pending expenses
        member_ids: All members in group
        config: Rounding configuration
        strategy: Split strategy (default: even split)
    
    Returns:
        Dict mapping user_id to MemberBalance
    
    Raises:
        BalanceCalculationError: If currencies are mixed or calculation fails
    """
    # Validate all expenses have same currency
    # Track amount_paid per person
    # Calculate fair share per person using strategy
    # Compute net_balance = amount_paid - fair_share
    # Apply rounding according to config
    # Ensure sum of all balances equals zero (adjust payer if needed)

def minimize_transactions(
    balances: dict[int, MemberBalance]
) -> list[SettlementTransaction]:
    """Minimize transactions to settle all debts.
    
    Uses greedy algorithm: largest debtor pays largest creditor.
    Produces at most N-1 transactions for N people.
    
    Args:
        balances: Member balances from calculate_balances
    
    Returns:
        List of transactions to settle all debts
    """
    # Separate debtors (net_balance < 0) and creditors (net_balance > 0)
    # Sort by absolute amount (descending)
    # While both lists non-empty:
    #   - Match first debtor with first creditor
    #   - Create transaction for min(amount)
    #   - Update remaining amounts
    #   - Remove settled parties
```

### Split Strategy Interface

```python
# app/domain/splits/strategies.py

class SplitStrategy(ABC):
    """Abstract base for expense splitting strategies."""
    
    @abstractmethod
    def calculate_shares(
        self,
        expense: ExpensePublic,
        member_ids: list[int],
    ) -> dict[int, Money]:
        """Calculate each member's share of the expense.
        
        Args:
            expense: The expense to split
            member_ids: All members who should share
        
        Returns:
            Mapping of user_id to their share amount
        """

class EvenSplitStrategy(SplitStrategy):
    """Split expense evenly among all members."""
    
    def calculate_shares(self, expense, member_ids) -> dict[int, Money]:
        share = Money(expense.amount, expense.currency) / len(member_ids)
        return {user_id: share for user_id in member_ids}
```

---

## Error Handling

New domain errors to add:

```python
# app/domain/errors.py

class BalanceCalculationError(DomainError):
    """Base error for balance calculation failures."""

class InvalidShareError(BalanceCalculationError):
    """Raised when share calculation fails (e.g., zero members)."""

class RoundingPrecisionError(BalanceCalculationError):
    """Raised when rounding configuration is invalid."""

class CurrencyMismatchError(BalanceCalculationError):
    """Raised when expenses have different currencies."""
```

---

## Testing Strategy

### Unit Tests (No Database)

**File**: `tests/domain/balance_test.py`

**Test Coverage**:

| Category | Test Cases |
|----------|-----------|
| **2-Person** | Equal expenses, one pays all, alternating payments, zero balance |
| **3-Person** | 100€/3=33.34/33.33/33.33 rounding, various contributions |
| **4+ Person** | Equal split, various contributions, zero contributors |
| **Rounding** | 0.01€/3 people, 100.005€ pre-rounded, very large amounts |
| **Edge Cases** | Empty expenses, single person, negative amounts (rejected), NaN/Infinity (rejected) |
| **Transactions** | 2-person simple, 3-person chain, complex 4-person, already settled |
| **Idempotency** | Same inputs produce same outputs |
| **Currency** | Mixed currencies raise error, single currency OK |

**Example Test**:

```python
def test_three_person_split_100_euros():
    """100€ / 3 = 33.34 for payer, 33.33 for others."""
    expenses = [
        ExpensePublic(amount=Decimal("100.00"), payer_id=1, ...)
    ]
    member_ids = [1, 2, 3]
    config = BalanceConfig()
    
    result = calculate_balances(expenses, member_ids, config)
    
    # Payer paid 100, fair share is 33.34
    assert result[1].net_balance.amount == Decimal("33.34")
    # Others owe 33.33 each
    assert result[2].net_balance.amount == Decimal("-33.33")
    assert result[3].net_balance.amount == Decimal("-33.33")
    # Sum must be zero
    total = sum(r.net_balance.amount for r in result.values())
    assert total == Decimal("0")
```

---

## Integration Points

### Current Code Updates

**1. dashboard_queries.py**:

```python
# Current
from app.domain.balance import calculate_balances
from app.domain.splits import BalanceConfig, EvenSplitStrategy

def calculate_balance(session, group_id, user_id):
    expenses = get_pending_expenses(session, group_id)
    members = get_group_members(session, group_id)
    member_ids = [m.user_id for m in members]
    
    config = BalanceConfig()  # Default config
    balances = calculate_balances(expenses, member_ids, config)
    
    return {
        "current_user_is_owed": balances[user_id].net_balance.amount,
        "formatted_message": format_message(balances[user_id]),
        # ... other fields
    }
```

**2. settlements.py**:

```python
# Refactor to use minimize_transactions
from app.domain.balance import calculate_balances, minimize_transactions

def calculate_settlement(expenses, user_display_names):
    member_ids = list(user_display_names.keys())
    config = BalanceConfig()
    
    balances = calculate_balances(expenses, member_ids, config)
    transactions = minimize_transactions(balances)
    
    # Return first transaction (or multiple for N-person)
    if not transactions:
        return "All square!"
    
    tx = transactions[0]
    return f"{user_display_names[tx.from_user_id]} pays {user_display_names[tx.to_user_id]} €{tx.amount}"
```

---

## Deferred to Future Epics

### Epic 4: Uneven Splits

**Features**:

- Custom percentage splits (60/40, 50/30/20)
- Share-based splits (3 shares vs 2 shares)
- Exact amount splits
- Per-expense split configuration

**Implementation**:

- Add `PercentageSplitStrategy`, `ShareSplitStrategy`
- New table `expense_splits` to persist share configuration
- UI for configuring splits per expense

**Extension Point**: Add new strategies to `app/domain/splits/strategies.py`

### Epic 5: Multi-Currency

**Features**:

- Expenses in different currencies
- Currency conversion with exchange rates
- Display balances in preferred currency

**Implementation**:

- `CurrencyConversionPort` for exchange rate service
- Conversion in `calculate_balances()` before calculation
- Exchange rate caching and updates

**Extension Point**: Inject conversion service, validate currencies or convert

### Future: Advanced Optimization

**Features**:

- Optimal transaction routing (minimize total amount transferred)
- Historical balance snapshots
- Balance caching for performance

**Implementation**:

- `TransactionOptimizerPort` with multiple algorithms
- `NetworkFlowOptimizer` for optimal routing
- Balance cache invalidation on new expenses

**Extension Point**: Define `TransactionOptimizerPort` in `ports.py`

---

## Success Criteria

- [x] All pure functions have 100% unit test coverage
- [x] 2-person scenarios match current implementation exactly
- [x] 3-person split of 100€ sums to exactly 0.00 (no rounding leakage)
- [x] Input validation rejects negative amounts, NaN, Infinity
- [x] Mixed currencies raise CurrencyMismatchError
- [x] Transaction minimization produces ≤ N-1 transactions
- [x] No global state or side effects
- [x] All tests pass: `mise run test`
- [x] All linting passes: `mise run lint`
- [x] Follows hexagonal architecture principles
- [x] Extensible for uneven splits (Epic 4)

---

## Implementation Timeline

**Phase 1: Domain Layer** (2 hours)

- Create `value_objects.py` (Money class)
- Create `splits/` package (config, strategies)
- Create `balance.py` (calculate_balances, minimize_transactions)
- Add error types to `errors.py`

**Phase 2: Tests** (2 hours)

- Create comprehensive unit tests
- 2-person, 3-person, 4+ person scenarios
- Edge cases and rounding tests
- Transaction optimization tests

**Phase 3: Integration** (1 hour)

- Refactor `dashboard_queries.py`
- Refactor `settlements.py` (optional)
- Update any existing tests
- Run full test suite

**Total Estimated Time**: 5 hours

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rounding errors accumulate | Low | Medium | Validate sum to zero, adjust payer |
| Performance with large groups | Low | Low | O(n log n) algorithm, database is bottleneck |
| Breaking existing balance display | Medium | High | Keep same return format initially, test thoroughly |
| Floating point precision issues | Low | High | Use Decimal throughout, never float |
| Currency mixing bugs | Low | High | Explicit validation, raise error if mixed |

---

## References

- **Existing Pattern**: `app/domain/use_cases/settlements.py` - `calculate_settlement()`
- **Inspiration**: `home-automation-hub/apps/cost_splitter/utils.py`
- **Architecture**: Hexagonal Architecture, Ports & Adapters
- **Rounding**: Banker's rounding (ROUND_HALF_EVEN) for statistical fairness

---

## Notes

- **Payer absorbs rounding error**: Arrange input so payer is first in member_ids list
- **Keep Money operations simple**: Implement only what balance calculation needs
- **Folder structure**: Use `app/domain/splits/` package
- **Test naming**: Follow convention `tests/domain/balance_test.py`
- **No persistence changes**: This is pure domain logic refactoring
- **Backward compatibility**: Phase 3 integration maintains existing API signatures initially

---

## Post-Implementation Next Steps

### Phase 4: Integration (TODO)

Now that the core domain logic is complete, the following integration work remains:

**1. Refactor `app/adapters/sqlalchemy/queries/dashboard_queries.py`**

- Replace hardcoded 2-person `calculate_balance()` function
- Use new `calculate_balances()` from `app/domain/balance`
- Pass `BalanceConfig` with appropriate settings
- Maintain backward-compatible return format initially

**2. Update `app/domain/use_cases/settlements.py`**

- Refactor `calculate_settlement()` to use `minimize_transactions()`
- Support N-person settlement transactions
- Handle multiple transactions (not just single payer/payee)

**3. Update UI/Templates**

- Modify balance bar display for N-person scenarios
- Update settlement review page for multiple transactions
- Handle new settlement transaction format

**4. Migration Strategy**

- Gradual rollout: test with existing 2-person groups first
- Monitor for any discrepancies in balance calculations
- Full rollout once validated

**5. Documentation Updates**

- Update API documentation if balance endpoint changes
- Document new N-person support for users
- Update architecture docs to reflect completed refactoring

---

**Status**: ✅ **Phase 1-3 Complete** (Domain + Tests)

**Next Step**: Phase 4 Integration - Update `dashboard_queries.py` and `settlements.py` to use new generic balance calculation
