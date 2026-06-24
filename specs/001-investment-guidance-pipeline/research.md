# Research: Investment Guidance Pipeline

**Feature**: `001-investment-guidance-pipeline`
**Date**: 2026-06-03
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## Decision 1: LLM Framework

**Decision**: Raw Anthropic SDK (`anthropic` Python package, `claude-sonnet-4-6`)
— no LangChain.

**Rationale**: LangChain adds abstraction overhead for a single-provider,
single-model use case. The direct SDK is simpler (Principle V — YAGNI), has
better type safety, lower dependency surface, and easier to debug. Prompt
caching via the Anthropic SDK also reduces per-run cost significantly for the
repeated system-prompt pattern used in sentiment scoring.

**Alternatives considered**:
- LangChain — rejected: over-abstraction for one provider, frequent breaking
  changes, heavier dependency footprint.
- OpenAI-compatible proxy — rejected: no benefit over direct Anthropic SDK.

---

## Decision 2: Reddit Ingestion

**Decision**: PRAW with script-type OAuth2 credentials; polling top posts from
`r/investing`, `r/stocks`, `r/economics` per run (configurable subreddits).

**Rationale**: PRAW is the official Python Reddit wrapper, handles rate
limiting internally (60 req/min), and supports fetching `hot` and `new` feeds
cleanly. Script-type auth is appropriate for single-user personal use without
a redirect URI.

**Defaults**: Fetch top 25 `hot` posts per subreddit per pipeline run.
Post title + selftext fed to sentiment scorer; comments excluded in Phase 1.

**Alternatives considered**:
- Pushshift API — deprecated and unreliable.
- Raw Reddit API via `httpx` — more code for equivalent result.
- Reddit RSS endpoints — limited data, no auth, frequently rate-limited.

---

## Decision 3: RSS Ingestion

**Decision**: `feedparser` with conditional GET (ETag + Last-Modified headers)
to avoid re-processing unchanged feeds.

**Rationale**: feedparser handles RSS 1.0/2.0 and Atom, gracefully manages
encoding issues, and is well-maintained. Conditional GET reduces bandwidth and
avoids duplicate entries across monitor cycles. Feed URLs are user-configured
(no defaults — financial RSS varies widely by user preference).

**Caching strategy**: Store ETag/Last-Modified per feed URL in Supabase
`feed_state` table between monitor cycles.

**Alternatives considered**:
- `httpx` + `lxml` — full control but more code for same result.
- Commercial RSS aggregator APIs — adds a third-party dependency for something
  feedparser handles natively.

---

## Decision 4: Financial Data Provider

**Decision**: Finnhub as primary; Alpha Vantage as secondary/fallback. Both
accessed via the adapter pattern (swappable per Principle II).

**Rationale**:
- Finnhub free tier: real-time quotes, basic financials, company profile,
  earnings — sufficient for fundamental analysis at ≤50 tickers.
- Alpha Vantage free tier: technical indicators (RSI, MACD, SMA) and extended
  fundamentals — complements Finnhub.
- Adapter pattern: `FinancialDataProvider` abstract class; both implement it;
  config selects primary and fallback.

**Finnhub calls per run (≤50 tickers)**:
- `GET /stock/profile2` × 50 — company metadata
- `GET /quote` × 50 — real-time price
- `GET /stock/metric` × 50 — fundamental metrics
- Total: ~150 calls; at 60/min limit → ~2.5 min with rate-limiting backoff.

**Alternatives considered**:
- Yahoo Finance (yfinance) — unofficial, TOS concerns, unreliable.
- Polygon.io — requires paid tier for real-time data.
- IEX Cloud — deprecated free tier.

---

## Decision 5: Scheduler

**Decision**: APScheduler `AsyncIOScheduler` with interval triggers.

**Rationale**: Already in the constitution's tech stack. Integrates naturally
with Python's asyncio event loop (used by FastAPI + PRAW). Supports persistent
job stores (SQLAlchemy backend → Supabase Postgres) so jobs survive restarts.
Simple API for interval-based and cron-based triggers.

**Monitor cycle**: Default interval 60 minutes (user-configurable). On each
cycle: ingest new macro content → score sentiment → if delta > threshold,
trigger alert flow.

**Alternatives considered**:
- Celery — overkill for single-user; adds Redis/RabbitMQ dependency.
- Python `schedule` library — doesn't integrate with asyncio.
- OS cron — less control from within the app; harder to manage state.

---

## Decision 6: Sentiment Scoring Strategy

**Decision**: Claude API (`claude-sonnet-4-6`) with structured JSON output.
Single batched prompt per pipeline run sends all ingested titles/summaries and
returns per-item sentiment scores + an aggregate signal.

**Rationale**: LLM-based scoring handles financial jargon, sarcasm, and
context better than lexicon-based approaches (VADER, TextBlob). Structured
output (JSON with score + brief label) makes downstream processing deterministic.
Prompt caching on the system prompt reduces cost for recurring monitor cycles.

**Prompt structure**:
```
System: You are a financial sentiment analyzer. Return valid JSON only.
User: Score each of the following macro news items on a scale of -1.0 (bearish)
to +1.0 (bullish). Return: {"items": [{"id": ..., "score": ..., "label": ...}],
"aggregate": ..., "summary": "..."}
[batch of titles/summaries]
```

**Alternatives considered**:
- VADER — fast but poor accuracy for financial text (no sarcasm, jargon handling).
- FinBERT (HuggingFace) — good accuracy but adds local model download; slower
  cold start; inference cost on CPU.
- TextBlob — general-purpose, low financial accuracy.

---

## Decision 7: Barbell Strategy Classifier

**Decision**: Rule-based classifier with configurable thresholds; LLM provides
reasoning text only — not the classification decision.

**Rationale**: Deterministic, auditable, easily tuned without retraining.
Classification logic is pure Python (no API cost). Claude API generates the
"why" explanation after classification.

**Default thresholds**:
- **Safe-core** (≥1 qualifier): beta ≤ 0.8, P/E ≤ 20, dividend yield ≥ 1.5%,
  market cap ≥ $10B
- **Satellite** (≥2 qualifiers): 90-day momentum ≥ 15%, RSI 40–70, strong
  positive macro sentiment signal (aggregate ≥ 0.3), analyst consensus ≥ 4.0/5

**Capital allocation defaults**: 60% safe-core / 40% satellite (user-configurable via BARBELL_SAFE_CORE_RATIO; UI-configurable in Phase 2).

**Alternatives considered**:
- ML classifier — overkill, requires labeled training data, black-box.
- Pure LLM classification — non-deterministic, harder to audit, higher cost.

---

## Decision 8: State Log Format

**Decision**: Local NDJSON file (append-only) as primary audit log; Supabase
Postgres as queryable secondary store. Both written atomically per action.

**Rationale**: NDJSON is append-only (no corruption from interrupted writes),
human-readable with `jq`, portable (file copy = full audit trail). Supabase
enables queries like "show all BUY recommendations for AAPL" without parsing
the log file. Local file is the source of truth per Principle VI.

**Write order per action** (enforced by `log_writer.py`):
1. Append to local NDJSON file
2. Upsert to Supabase (non-blocking, best-effort)
3. Send Telegram notification (if applicable)

**Alternatives considered**:
- SQLite local only — not in tech stack; adds a second ORM; Supabase already
  handles persistence.
- Only Supabase — violates offline operation and Principle VI (local log is
  source of truth).

---

## Decision 9: CLI Framework

**Decision**: `Typer` (built on Click).

**Rationale**: Modern Python CLI framework, native Pydantic/type-hint
integration, auto-generates help text, minimal boilerplate. FastAPI also uses
Pydantic, so types are shared naturally across CLI and API layers.

**Alternatives considered**:
- `argparse` — verbose, no type inference.
- Click directly — Typer is Click with better ergonomics.
- `fire` — too magical, poor help generation.

---

## Decision 10: Capital Allocation Algorithm

**Decision**: Proportional weighting within barbell bands, then LLM generates
rationale.

**Algorithm**:
1. Classify shortlisted stocks into safe-core / satellite bands.
2. Allocate 60% of capital to safe-core band, 40% to satellite (configurable via BARBELL_SAFE_CORE_RATIO).
3. Within each band: weight by risk-reward score (normalized to sum to 1.0).
4. Enforce minimum position size ($500 default, configurable); remove
   positions below minimum and reallocate.
5. Pass allocation table + stock data to Claude API → returns per-position
   and overall rationale text.

**Alternatives considered**:
- Equal weighting — simpler but ignores risk-reward signal.
- Kelly criterion — mathematically optimal but requires probability estimates
  not reliably available from the data sources.
- Pure LLM allocation — non-deterministic; amounts could vary across identical
  runs. Rule-based math first, LLM explains only.
