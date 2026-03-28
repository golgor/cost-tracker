"""Proof: except X, Y: behavior differs across Python versions.

Run with: uv run python tests/proof_except_syntax.py

Python 2:    except X, Y:  → catches X, binds exception to name Y
Python 3.0-3.13: except X, Y:  → SyntaxError
Python 3.14: except X, Y:  → catches both X and Y (same as except (X, Y):)

Conclusion: with Python 3.14 the parentheses are optional but recommended
for clarity and backward compatibility.
"""

import ast
import sys

print(f"Python {sys.version}\n")

# ── Test 1: How does the parser interpret except X, Y: ? ─────────────

code_without_parens = """\
try:
    pass
except TypeError, ValueError:
    pass
"""

code_with_parens = """\
try:
    pass
except (TypeError, ValueError):
    pass
"""

print("=" * 60)
print("Test 1: AST comparison — with vs without parentheses")
print("=" * 60)

try:
    tree_no_parens = ast.parse(code_without_parens)
    handler = tree_no_parens.body[0].handlers[0]
    print(f"  except X, Y:   → type={ast.dump(handler.type)}")
    print(f"                   name={handler.name!r}")
except SyntaxError as e:
    print(f"  except X, Y:   → SyntaxError: {e.msg}")

tree_with_parens = ast.parse(code_with_parens)
handler = tree_with_parens.body[0].handlers[0]
print(f"  except (X, Y): → type={ast.dump(handler.type)}")
print(f"                   name={handler.name!r}")


# ── Test 2: Does except X, Y: catch both exception types? ────────────

from decimal import Decimal, InvalidOperation  # noqa: E402

print()
print("=" * 60)
print("Test 2: Does 'except InvalidOperation, ValueError:' catch both?")
print("=" * 60)


def trigger_invalid_operation():
    try:
        Decimal("not-a-number")  # raises InvalidOperation
    except InvalidOperation, ValueError:
        return "CAUGHT"
    return "MISSED"


def trigger_value_error():
    try:
        int("not-a-number")  # raises ValueError
    except InvalidOperation, ValueError:
        return "CAUGHT"
    return "MISSED"


print(f"  InvalidOperation → {trigger_invalid_operation()}")
print(f"  ValueError       → {trigger_value_error()}")


# ── Test 3: Does it shadow the ValueError name? ──────────────────────

print()
print("=" * 60)
print("Test 3: Does 'except X, Y:' shadow the name Y?")
print("=" * 60)

# In Python 2, except X, Y: would rebind Y to the caught exception.
# In Python 3.14, it does NOT — Y remains the original builtin.
original_ve = ValueError
try:
    Decimal("bad")
except InvalidOperation, ValueError:
    pass

print(f"  ValueError is still builtins.ValueError: {ValueError is original_ve}")

print()
print("=" * 60)
print("CONCLUSION")
print("=" * 60)
if sys.version_info >= (3, 14):
    print("""
  Python 3.14 re-introduced 'except X, Y:' as equivalent to 'except (X, Y):'.
  Both forms catch both exception types. No name shadowing occurs.

  Parentheses are optional in 3.14+ but RECOMMENDED for:
  - Backward compatibility with Python 3.0-3.13 (where it's a SyntaxError)
  - Clarity of intent
  - Consistency with PEP 8 style
""")
else:
    print(f"""
  Python {sys.version_info.major}.{sys.version_info.minor} requires parentheses.
  'except X, Y:' is a SyntaxError in this version.
""")
