# Skeleton — domain ports (Protocol classes) will be added in Stories 1.4, 1.5, 2.1+
# Allowed imports: stdlib + external validation libs (sqlmodel, pydantic) per ADR-011
# Forbidden imports: app.adapters, app.web, app.auth, app.api (internal modules)
from typing import Protocol  # noqa: F401
