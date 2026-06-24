# Feature Specification: Investment Guidance Pipeline

**Feature Branch**: `001-investment-guidance-pipeline`

**Created**: 2026-06-03

**Status**: Draft

**Input**: User description: "Investment Guidance App. Ingests macro trends from Reddit and RSS, scores sentiment, runs fundamental and technical analysis on stocks via Finnhub/Alpha Vantage, applies barbell strategy filter, generates risk-reward scored stock shortlist with per-stock reasoning, accepts user's available capital and allocates across recommendations with reasoning per allocation, runs recurring news checks, logs actions to state file, sends Telegram notifications for critical actions."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - On-Demand Analysis & Allocation (Priority: P1)

A user provides their available capital and triggers the pipeline. The system
ingests the latest macro signals from Reddit and RSS, scores market sentiment,
runs fundamental and technical analysis on the configured stock universe,
applies the barbell strategy filter, and returns a risk-reward scored shortlist.
For each stock on the shortlist the system provides reasoning. The system then
allocates the user's capital across the recommended positions, with a written
rationale for each allocation. The full result is sent to the user via Telegram.

**Why this priority**: This is the core value proposition of the app. Everything
else depends on this working end-to-end.

**Independent Test**: User runs the pipeline with a capital figure (e.g., $10,000).
System completes analysis and delivers a Telegram message containing a shortlist
of ≥1 stock with a risk-reward score, per-stock reasoning, and a capital
allocation table with rationale. No prior state required.

**Acceptance Scenarios**:

1. **Given** the user provides $10,000 as available capital,
   **When** the pipeline is triggered,
   **Then** the system delivers a Telegram notification containing a shortlist
   of stocks with risk-reward scores, per-stock reasoning, and a capital
   allocation breakdown that sums to ≤ $10,000.

2. **Given** macro sentiment is predominantly bearish (e.g., negative Reddit
   and RSS signals),
   **When** the pipeline runs,
   **Then** the barbell filter increases weighting toward safe-core positions
   and the allocation reasoning reflects the bearish context.

3. **Given** no stocks pass the barbell strategy filter thresholds,
   **When** the pipeline completes,
   **Then** the system sends a Telegram notification explaining that no
   qualifying positions were found rather than forcing invalid recommendations.

---

### User Story 2 - Recurring News Monitoring & Alerts (Priority: P2)

The system runs on a configurable schedule, continuously re-ingesting macro
news from Reddit and RSS. When a critical signal is detected (significant
sentiment shift, breaking macro event), the system sends a Telegram alert
immediately without waiting for the next scheduled full analysis run.

**Why this priority**: Timely alerts allow the user to act on market-moving
events. Without this, the app is only useful when manually triggered.

**Independent Test**: Configure the scheduler for a short interval (e.g., 5 min).
Wait for a news cycle. Verify a Telegram message is received when a high-scoring
signal is detected. The message should include the signal summary and source.

**Acceptance Scenarios**:

1. **Given** the recurring monitor is running,
   **When** a macro news item scores above the critical threshold,
   **Then** a Telegram notification is sent within 60 seconds of detection,
   containing the signal summary, source, and sentiment score.

2. **Given** the monitor has run multiple cycles,
   **When** reviewing the state log,
   **Then** each cycle's inputs, signal scores, and outcomes are recorded
   with timestamps.

3. **Given** no critical signals appear during a monitoring cycle,
   **When** the cycle completes,
   **Then** no Telegram notification is sent and the cycle is logged as
   "no action required."

---

### User Story 3 - Audit Trail Review (Priority: P3)

The user can review the persistent state log to understand every action the
system has taken: what signals were ingested, what scores were assigned, which
stocks were analyzed, what allocations were proposed, and what notifications
were sent — all with timestamps.

**Why this priority**: Accountability and debugging. Users need to understand
the system's reasoning over time, especially after a bad recommendation.

**Independent Test**: After running the pipeline at least once, inspect the
state log file. Verify it contains structured, human-readable entries for
each pipeline action with timestamps.

**Acceptance Scenarios**:

1. **Given** the pipeline has run at least once,
   **When** the user opens the state log file,
   **Then** entries exist for macro ingestion, sentiment scoring, stock
   analysis, barbell filtering, shortlist generation, capital allocation,
   and Telegram dispatch — each with an ISO timestamp.

2. **Given** a prior run produced a stock recommendation,
   **When** the user reviews that run's log entry,
   **Then** the per-stock reasoning and allocation rationale used in that
   run are preserved verbatim in the log.

---

### Edge Cases

- What happens when Reddit or an RSS feed is unreachable during ingestion?
  System MUST proceed with available sources and note the failure in the state log.
- What happens when Finnhub/Alpha Vantage API rate limits are hit?
  System MUST respect rate limits, queue remaining requests, and complete
  analysis on a delay rather than failing the run.
- What happens when available capital is less than the minimum position size
  across all recommendations?
  System MUST notify the user that no allocations can be made at the given
  capital level and suggest minimum required capital.
- What happens when Telegram delivery fails?
  System MUST log the failure and retry at least once before marking the
  notification as undelivered in the state log.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST ingest macro trend content from a configured list of
  Reddit subreddits on each pipeline run.
- **FR-002**: System MUST ingest macro trend content from a configured list of
  RSS feed URLs on each pipeline run.
- **FR-003**: System MUST score macro sentiment (bullish / neutral / bearish)
  per ingested item and produce an aggregate sentiment signal.
- **FR-004**: System MUST run fundamental analysis on each stock in the
  configured universe using Finnhub and/or Alpha Vantage APIs.
- **FR-005**: System MUST run technical analysis (price momentum, trend
  indicators) on each stock in the configured universe.
- **FR-006**: System MUST apply a barbell strategy filter that classifies each
  stock as safe-core (low-volatility, value) or satellite (high-conviction,
  asymmetric upside) based on configurable thresholds.
- **FR-007**: System MUST generate a risk-reward scored shortlist containing
  only stocks that pass the barbell filter, with a reasoning string per stock.
- **FR-008**: System MUST accept the user's available capital as an input
  parameter (CLI argument or prompt).
- **FR-009**: System MUST allocate the user's capital across shortlisted
  positions according to the barbell strategy weighting, with a written
  rationale for each allocation.
- **FR-010**: System MUST run recurring macro news checks on a schedule that
  adapts to the volatility tier of monitored stocks. High-volatility (high-beta)
  stocks MUST be checked more frequently than low-volatility safe-core positions.
  Three configurable intervals apply: MONITOR_INTERVAL_HIGH_VOL,
  MONITOR_INTERVAL_MED_VOL, MONITOR_INTERVAL_LOW_VOL.
- **FR-011**: System MUST append a structured log entry to a persistent state
  file for every significant action taken (ingestion, scoring, analysis,
  allocation, notification).
- **FR-012**: System MUST send a Telegram message for: completed on-demand
  analysis results, critical macro signal detections, and allocation proposals.
- **FR-013**: System MUST handle API failures gracefully — logging errors,
  retrying where appropriate, and completing the run with partial data rather
  than crashing.

### Key Entities

- **MacroSignal**: source type (Reddit/RSS), source identifier, raw content
  summary, sentiment score (-1.0 to +1.0), timestamp.
- **Stock**: ticker symbol, fundamental metrics (P/E, revenue growth, debt ratio,
  etc.), technical indicators (momentum, moving averages, RSI), barbell
  classification, risk-reward score, reasoning text.
- **Allocation**: stock ticker, allocated capital amount, percentage of total
  capital, rationale text.
- **PipelineRun**: run ID, trigger type (on-demand / scheduled), timestamp,
  capital input, shortlist produced, allocations produced, notifications sent.
- **StateLogEntry**: run ID, action type, timestamp, payload (JSON-serializable
  details of the action).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On-demand pipeline completes end-to-end (ingestion through
  Telegram delivery) within 5 minutes of being triggered.
- **SC-002**: Telegram notifications for critical signals are delivered within
  60 seconds of signal detection.
- **SC-003**: Every pipeline run produces a complete, human-readable state log
  entry covering all major actions in that run.
- **SC-004**: Capital allocation totals never exceed the user's stated available
  capital.
- **SC-005**: The system processes a stock universe of up to 50 tickers per run
  without exceeding API rate limits (through queuing/backoff).
- **SC-006**: Recurring monitor runs continuously for 24 hours without crashing
  or requiring manual intervention.

---

## Assumptions

- The app runs as a command-line tool (not a web service or mobile app) in its
  initial version.
- The stock universe is user-defined via a configuration file (list of tickers);
  no auto-discovery of stocks in scope.
- Default Reddit subreddits are r/investing, r/stocks, and r/economics
  (conservative macro signal, low noise). The list is user-configurable.
- Barbell strategy weighting defaults to 60% safe-core / 40% satellite
  allocation of capital; this is configurable via BARBELL_SAFE_CORE_RATIO env
  var. Barbell classification thresholds are also configurable. Both will be
  exposed as UI controls in Phase 2 (React frontend).
- "Critical signal" for Telegram alert is defined as: aggregate sentiment score
  shifting by more than a configurable threshold (e.g., ±0.3) within a single
  monitoring cycle.
- This is a single-user, single-portfolio tool. No multi-user support or
  authentication is required.
- The state file is a newline-delimited JSON (NDJSON) or structured JSON file
  stored locally; no remote database required for initial version.
- Finnhub and Alpha Vantage API keys are provided via environment variables or
  a local config file; no key management UI is required.
- Allocation and per-stock reasoning is generated by an LLM (Claude API),
  producing natural-language rationale. Claude API key is provided via
  environment variable.
- Telegram delivery uses a bot token and a single configured chat ID (one
  destination per deployment).
- The scheduler for recurring checks is a simple time-based loop (e.g., cron
  or sleep interval) — not a distributed job queue.
