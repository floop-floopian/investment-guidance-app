---
description: "Task list for Investment Guidance Pipeline implementation"
---

# Tasks: Investment Guidance Pipeline

**Input**: Design documents from `specs/001-investment-guidance-pipeline/`

**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅

**Tests**: Included — TDD is NON-NEGOTIABLE per constitution Principle III.
Tests MUST be written first and MUST fail before implementation begins.

**Organization**: Tasks grouped by user story for independent implementation
and testing of each story.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Exact file paths included in every task description

## Path Conventions

- Source: `src/` at repository root
- Tests: `tests/` at repository root
- Specs: `specs/001-investment-guidance-pipeline/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependency wiring, and base structure.

- [X] T001 Initialize Python project with pyproject.toml, src/ and tests/ layout, and .gitignore at repository root
- [ ] T002 Add all dependencies to pyproject.toml: anthropic, praw, feedparser, finnhub-python, alpha-vantage, python-telegram-bot, apscheduler, supabase, typer, fastapi, uvicorn, pydantic, pydantic-settings, pytest, pytest-asyncio
- [ ] T003 [P] Configure pytest and pytest-asyncio in pyproject.toml; create tests/contract/, tests/integration/, tests/unit/ directories with __init__.py
- [ ] T004 [P] Implement Pydantic BaseSettings config in src/config/settings.py covering all env vars: ANTHROPIC_API_KEY, FINNHUB_API_KEY, ALPHA_VANTAGE_API_KEY, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, SUPABASE_URL, SUPABASE_KEY, STATE_LOG_PATH, CAPITAL_MIN_POSITION_USD, BARBELL_SAFE_CORE_RATIO (default 0.60), BARBELL_SAFE_BETA_MAX, BARBELL_SATELLITE_BETA_MIN, SENTIMENT_CRITICAL_DELTA, MONITOR_INTERVAL_HIGH_VOL_MINUTES, MONITOR_INTERVAL_MED_VOL_MINUTES, MONITOR_INTERVAL_LOW_VOL_MINUTES
- [ ] T005 Create Supabase schema: write migration SQL for tables pipeline_runs, macro_signals, stocks, allocations, state_log, feed_state per data-model.md entity definitions

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Abstract interfaces, shared models, and state persistence that all
user stories depend on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [ ] T006 Implement abstract adapter base classes in src/adapters/base.py: FinancialDataProvider (get_quote, get_fundamentals, get_technicals), MacroSignalProvider (fetch_signals), NotificationProvider (send_message)
- [ ] T007 [P] Implement Pydantic entity models in src/models/: macro_signal.py (MacroSignal, SentimentLabel, SourceType), stock.py (Stock, BarbellClass, VolatilityTier [HIGH/MED/LOW derived from beta], DataSource), allocation.py (Allocation), pipeline_run.py (PipelineRun, TriggerType, RunStatus), state_log.py (StateLogEntry, ActionType, LogLevel)
- [ ] T008 Implement append-only NDJSON state log writer in src/state/log_writer.py: atomic line append, StateLogEntry serialization, path from settings
- [ ] T009 Implement Supabase persistence in src/state/supabase_store.py: upsert methods for all six tables (pipeline_runs, macro_signals, stocks, allocations, state_log, feed_state), non-blocking best-effort writes
- [ ] T010 [P] Write contract test for FinancialDataProvider interface in tests/contract/test_financial_provider.py: verify any concrete adapter implements all required methods with correct return types
- [ ] T011 [P] Write contract test for MacroSignalProvider interface in tests/contract/test_macro_provider.py: verify fetch_signals returns List[MacroSignal]
- [ ] T012 [P] Write contract test for NotificationProvider interface in tests/contract/test_notification_provider.py: verify send_message signature and return type

**Checkpoint**: Foundation ready — all adapters, models, and state persistence
in place. User story implementation can now begin.

---

## Phase 3: User Story 1 — On-Demand Analysis & Allocation (Priority: P1) 🎯 MVP

**Goal**: User provides capital, triggers pipeline, receives Telegram message
with risk-reward scored shortlist and capital allocation with per-position reasoning.

**Independent Test**: `python -m src.cli run-pipeline --capital 10000` completes
without error, Telegram message received containing ≥1 stock, risk-reward score,
reasoning text, and allocation table summing to ≤$10,000.

### Tests for User Story 1 (write first — MUST fail before implementing)

> **NOTE: Write these tests FIRST and confirm they FAIL before T017**

- [ ] T013 [P] [US1] Write failing unit tests for SentimentService in tests/unit/test_sentiment_service.py: test batched scoring returns MacroSignal list with scores in [-1.0, 1.0], test aggregate signal computation, test structured JSON parsing
- [ ] T014 [P] [US1] Write failing unit tests for BarbellService in tests/unit/test_barbell_service.py: test SAFE_CORE classification thresholds, test SATELLITE classification thresholds, test EXCLUDED when no thresholds met, test configurable threshold overrides
- [ ] T015 [P] [US1] Write failing unit tests for AllocationService in tests/unit/test_allocation_service.py: test 60/40 band split (BARBELL_SAFE_CORE_RATIO=0.60 default), test proportional weighting by risk-reward score, test minimum position enforcement ($500 default), test allocation sum never exceeds capital input, test ratio is overridable via settings
- [ ] T016 [US1] Write failing integration test for end-to-end pipeline in tests/integration/test_pipeline_end_to_end.py: mock all adapters, assert StateLogEntry written before Telegram call, assert allocation sum ≤ capital, assert all NDJSON entries present

### Implementation for User Story 1

- [ ] T017 [P] [US1] Implement RedditAdapter in src/adapters/reddit_adapter.py: PRAW OAuth2 script auth, fetch top-25 hot posts per configured subreddit, return List[MacroSignal] with source_type=REDDIT
- [ ] T018 [P] [US1] Implement RSSAdapter in src/adapters/rss_adapter.py: feedparser polling per configured feed URL, conditional GET using ETag/Last-Modified from FeedState, return List[MacroSignal] with source_type=RSS
- [ ] T019 [US1] Implement SentimentService in src/services/sentiment_service.py: batch all ingested items into single Claude API call (claude-sonnet-4-6), system-prompt caching via anthropic cache_control, parse structured JSON response, update sentiment_score and sentiment_label on each MacroSignal, compute aggregate signal
- [ ] T020 [P] [US1] Implement FinnhubAdapter in src/adapters/finnhub_adapter.py: get_quote (real-time price), get_fundamentals (P/E, market cap, dividend yield, beta, revenue growth, debt/equity), token-bucket rate limiter at 60 req/min
- [ ] T021 [P] [US1] Implement AlphaVantageAdapter in src/adapters/alphavantage_adapter.py: get_technicals (RSI-14, SMA-50, SMA-200, 90d momentum via MONTHLY_ADJUSTED), daily request counter against 75/day free tier limit, warn on approach
- [ ] T022 [US1] Implement AnalysisService in src/services/analysis_service.py: iterate configured ticker list, call FinnhubAdapter (primary) with AlphaVantageAdapter fallback, assemble Stock entities, set data_source field, log API_ERROR on per-ticker failures without aborting run
- [ ] T023 [US1] Implement BarbellService in src/services/barbell_service.py: classify each Stock as SAFE_CORE / SATELLITE / EXCLUDED using rule-based thresholds from settings, expose classify_all(stocks, macro_aggregate) → List[Stock]
- [ ] T024 [US1] Implement ShortlistService in src/services/shortlist_service.py: filter EXCLUDED stocks, compute risk_reward_score (weighted composite of fundamentals + technicals + macro signal), call Claude API for per-stock reasoning text, return sorted shortlist
- [ ] T025 [US1] Implement AllocationService in src/services/allocation_service.py: split shortlist by barbell band, apply configurable capital ratio (BARBELL_SAFE_CORE_RATIO, default 0.60 safe-core / 0.40 satellite), proportional weight by risk_reward_score, enforce minimum position size, call Claude API for per-allocation and overall rationale, return List[Allocation]
- [ ] T026 [P] [US1] Implement TelegramAdapter in src/adapters/telegram_adapter.py: python-telegram-bot async send_message to configured chat_id, format shortlist + allocation table as Markdown, 2-retry backoff on failure
- [ ] T027 [US1] Implement PipelineOrchestrator for on-demand runs in src/pipeline/orchestrator.py: ordered stage execution (ingest → score → analyze → classify → shortlist → allocate), write StateLogEntry to log_writer BEFORE each external notification, create and update PipelineRun record, handle PARTIAL status on non-fatal errors
- [ ] T028 [US1] Add `run-pipeline` command to src/cli.py using Typer: --capital FLOAT (required), --config PATH (optional override), calls orchestrator.run_on_demand(capital)
- [ ] T029 [US1] Make all T013–T016 tests pass; confirm Red→Green for each test file

**Checkpoint**: User Story 1 fully functional — run-pipeline delivers Telegram
message with shortlist and allocations.

---

## Phase 4: User Story 2 — Recurring News Monitoring & Alerts (Priority: P2)

**Goal**: System polls macro sources on a configurable schedule; sends Telegram
alert within 60 seconds when sentiment delta exceeds threshold.

**Independent Test**: Start monitor with short interval (5 min), wait for cycle,
confirm state log shows MONITOR_CYCLE_COMPLETE or CRITICAL_SIGNAL_DETECTED entry;
if signal detected, confirm Telegram received within 60s.

### Tests for User Story 2 (write first — MUST fail before implementing)

> **NOTE: Write these tests FIRST and confirm they FAIL before T032**

- [ ] T030 [P] [US2] Write failing unit tests for MonitorService in tests/unit/test_monitor_service.py: test cycle runs ingestion + scoring, test delta calculation against prior aggregate, test CRITICAL_SIGNAL_DETECTED fires when delta ≥ threshold, test no alert when delta < threshold, test HIGH volatility stocks use MONITOR_INTERVAL_HIGH_VOL_MINUTES, test LOW volatility stocks use MONITOR_INTERVAL_LOW_VOL_MINUTES
- [ ] T031 [US2] Write failing integration test for monitor cycle in tests/integration/test_monitor_cycle.py: mock adapters, run one cycle, assert MONITOR_CYCLE_COMPLETE log entry written, assert FeedState updated per RSS feed

### Implementation for User Story 2

- [ ] T032 [US2] Implement MonitorService in src/services/monitor_service.py: APScheduler AsyncIOScheduler with per-stock volatility-aware interval triggers — HIGH volatility stocks (VolatilityTier.HIGH, beta > BARBELL_SATELLITE_BETA_MIN) use MONITOR_INTERVAL_HIGH_VOL_MINUTES, MED use MONITOR_INTERVAL_MED_VOL_MINUTES, LOW use MONITOR_INTERVAL_LOW_VOL_MINUTES. Each cycle ingests Reddit + RSS, scores sentiment, computes delta vs prior aggregate (stored in Supabase state_log), writes log entry, triggers Telegram alert if |delta| ≥ SENTIMENT_CRITICAL_DELTA
- [ ] T033 [US2] Extend SupabaseStore in src/state/supabase_store.py: add feed_state upsert (ETag, Last-Modified, last_checked_at) and get_last_aggregate() to retrieve prior sentiment aggregate for delta comparison
- [ ] T034 [US2] Add `start-monitor` command to src/cli.py using Typer: starts APScheduler event loop, logs startup to state log, runs until interrupted
- [ ] T035 [US2] Make all T030–T031 tests pass; confirm Red→Green for each test file

**Checkpoint**: User Stories 1 and 2 both independently functional.

---

## Phase 5: User Story 3 — Audit Trail Review (Priority: P3)

**Goal**: User can query the persistent state log to review all pipeline actions
with timestamps, reasoning, and allocation details.

**Independent Test**: After ≥1 pipeline run, execute `python -m src.cli logs
--last-n 20`; output shows structured entries with timestamps for PIPELINE_STARTED,
MACRO_INGESTION_COMPLETE, SENTIMENT_SCORED, ALLOCATION_GENERATED, TELEGRAM_SENT.

### Tests for User Story 3 (write first — MUST fail before implementing)

> **NOTE: Write these tests FIRST and confirm they FAIL before T037**

- [ ] T036 [P] [US3] Write failing integration tests for state log completeness in tests/integration/test_state_log.py: run mock pipeline, assert NDJSON file contains entries for every ActionType in the on-demand flow in correct order, assert StateLogEntry written before Telegram dispatch

### Implementation for User Story 3

- [ ] T037 [US3] Add `logs` command to src/cli.py using Typer: --last-n INT (default 20), --run-id STR, --action-type STR filters; reads STATE_LOG_PATH NDJSON file, pretty-prints matching entries as table or JSON (--format flag)
- [ ] T038 [US3] Audit src/pipeline/orchestrator.py and src/pipeline/stages.py: verify StateLogEntry is written for every ActionType defined in data-model.md; add any missing log writes; confirm state log write always precedes Telegram call (Principle VI)
- [ ] T039 [US3] Make T036 tests pass; confirm Red→Green

**Checkpoint**: All three user stories independently functional and auditable.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hardening, documentation, and reliability improvements across all stories.

- [ ] T040 [P] Write quickstart.md in specs/001-investment-guidance-pipeline/quickstart.md: prerequisites (Python 3.12, API keys), environment setup (.env template), Supabase schema setup, running run-pipeline, running start-monitor, reading logs
- [ ] T041 Harden TelegramAdapter in src/adapters/telegram_adapter.py: 2 retries with exponential backoff, write TELEGRAM_FAILED StateLogEntry on final failure, ensure failed delivery does not crash the pipeline
- [ ] T042 [P] Add token-bucket rate limiter for Finnhub in src/adapters/finnhub_adapter.py: enforce ≤60 req/min across all tickers, queue overflow with sleep-based backoff, log API_ERROR with retry count on 429 responses
- [ ] T043 [P] Add daily request counter for Alpha Vantage in src/adapters/alphavantage_adapter.py: track calls in Supabase feed_state or in-memory, emit WARNING log at 60/75 calls, gracefully skip AV calls when limit reached and fall back to Finnhub-only
- [ ] T044 [P] Write README.md at repository root: project overview, quick start (5 steps), configuration reference table of all env vars, architecture diagram (text-based), licence
- [ ] T045 [P] Add `status` command to src/cli.py: reads last PipelineRun from Supabase, prints run_id, status, started_at, completed_at, shortlist_count, allocation_count, telegram_sent
- [ ] T046 Run full test suite (pytest -v); fix any remaining failures; ensure all contract, integration, and unit tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 complete — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependency on US2 or US3
- **US2 (Phase 4)**: Depends on Phase 2 — no dependency on US1 (shares adapters only)
- **US3 (Phase 5)**: Depends on Phase 2 and benefits from US1 existing for real log data
- **Polish (Phase 6)**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no US dependency
- **US2 (P2)**: Can start after Phase 2 — reuses Reddit/RSS adapters from US1 if complete, otherwise implements independently via base class
- **US3 (P3)**: Can start after Phase 2 — `logs` CLI and log audit are independent of US1/US2 features

### Within Each User Story

- Tests MUST be written and confirmed failing BEFORE implementation tasks
- Models (T007) before services (T019, T022, T023...)
- Services before orchestrator (T027)
- Orchestrator before CLI command (T028)
- Implementation tasks before Green phase (T029, T035, T039)

### Parallel Opportunities

All [P]-marked tasks within a phase can run concurrently:
- T003, T004 (Phase 1 setup) — parallel
- T007, T010, T011, T012 (Phase 2) — parallel
- T013, T014, T015 (US1 tests) + T017, T018, T020, T021, T026 (US1 adapters) — parallel
- T030 + T031 (US2 tests) — parallel
- T040, T042, T043, T044, T045 (Polish) — parallel

---

## Parallel Execution Example: User Story 1

```bash
# After Phase 2 complete, launch US1 test-writing in parallel:
Task: "Write failing unit tests for SentimentService in tests/unit/test_sentiment_service.py"  # T013
Task: "Write failing unit tests for BarbellService in tests/unit/test_barbell_service.py"      # T014
Task: "Write failing unit tests for AllocationService in tests/unit/test_allocation_service.py" # T015

# After tests confirmed failing, launch adapter implementations in parallel:
Task: "Implement RedditAdapter in src/adapters/reddit_adapter.py"       # T017
Task: "Implement RSSAdapter in src/adapters/rss_adapter.py"             # T018
Task: "Implement FinnhubAdapter in src/adapters/finnhub_adapter.py"     # T020
Task: "Implement AlphaVantageAdapter in src/adapters/alphavantage_adapter.py" # T021
Task: "Implement TelegramAdapter in src/adapters/telegram_adapter.py"   # T026
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Write and confirm failing tests T013–T016
4. Complete Phase 3: User Story 1 (T017–T028)
5. Make tests pass (T029)
6. **STOP and VALIDATE**: `run-pipeline --capital 10000` → Telegram received
7. Deploy/use if ready

### Incremental Delivery

1. Setup + Foundational → base ready
2. US1 complete → run-pipeline works end-to-end → **ship and use**
3. US2 complete → add start-monitor → automated alerts live
4. US3 complete → add logs → full audit capability
5. Polish → harden for long-running production use

### Parallel Team Strategy (if applicable)

After Phase 2:
- Developer A: US1 (pipeline core, on-demand analysis)
- Developer B: US2 (monitor service, APScheduler)
- (US3 is small enough to be done sequentially after US1)

---

## Notes

- [P] tasks = different files, no shared state dependencies
- [Story] label maps each task to its user story for traceability
- Tests MUST fail before implementation — no exceptions (Principle III)
- Every state log write MUST precede any Telegram call (Principle VI)
- External providers MUST be accessed via adapter interfaces only (Principle II)
- Commit after each task or logical group
- Stop at any checkpoint to validate the story independently before continuing
