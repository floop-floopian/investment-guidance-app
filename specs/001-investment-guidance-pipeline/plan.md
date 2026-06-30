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

---

## Phase 1 Stabilisation — 2026-06-30

Post-implementation bug fixes and real-data integration. Pipeline is now end-to-end
functional with live data sources. Changes committed as `fix: stabilise pipeline`.

### Data Sources

| Component | Before | After |
|---|---|---|
| Technical indicators | Alpha Vantage (25 req/day free tier — always rate-limited) | `yfinance` — no API key, no rate limit, 1-year daily history |
| Macro signals | Reddit PRAW OAuth (credentials unavailable — 401 on every call) | RSS feeds: Yahoo Finance, CNBC, MarketWatch |
| Reddit adapter | Crashed with 401 on every run | Silently skips when credentials absent |

### New: Signal-Driven Ticker Universe

Added `TickerExtractionService` between sentiment scoring (Stage 2) and stock
analysis (Stage 3). The LLM now extracts ticker symbols from the scored news
headlines; those tickers drive the analysis universe. The configured `STOCK_TICKERS`
list in `.env` acts as fallback/supplement only (capped at 15 total).

**Pipeline flow after this change:**
```
RSS news → top 25 signals scored → tickers extracted → those stocks analysed
→ barbell classified → shortlist → allocation → Discord
```

### Bug Fixes

| Bug | Root Cause | Fix |
|---|---|---|
| Sentiment always `0.00` | 88 signals × response tokens exceeded `max_tokens=2048`, JSON truncated, silent fallback to 0 | Cap to 25 most-recent signals before scoring |
| Barbell classifier too loose | `safe_qualifiers >= 1` — large-cap alone qualified anything as SAFE_CORE | Raised to `>= 2` qualifiers required |
| Satellite momentum threshold | `15.0` was intended as % per year but applied to 90-day window (= 60% annualised) | Corrected to `5.0` (≈ 20% annualised — above-market threshold) |
| Analyst consensus always `None` | Finnhub adapter hardcoded `analyst_consensus: None` | Implemented via `recommendation_trends` API; weighted 1–5 scale |
| Supabase duplicate upsert error | `upsert()` without `on_conflict` tried to resolve on all unique constraints; cross-feed articles caused ambiguity | Explicit `on_conflict="id"` + dedup guard before batch |
| RSS adapter double-parse | `feedparser.parse()` called twice; second call overwrote conditional GET result | Single call with kwargs; conditional GET preserved |
| State log written to wrong path | `~` in `STATE_LOG_PATH` env var not expanded by Pydantic; log written inside project dir | Added `.expanduser()` in `log_writer.py` |
| RSS signal ID collisions | Fallback used `entry.get('link', str(len(signals)))` — relative IDs collide across feeds | `hashlib.md5(feed_url + entry_key)[:16]` — deterministic, globally unique |

### Phase 2 Backlog (deferred)

- **Reddit ingestion** — replace PRAW with Reddit JSON API (`reddit.com/r/subreddit.json`), no OAuth required
- **Barbell threshold UI** — expose `barbell_*` settings as user-configurable via web form (risk profile presets: Conservative / Moderate / Aggressive)
- **Signal-to-ratio coupling** — macro sentiment aggregate dynamically shifts the SAFE_CORE / SATELLITE capital ratio (Phase 3)
- **NewsAPI** — keyword-query news (`"NVDA OR inflation"`) for higher-relevance signals
- **Frontend** — FastAPI + web UI per spec (currently CLI + Discord only)
