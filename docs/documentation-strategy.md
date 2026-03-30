# Documentation Strategy Plan

## Context

The cost-tracker project has ~250KB of documentation across 23 markdown files, but it's almost
entirely **design-phase artifacts** (architecture decisions, UX specs, journey maps) produced during
initial planning. There is no user-facing documentation, no deployment guide, no README, and no
clear separation between "design records" and "living documentation." The user wants to restructure
docs with defined personas, a clear taxonomy, and a sustainable framework — covering both end-user
and maintainer audiences.

---

## 1. Personas

### P1: End User (Household Member / Evaluator)

**Who:** Golgor and Partner, plus potential self-hosters evaluating the project.
**Goals:** Understand what the app does, how to use it, find answers when stuck.
**Reads:** Getting started guide, feature overview with screenshots, FAQ/troubleshooting.
**Context:** Ranges from non-technical household members to technical users evaluating whether to
deploy. User docs double as product showcase for the open-source project — they help potential
adopters understand the app's value before committing to deployment.

### P2: Operator (Self-Hoster / Deployer)

**Who:** Golgor (or anyone deploying their own instance).
**Goals:** Install, configure, deploy, upgrade, back up, and monitor the application.
**Reads:** Installation guide, configuration reference, deployment guide, upgrade procedures,
backup/restore, troubleshooting.
**Context:** Technically capable. Needs precise, actionable instructions.

### P3: Developer (Contributor / Maintainer)

**Who:** Golgor as sole developer, plus AI coding agents (Claude sub-agents).
**Goals:** Understand architecture, conventions, and patterns to make changes confidently.
**Reads:** Architecture docs, ADRs, coding conventions, testing strategy, domain model reference.
**Context:** Deeply technical. Needs both "why" (explanation) and "how" (reference). AI agents are
a primary consumer — CLAUDE.md and AGENTS.md already serve this role well.

---

## 2. Framework Recommendation: MkDocs Material

**Recommendation: Keep MkDocs with Material theme.** It's already configured and is the right tool.

| Criterion | MkDocs Material | Plain Markdown | mdBook | Docusaurus |
| --- | --- | --- | --- | --- |
| Already configured | Yes | N/A | No | No |
| Markdown in `/docs` | Yes | Yes | Yes | Yes |
| Search | Built-in | No | Basic | Yes |
| Navigation/tabs | Yes | No | Yes | Yes |
| Python ecosystem fit | Native | N/A | Rust-oriented | JS/React |
| Maintenance burden | Low (pip install) | Zero | Low | High (Node.js) |
| Versioning support | Plugin (mike) | No | No | Yes |
| Mermaid diagrams | Plugin | No | Plugin | Plugin |

**Why not plain markdown?** You already have 20+ files. Without navigation, search, and structure,
discoverability drops fast. GitHub renders markdown, but cross-references break, there's no search,
and the reading experience is poor for operational docs.

**Why not Docusaurus?** Adds Node.js as a dependency. The project explicitly avoids Node.js at
runtime and this would add unnecessary toolchain complexity.

**Why not mdBook?** Rust-oriented, smaller plugin ecosystem, less natural for a Python project.

### Suggested MkDocs Enhancements

Add to `mkdocs.yml`:

- `mkdocs-mermaid2-plugin` — for architecture diagrams already in docs
- `navigation.indexes` feature — use `index.md` as section landing pages
- `toc.integrate` — integrate table of contents into navigation
- Admonitions extension — for warnings, notes, tips in operational docs
- Consider `mike` plugin later for versioned docs if needed

---

## 3. Documentation Taxonomy (Diataxis-Inspired)

The [Diataxis framework](https://diataxis.fr/) categorizes docs into four types. Here's how it
maps to this project:

| Diataxis Type | Purpose | Primary Persona | Cost Tracker Examples |
| --- | --- | --- | --- |
| **Tutorials** | Learning-oriented | End User, Operator | Getting started, first deployment |
| **How-to Guides** | Task-oriented | Operator, Developer | Deploy to k3s, add a new domain entity, run migrations |
| **Reference** | Information-oriented | Developer, Operator | Config reference, API reference, domain model reference |
| **Explanation** | Understanding-oriented | Developer | Architecture decisions, design rationale |

### Where Current Docs Fit

Most existing docs are **Explanation** (architecture rationale, UX design decisions). What's missing
is everything else — tutorials, how-to guides, and reference material.

---

## 4. Proposed Directory Structure

```text
docs/
├── index.md                              # Landing page with persona-based navigation
│
├── user-guide/                           # Persona: End User / Evaluator
│   ├── index.md                          # What is Cost Tracker? (product overview)
│   ├── getting-started.md                # First login, adding first expense
│   ├── features.md                       # Feature walkthrough with screenshots
│   └── faq.md                            # Common questions
│
├── operations/                           # Persona: Operator
│   ├── index.md                          # Operations overview
│   ├── installation.md                   # Prerequisites, Docker setup, first run
│   ├── configuration.md                  # All env vars, settings reference
│   ├── deployment.md                     # Docker, k3s/ArgoCD, GHCR pipeline
│   ├── authentication.md                 # Authentik/OIDC setup
│   ├── database.md                       # PostgreSQL setup, migrations, backups
│   ├── upgrading.md                      # Version upgrade procedures
│   └── troubleshooting.md               # Common issues and solutions
│
├── development/                          # Persona: Developer
│   ├── index.md                          # Dev quickstart
│   ├── setup.md                          # Local dev environment setup
│   ├── conventions.md                    # Naming, patterns, mandatory rules (extracted from CLAUDE.md)
│   ├── testing.md                        # Test strategy, running tests, writing tests
│   └── how-to/                           # Task-oriented developer guides
│       ├── add-domain-entity.md          # Step-by-step: new model → port → adapter → route
│       ├── add-route.md                  # Adding a new page/endpoint
│       └── add-migration.md             # Creating and running Alembic migrations
│
├── architecture/                         # Persona: Developer (Explanation)
│   ├── index.md                          # (existing, update)
│   ├── core-architectural-decisions.md   # (existing - ADRs)
│   ├── project-structure-boundaries.md   # (existing)
│   ├── implementation-patterns-consistency-rules.md  # (existing)
│   ├── settlement-patterns.md            # (existing)
│   └── project-context-analysis.md       # (existing)
│
├── design/                               # Persona: Developer (archived design artifacts)
│   ├── index.md                          # Context: these are design-phase records
│   ├── ux/                               # Renamed from ux-design/
│   │   ├── executive-summary.md
│   │   ├── core-user-experience.md
│   │   ├── user-journey-flows.md
│   │   ├── visual-design-foundation.md
│   │   ├── design-system-foundation.md
│   │   ├── filter-bar-date-picker.md
│   │   ├── admin-interface.md
│   │   └── ... (remaining UX files)
│   └── architecture/                     # One-time evaluation docs
│       ├── starter-template-evaluation.md
│       └── architecture-validation-results.md
│
└── backlog/                              # (existing)
    └── admin-user-management-ux.md
```

### Key Decisions

1. **Separate `architecture/` from `design/`**: Active ADRs and patterns stay in `architecture/`.
   One-time evaluation docs (starter template, validation results) move to `design/architecture/`
   as historical records.

2. **UX docs move to `design/ux/`**: These are design-phase artifacts, not living docs. They
   remain valuable as decision records but shouldn't be top-level navigation.

3. **`operations/` is the biggest gap**: No deployment, config, or operational docs exist today.

4. **`development/` extracts from CLAUDE.md**: CLAUDE.md is excellent for AI agents but not ideal
   as human-readable developer docs. Key content should be extracted (not duplicated — CLAUDE.md
   remains the source of truth for AI agents, developer docs reference it).

---

## 5. Migration Plan for Existing Docs

| Current Location | Action | New Location |
| --- | --- | --- |
| `docs/architecture/*.md` (6 core files) | Keep in place | `docs/architecture/` |
| `docs/architecture/starter-template-evaluation.md` | Move | `docs/design/architecture/` |
| `docs/architecture/architecture-validation-results.md` | Move | `docs/design/architecture/` |
| `docs/ux-design/*.md` (11 files) | Move | `docs/design/ux/` |
| `docs/backlog/*.md` | Keep in place | `docs/backlog/` |
| `CLAUDE.md` | Keep as-is (AI agent config) | Root |
| `AGENTS.md` | Keep as-is (AI agent config) | Root |
| `steps.md` | Remove or move to backlog | `docs/backlog/` or delete |

---

## 6. What to Write (Priority Order)

### Phase 1: Foundation (do first)

1. **`docs/index.md`** — Landing page with persona-based navigation ("I want to use the app" /
   "I want to deploy it" / "I want to develop on it")
2. **`README.md`** (project root) — Project overview, quick links, badges. Points to docs/.
3. **`docs/operations/configuration.md`** — Reference for all env vars from `settings.py`.
   Highest-value operational doc since it's needed for any deployment.
4. **`docs/operations/installation.md`** — Docker-compose quickstart, prerequisites.

### Phase 2: Operator Essentials

1. **`docs/operations/deployment.md`** — Full deployment guide (Docker build, GHCR, k3s/ArgoCD).
2. **`docs/operations/authentication.md`** — Authentik OIDC setup (currently undocumented).
3. **`docs/operations/database.md`** — PostgreSQL setup, Alembic migrations, backup strategy.

### Phase 3: Developer Onboarding

1. **`docs/development/setup.md`** — Local dev environment (uv, mise, PostgreSQL, first run).
2. **`docs/development/conventions.md`** — Human-readable version of key CLAUDE.md rules.
3. **`docs/development/testing.md`** — How to run tests, write tests, test patterns.

### Phase 4: Restructure Existing

1. Move UX design docs to `docs/design/ux/`
2. Move one-time architecture docs to `docs/design/architecture/`
3. Update `mkdocs.yml` navigation to reflect new structure
4. Add section index pages

### Phase 5: End-User & Showcase Docs

1. **`docs/user-guide/index.md`** — Product overview: what it is, who it's for, how it works.
   Doubles as the "why should I deploy this?" page for potential adopters.
2. **`docs/user-guide/getting-started.md`** — First login, adding first expense, basic workflow.
3. **`docs/user-guide/features.md`** — Feature walkthrough with screenshots (expenses, splits,
   settlements, recurring costs, admin). Serves both users and evaluators.

---

## 7. AGENTS.md and Lessons

`AGENTS.md` serves AI agents and stays at the project root. `tasks/lessons.md` contains accumulated
conventions and hard-won rules. `docs/development/conventions.md` extracts a human-friendly subset
rather than duplicating content. This avoids drift.

---

## 8. MkDocs Configuration Changes

Update `mkdocs.yml` to reflect the new structure:

```yaml
nav:
  - Home: index.md
  - User Guide:
    - user-guide/index.md
    - Getting Started: user-guide/getting-started.md
    - Features: user-guide/features.md
  - Operations:
    - operations/index.md
    - Installation: operations/installation.md
    - Configuration: operations/configuration.md
    - Deployment: operations/deployment.md
    - Authentication: operations/authentication.md
    - Database: operations/database.md
    - Upgrading: operations/upgrading.md
    - Troubleshooting: operations/troubleshooting.md
  - Development:
    - development/index.md
    - Local Setup: development/setup.md
    - Conventions: development/conventions.md
    - Testing: development/testing.md
    - How-To Guides:
      - Add a Domain Entity: development/how-to/add-domain-entity.md
      - Add a Route: development/how-to/add-route.md
      - Add a Migration: development/how-to/add-migration.md
  - Architecture:
    - architecture/index.md
    - Core Decisions: architecture/core-architectural-decisions.md
    - Project Structure: architecture/project-structure-boundaries.md
    - Implementation Patterns: architecture/implementation-patterns-consistency-rules.md
    - Settlement Patterns: architecture/settlement-patterns.md
  - Design Records:
    - design/index.md
    - UX Design:
      - design/ux/executive-summary.md
      - design/ux/core-user-experience.md
      - design/ux/user-journey-flows.md
      # ... remaining UX files
    - Architecture Evaluations:
      - design/architecture/starter-template-evaluation.md
      - design/architecture/architecture-validation-results.md
```

Add extensions:

```yaml
markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - toc:
      permalink: true

plugins:
  - search
```

---

## 9. Implementation Scope (This Task)

**Strategy + Foundation** — restructure and scaffold, but don't write all content yet.

### What we do now

1. Create `README.md` at project root (project overview, quick links to docs)
2. Restructure `/docs` directories (move UX docs to `design/ux/`, etc.)
3. Create all `index.md` landing pages (with persona-based navigation on root index)
4. Update `mkdocs.yml` with new nav structure and extensions
5. Create `docs/development/conventions.md` (extracted from CLAUDE.md)
6. Create `docs/operations/configuration.md` (generated from `settings.py`)

### What comes later (separate tasks)

- Full operations guides (deployment, authentication, database, upgrading)
- Developer how-to guides (add entity, add route, add migration)
- User guide content (getting started, features with screenshots)
- Troubleshooting docs

---

## 10. Verification

After implementation:

- [ ] `mise run lint:docs` passes on all new/moved files
- [ ] `mkdocs build --strict` produces no warnings
- [ ] `mkdocs serve` renders correctly with working navigation
- [ ] All internal cross-references resolve
- [ ] Existing docs haven't lost content during moves
- [ ] README.md renders well on GitHub
