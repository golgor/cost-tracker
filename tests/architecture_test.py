"""Architecture enforcement tests.

These tests guard the hexagonal architecture boundaries:
1. Domain import purity — no infrastructure framework imports in app/domain/
2. Domain isolation — no internal app module imports in app/domain/
3. Queries are read-only — no write operations in app/adapters/sqlalchemy/queries/
4. No utils.py or helpers.py — files must be named by purpose
"""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
DOMAIN_DIR = REPO_ROOT / "app" / "domain"
QUERIES_DIR = REPO_ROOT / "app" / "adapters" / "sqlalchemy" / "queries"

# Infrastructure frameworks forbidden in domain layer
# Note: sqlmodel and pydantic are ALLOWED for data modeling/validation (ADR-011)
FORBIDDEN_DOMAIN_IMPORTS = {
    "fastapi",
    "starlette",
    "authlib",
    "structlog",
    "logging",
}

# Internal app modules forbidden in domain (maintains hexagonal boundary)
FORBIDDEN_INTERNAL_IMPORTS = {"app.adapters", "app.web", "app.auth", "app.api"}
WRITE_INDICATORS = {
    "session.add",
    "session.delete",
    "session.commit",
    "session.flush",
    ".add(",
    ".delete(",
    ".commit(",
    ".flush(",
    "INSERT",
    "UPDATE",
    "DELETE",
}


def _python_files(directory: Path) -> list[Path]:
    return list(directory.rglob("*.py"))


def test_domain_import_purity() -> None:
    """No infrastructure framework imports are permitted inside app/domain/."""
    violations: list[str] = []
    for py_file in _python_files(DOMAIN_DIR):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    if top_level in FORBIDDEN_DOMAIN_IMPORTS:
                        loc = f"{py_file.relative_to(REPO_ROOT)}:{node.lineno}"
                        violations.append(f"{loc} — import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.module:
                top_level = node.module.split(".")[0]
                if top_level in FORBIDDEN_DOMAIN_IMPORTS:
                    loc = f"{py_file.relative_to(REPO_ROOT)}:{node.lineno}"
                    violations.append(f"{loc} — from {node.module} import ...")

    assert not violations, "Domain import purity violations:\n" + "\n".join(violations)


def test_domain_no_internal_imports() -> None:
    """Domain must not import from internal application modules."""
    violations: list[str] = []
    for py_file in _python_files(DOMAIN_DIR):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(py_file))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for forbidden in FORBIDDEN_INTERNAL_IMPORTS:
                    if node.module.startswith(forbidden):
                        loc = f"{py_file.relative_to(REPO_ROOT)}:{node.lineno}"
                        violations.append(f"{loc} — from {node.module} import ...")

    assert not violations, "Domain internal import violations:\n" + "\n".join(violations)


def test_queries_are_read_only() -> None:
    """No write operations are permitted in app/adapters/sqlalchemy/queries/."""
    violations: list[str] = []
    for py_file in _python_files(QUERIES_DIR):
        source = py_file.read_text(encoding="utf-8")
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            for indicator in WRITE_INDICATORS:
                if indicator in stripped:
                    loc = f"{py_file.relative_to(REPO_ROOT)}:{lineno}"
                    violations.append(f"{loc} — '{indicator}' found")
                    break

    assert not violations, "Queries write operation violations:\n" + "\n".join(violations)


def test_no_utils_or_helpers_files() -> None:
    """No utils.py or helpers.py files are permitted under app/."""
    app_dir = REPO_ROOT / "app"
    forbidden = list(app_dir.rglob("utils.py")) + list(app_dir.rglob("helpers.py"))
    relative = [str(f.relative_to(REPO_ROOT)) for f in forbidden]
    assert not forbidden, "Forbidden files found (name by purpose instead):\n" + "\n".join(relative)
