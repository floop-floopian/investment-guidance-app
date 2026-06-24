# Implementation Plan: Investment Guidance Pipeline

**Branch**: `001-investment-guidance-pipeline` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-investment-guidance-pipeline/spec.md`

## Summary

Build a single-user Python CLI + background service that ingests macro signals
from Reddit (r/investing, r/stocks, r/economics) and RSS feeds, scores
sentiment via Claude API, runs fundamental and technical analysis on a
configured stock universe via Finnhub/Alpha Vantage, applies a barbell strategy
classifier, generates an LLM-reasoned shortlist, allocates user capital with
per-position rationale, logs all actions to local NDJSON + Supabase, and sends
Telegram notifications for completed analysis and critical signal shifts.

## Technical Context

**Language/Version**: Python 3.12

**Primary Dependencies**:
- `anthropic` — Claude API for sentiment scoring and reasoning generation
- `praw` — Reddit API ingestion (PRAW OAuth2)
- `feedparser` — RSS/Atom ingestion with conditional GET
- `finnhub-python` — primary financial data (fundamentals, price)
- `alpha-vantage` — secondary financial data (technical indicators, fallback)
- `python-telegram-bot` — Telegram Bot API delivery
- `apscheduler` — recurring monitor scheduler (AsyncIOScheduler)
- `supabase` — Postgres state persistence
- `typer` — CLI framework (built on Click)
- `fastapi` + `uvicorn` — HTTP API layer (Phase 1 minimal, Phase 2 full)
- `pydantic` — data validation and settings management
- `pytest` + `pytest-asyncio` — test suite

**Storage**: Local NDJSON state file (append-only audit log) + Supabase Postgres
(queryable history, pipeline run records)

**Testing**: pytest + pytest-asyncio; contract tests for all adapter interfaces

**Target Platform**: Linux/macOS (self-hosted, single user, Phase 1)

**Project Type**: CLI tool + background service (Phase 1); REST API with web UI
deferred to Phase 2 per constitution Principle IV

**Performance Goals**:
- On-demand pipeline: ≤5 min end-to-end (ingestion → Telegram delivery)
- Recurring monitor alert: ≤60 s from signal detection to Telegram delivery

**Constraints**:
- Finnhub free tier: 60 calls/min — requires queuing/backoff for ≤50 tickers
- Reddit PRAW: 60 req/min — batch subreddit fetches
- Single user; no auth or multi-tenancy in Phase 1
- All secrets via environment variables (no config UI)

**Scale/Scope**: 1 user, ≤50 tickers, 3 subreddits + configurable RSS feeds

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- [x] Feature has an approved spec (Principle I — Spec-Driven Development)
- [x] All external data sources accessed via adapter interfaces (Principle II)
- [x] Tests planned before any implementation task (Principle III — TDD)
- [x] No SaaS/multi-user features included — Phase 1 is single-user CLI/service only (Principle IV)
- [x] Complexity justified — minimal stack, no over-engineering (Principle V)
- [x] State log write precedes Telegram notification in every design path (Principle VI)

**Post-Phase 1 re-check**: All gates re-confirmed after design. Adapter interfaces
defined in `contracts/adapters.md`. State log write is first action in every
pipeline stage before any external call.

## Project Structure

### Documentation (this feature)

```text
specs/001-investment-guidance-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── cli.md           # CLI command contracts
│   └── adapters.md      # Adapter interface contracts
└── tasks.md             # Phase 2 output (/speckit-tasks)
```

### Source Code (repository root)

```text
src/
├── adapters/
│   ├── base.py               # Abstract base classes for all providers
│   ├── reddit_adapter.py     # PRAW-based Reddit ingestion
│   ├── rss_adapter.py        # feedparser-based RSS ingestion
│   ├── finnhub_adapter.py    # Finnhub financial data
│   ├── alphavantage_adapter.py # Alpha Vantage financial data
│   └── telegram_adapter.py   # Telegram Bot API delivery
├── models/
│   ├── macro_signal.py       # MacroSignal entity + Pydantic schema
│   ├── stock.py              # Stock entity + barbell classification
│   ├── allocation.py         # Allocation entity
│   ├── pipeline_run.py       # PipelineRun entity
│   └── state_log.py          # StateLogEntry entity
├── services/
│   ├── sentiment_service.py  # Claude API sentiment scoring
│   ├── analysis_service.py   # Fundamental + technical analysis
│   ├── barbell_service.py    # Barbell strategy classifier
│   ├── shortlist_service.py  # Risk-reward scoring + LLM reasoning
│   ├── allocation_service.py # Capital allocation + LLM rationale
│   └── monitor_service.py    # Recurring news check scheduler
├── pipeline/
│   ├── orchestrator.py       # End-to-end pipeline runner
│   └── stages.py             # Named pipeline stages (ingestion, analysis, etc.)
├── state/
│   ├── log_writer.py         # NDJSON append-only local log
│   └── supabase_store.py     # Supabase persistence layer
├── config/
│   └── settings.py           # Pydantic settings (env vars + config file)
└── cli.py                    # Typer CLI entrypoint

tests/
├── contract/
│   ├── test_reddit_adapter.py
│   ├── test_rss_adapter.py
│   ├── test_finnhub_adapter.py
│   ├── test_alphavantage_adapter.py
│   └── test_telegram_adapter.py
├── integration/
│   ├── test_pipeline_end_to_end.py
│   ├── test_monitor_cycle.py
│   └── test_state_log.py
└── unit/
    ├── test_sentiment_service.py
    ├── test_barbell_service.py
    ├── test_allocation_service.py
    └── test_shortlist_service.py
```

**Structure Decision**: Single-project layout. All source under `src/`, tests
mirroring the service/adapter structure. `adapters/` is a first-class directory
to enforce Principle II — every external provider is an adapter, not an inline
import.

## Complexity Tracking

> No Constitution Check violations — no entries required.
