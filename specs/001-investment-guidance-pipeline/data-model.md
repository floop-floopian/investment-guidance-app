# Data Model: Investment Guidance Pipeline

**Feature**: `001-investment-guidance-pipeline`
**Date**: 2026-06-03

---

## Entities

### MacroSignal

Represents a single ingested item from Reddit or RSS, with its sentiment score.

| Field           | Type            | Description                                      |
|-----------------|-----------------|--------------------------------------------------|
| `id`            | `str`           | Unique identifier (source:post_id or feed:url:item_id) |
| `source_type`   | `enum`          | `REDDIT` or `RSS`                                |
| `source_id`     | `str`           | Subreddit name or feed URL                       |
| `title`         | `str`           | Post/item title                                  |
| `summary`       | `str \| None`   | Body text or feed description (truncated ≤500 chars) |
| `url`           | `str \| None`   | Source URL                                       |
| `published_at`  | `datetime`      | Original publish timestamp (UTC)                 |
| `ingested_at`   | `datetime`      | When this item was ingested by the pipeline      |
| `sentiment_score` | `float`       | -1.0 (bearish) to +1.0 (bullish)                 |
| `sentiment_label` | `enum`        | `BEARISH`, `NEUTRAL`, `BULLISH`                  |
| `run_id`        | `str`           | Foreign key → PipelineRun.id                     |

**Validation rules**:
- `sentiment_score` must be in range [-1.0, 1.0]
- `ingested_at` must be ≥ `published_at` when both are known
- `source_id` must match a value in the configured sources list

**State transitions**: MacroSignal is immutable after creation.

---

### Stock

Represents a single ticker after analysis and classification. One record per
ticker per pipeline run.

| Field                  | Type            | Description                                   |
|------------------------|-----------------|-----------------------------------------------|
| `ticker`               | `str`           | Stock ticker symbol (e.g., "AAPL")            |
| `company_name`         | `str`           | Full company name                             |
| `price`                | `float`         | Current price (USD) at time of analysis       |
| `market_cap`           | `float \| None` | Market capitalisation (USD)                   |
| `pe_ratio`             | `float \| None` | Price-to-earnings ratio (trailing)            |
| `dividend_yield`       | `float \| None` | Annual dividend yield (%)                     |
| `beta`                 | `float \| None` | 5-year monthly beta vs S&P 500                |
| `revenue_growth_yoy`   | `float \| None` | Year-over-year revenue growth (%)             |
| `debt_to_equity`       | `float \| None` | Total debt / total equity                     |
| `rsi_14`               | `float \| None` | 14-day Relative Strength Index                |
| `sma_50`               | `float \| None` | 50-day simple moving average (USD)            |
| `sma_200`              | `float \| None` | 200-day simple moving average (USD)           |
| `momentum_90d`         | `float \| None` | Price return over 90 days (%)                 |
| `analyst_consensus`    | `float \| None` | Mean analyst rating (1.0–5.0 scale)           |
| `barbell_class`        | `enum`          | `SAFE_CORE`, `SATELLITE`, `EXCLUDED`          |
| `risk_reward_score`    | `float`         | Composite score 0.0–1.0 (higher = better)    |
| `reasoning`            | `str`           | LLM-generated per-stock reasoning text        |
| `data_source`          | `enum`          | `FINNHUB`, `ALPHA_VANTAGE`, `PARTIAL`         |
| `analyzed_at`          | `datetime`      | Timestamp of analysis (UTC)                   |
| `run_id`               | `str`           | Foreign key → PipelineRun.id                  |

**Validation rules**:
- `risk_reward_score` must be in range [0.0, 1.0]
- `barbell_class` = `EXCLUDED` if stock fails to meet thresholds for either band
- `rsi_14` must be in range [0, 100] when present
- At least one of `pe_ratio`, `beta`, `momentum_90d` must be non-null for
  classification (otherwise set `barbell_class = EXCLUDED`)

**Barbell classification thresholds** (defaults, user-configurable):
- `SAFE_CORE`: satisfies ≥1 of: beta ≤ 0.8, P/E ≤ 20, dividend_yield ≥ 1.5%,
  market_cap ≥ $10B
- `SATELLITE`: satisfies ≥2 of: momentum_90d ≥ 15%, RSI 40–70,
  macro aggregate sentiment ≥ 0.3, analyst_consensus ≥ 4.0

---

### Allocation

Represents a single position in the capital allocation output.

| Field           | Type       | Description                                      |
|-----------------|------------|--------------------------------------------------|
| `id`            | `str`      | UUID                                             |
| `ticker`        | `str`      | Stock ticker (references Stock.ticker in same run) |
| `band`          | `enum`     | `SAFE_CORE` or `SATELLITE`                       |
| `amount_usd`    | `float`    | Dollar amount allocated (USD)                    |
| `percentage`    | `float`    | Percentage of total capital (0.0–100.0)          |
| `rationale`     | `str`      | LLM-generated per-allocation rationale text      |
| `run_id`        | `str`      | Foreign key → PipelineRun.id                     |

**Validation rules**:
- `amount_usd` must be ≥ configured minimum position size (default $500)
- Sum of all `amount_usd` for a given `run_id` must be ≤ `PipelineRun.capital_input`
- `percentage` = `amount_usd / PipelineRun.capital_input × 100`

---

### Users (notification recipients)

Supabase-only table (no corresponding Pydantic model) listing Discord accounts
that should receive pipeline notifications. `DiscordAdapter.send_message`
reads all rows with `is_active = true` and DMs each one.

| Field             | Type       | Description                                |
|-------------------|------------|---------------------------------------------|
| `id`              | `uuid`     | Primary key                                 |
| `discord_user_id` | `str`      | Discord snowflake ID for the DM recipient   |
| `is_active`       | `bool`     | Whether this user currently receives alerts |
| `created_at`      | `datetime` | Row creation timestamp                      |

---

### PipelineRun

Top-level record for a single end-to-end pipeline execution.

| Field               | Type       | Description                                      |
|---------------------|------------|--------------------------------------------------|
| `id`                | `str`      | UUID (used as correlation ID across all sub-records) |
| `trigger_type`      | `enum`     | `ON_DEMAND` or `SCHEDULED`                       |
| `started_at`        | `datetime` | Pipeline start timestamp (UTC)                   |
| `completed_at`      | `datetime \| None` | Pipeline end timestamp (null while running) |
| `status`            | `enum`     | `RUNNING`, `COMPLETED`, `FAILED`, `PARTIAL`      |
| `capital_input`     | `float \| None` | User-provided capital (USD); null for monitor-only runs |
| `macro_signal_count` | `int`     | Number of macro signals ingested                 |
| `shortlist_count`   | `int`      | Number of stocks on shortlist (passed barbell filter) |
| `allocation_count`  | `int`      | Number of positions allocated                    |
| `discord_sent`      | `bool`     | Whether Discord notification was dispatched      |
| `error_message`     | `str \| None` | Error detail if status is FAILED or PARTIAL   |

**State transitions**:
`RUNNING` → `COMPLETED` (all stages finished)
`RUNNING` → `PARTIAL` (some stages failed but run continued with partial data)
`RUNNING` → `FAILED` (unrecoverable error)

---

### StateLogEntry

Append-only audit log for every significant system action. Written to local
NDJSON file and Supabase `state_log` table.

| Field        | Type       | Description                                        |
|--------------|------------|----------------------------------------------------|
| `id`         | `str`      | UUID                                               |
| `run_id`     | `str`      | Foreign key → PipelineRun.id                       |
| `action`     | `enum`     | See action types below                             |
| `timestamp`  | `datetime` | UTC timestamp of the action                        |
| `payload`    | `dict`     | JSON-serializable details (varies by action type)  |
| `level`      | `enum`     | `INFO`, `WARNING`, `ERROR`                         |

**Action types**:
| Action                    | Trigger                                      |
|---------------------------|----------------------------------------------|
| `PIPELINE_STARTED`        | Pipeline run begins                          |
| `MACRO_INGESTION_COMPLETE`| Reddit + RSS ingestion finished              |
| `SENTIMENT_SCORED`        | Aggregate sentiment result produced          |
| `ANALYSIS_COMPLETE`       | Fundamental + technical analysis finished    |
| `BARBELL_CLASSIFIED`      | Barbell filter applied, shortlist produced   |
| `ALLOCATION_GENERATED`    | Capital allocation produced                  |
| `DISCORD_SENT`            | Discord notification dispatched              |
| `DISCORD_FAILED`          | Discord delivery failed (with retry count)   |
| `API_ERROR`               | External API call failed (provider, ticker, error) |
| `MONITOR_CYCLE_COMPLETE`  | Scheduled monitor cycle finished (no alert)  |
| `CRITICAL_SIGNAL_DETECTED`| Sentiment delta exceeded threshold           |
| `PIPELINE_COMPLETED`      | Pipeline run finished successfully           |
| `PIPELINE_FAILED`         | Pipeline run failed with error               |

---

### FeedState

Tracks ETag/Last-Modified headers per RSS feed URL to enable conditional GET.

| Field             | Type            | Description                          |
|-------------------|-----------------|--------------------------------------|
| `feed_url`        | `str`           | RSS feed URL (primary key)           |
| `etag`            | `str \| None`   | Last received ETag header            |
| `last_modified`   | `str \| None`   | Last received Last-Modified header   |
| `last_checked_at` | `datetime`      | UTC timestamp of last poll           |

---

## Supabase Table Summary

| Table           | Description                          |
|-----------------|--------------------------------------|
| `pipeline_runs` | PipelineRun records                  |
| `macro_signals` | MacroSignal records per run          |
| `stocks`        | Stock analysis records per run       |
| `allocations`   | Allocation records per run           |
| `state_log`     | StateLogEntry (audit trail)          |
| `feed_state`    | RSS feed ETag/Last-Modified cache    |

All tables include `created_at` timestamp managed by Supabase.
Row-level security (RLS) is disabled in Phase 1 (single-user, no auth).

---

## Local NDJSON State File

Path: `~/.investment-guidance/state.ndjson` (configurable via env var
`STATE_LOG_PATH`).

Each line is a JSON object with all fields from `StateLogEntry`. The file is
append-only — never modified or deleted by the application. Write is atomic
(line written in full before newline appended).
