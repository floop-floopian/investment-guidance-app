<!--
SYNC IMPACT REPORT
==================
Version change: [TEMPLATE] → 1.0.0
Modified principles: All (new project, template → concrete)
Added sections: Tech Stack, Quality Gates
Removed sections: None
Templates updated:
  ✅ .specify/memory/constitution.md (this file)
  ✅ .specify/templates/plan-template.md (Constitution Check gates updated)
  ✅ .specify/templates/spec-template.md (no changes needed — generic enough)
  ✅ .specify/templates/tasks-template.md (no changes needed — structure fits)
Follow-up TODOs: None
-->

# Investment Guidance App Constitution

## Core Principles

### I. Spec-Driven Development
Every feature MUST begin with an approved spec. No implementation starts without a completed
Spec → Plan → Tasks sequence. Deviating from this sequence requires explicit owner approval.

### II. Adapter Pattern for External Dependencies
All external data sources (Finnhub, Alpha Vantage, Reddit API, RSS, Telegram Bot API) MUST
be accessed through abstract provider interfaces. Swapping a provider MUST require zero
changes outside the adapter layer — configuration only.

### III. Test-First (NON-NEGOTIABLE)
TDD is mandatory. Tests MUST be written before implementation code. Tests MUST fail before
implementation begins. Red-Green-Refactor cycle MUST be enforced on every task.

### IV. Phase Discipline
Phase 1 is personal use only. Multi-user logic, authentication flows, and SaaS features
MUST NOT be implemented until Phase 1 is complete and in production use by the owner.
No premature SaaS scaffolding.

### V. Simplicity Over Cleverness
The simplest solution that satisfies the requirement MUST be chosen. Complexity MUST be
justified by a real, present requirement. YAGNI applies at all times.

### VI. Idempotent State Log
All critical system actions (BUY / SELL / HOLD recommendations) MUST be written to the
local state log before any external notification is sent. The state log is the source of
truth. Telegram (or any notification layer) is delivery-only and non-blocking.

## Tech Stack

- **Backend**: FastAPI (Python)
- **LLM Orchestration**: LangChain
- **Database**: Supabase (Postgres + Auth)
- **Scheduler**: APScheduler
- **Data Sources**: Finnhub + Alpha Vantage (adapter-wrapped, swappable)
- **Sentiment Sources**: Reddit API + RSS feeds (adapter-wrapped, swappable)
- **Notifications**: Telegram Bot API
- **Frontend**: React

## Quality Gates

- No feature branch merges without passing tests
- All PRs MUST include rationale for architectural decisions
- Data provider swaps MUST require zero changes outside the adapter layer
- Constitution Check in plan.md MUST be completed before Phase 0 research begins

## Governance

This constitution supersedes all other practices and documentation. Amendments require
explicit approval from the project owner before implementation. All PRs and reviews
MUST verify compliance with active principles. Complexity that violates Principle V
MUST be documented in the Complexity Tracking table of the implementation plan.

**Version**: 1.0.0 | **Ratified**: 2026-06-03 | **Last Amended**: 2026-06-03
