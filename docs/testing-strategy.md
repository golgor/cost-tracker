# Testing Strategy

## Overview

Simple, unified testing approach using **PostgreSQL only** with Django-style `_test` database suffix.

## Configuration

### Database URLs

| Environment | Database URL | Database Name |
|-------------|--------------|---------------|
| Development | `DATABASE_URL` | `costtracker` |
| Testing | Derived from `DATABASE_URL` | `costtracker_test` |
| CI/Override | `TEST_DATABASE_URL` | Custom |

The test database name is automatically derived by appending `_test` to your development database name:
- `costtracker` → `costtracker_test`
- `myapp` → `myapp_test`

## Test Types

### Unit Tests (`test:unit`)

Fast tests that don't require a database:
- Domain logic
- Model validation
- Business rules
- Utility functions

```bash
mise run test:unit
```

### Integration Tests (`test:integration`)

Tests requiring database persistence:
- Database adapters
- Repository patterns
- API endpoints
- Middleware

```bash
# Ensure PostgreSQL is running
mise run db

# Run migrations on dev database
mise run migrate

# Run integration tests (auto-creates test database)
mise run test:integration
```

### All Tests (`test`)

Run both unit and integration tests:

```bash
mise run test
```

## Test Database Lifecycle

1. **Before tests**: Test database auto-created (if doesn't exist)
2. **Before each test**: Transaction begins
3. **After each test**: Transaction rolls back (clean state)
4. **After test session**: Tables dropped, database kept for reuse

## Requirements

- PostgreSQL running locally or in Docker
- `DATABASE_URL` configured in `.env`
- User has permission to create databases

## Setup

```bash
# Start PostgreSQL
mise run db

# Run migrations on development database
mise run migrate

# Run all tests
mise run test
```

## CI/Production Override

Set `TEST_DATABASE_URL` to use a different test database:

```bash
TEST_DATABASE_URL=postgresql://user:pass@ci-host:5432/test_db mise run test
```

## Migration from SQLite

This setup replaces the previous SQLite + PostgreSQL hybrid approach:
- ❌ Removed SQLite fixtures
- ❌ Removed `check_same_thread` workarounds
- ✅ Single database technology (PostgreSQL)
- ✅ Consistent behavior across dev/test/prod
- ✅ No threading issues
