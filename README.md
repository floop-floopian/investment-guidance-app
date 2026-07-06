# Investment Guidance App

Single-user investment guidance pipeline: ingests macro sentiment from Reddit
and RSS, analyses stocks via Finnhub/Alpha Vantage, applies a barbell strategy
filter, and delivers LLM-reasoned recommendations and capital allocations via
Discord.

> **Disclaimer**: This is a proof-of-concept engineering portfolio project.
> It surfaces data and model-generated reasoning (e.g. "this stock passed the
> barbell filter," "aggregate sentiment shifted") using best-effort,
> potentially delayed or incomplete data from third-party APIs. It does not
> provide financial advice, and no real financial services are offered. Do
> not use this to make actual investment decisions.

## Quick Start (5 steps)

```bash
# 1. Create virtual environment
python3.12 -m venv .venv && source .venv/bin/activate

# 2. Install
pip install -e .

# 3. Configure
cp .env.example .env   # fill in API keys

# 4. Set up Supabase schema
# Paste supabase/migrations/001_initial_schema.sql into Supabase SQL Editor and run

# 5. Run
investment-guidance run-pipeline --capital 10000
```

## Commands

| Command | Description |
|---------|-------------|
| `run-pipeline --capital N` | On-demand analysis and allocation |
| `start-monitor` | Recurring macro news monitor (runs until Ctrl+C) |
| `logs [--last-n N] [--run-id R] [--action-type A]` | Query audit log |
| `status` | Show last pipeline run |

## Architecture

```
Reddit / RSS
     │
     ▼
[RedditAdapter] [RSSAdapter]     ← MacroSignalProvider (adapter pattern)
     │
     ▼
[SentimentService] ──────────── Groq API (batch scoring)
     │
     ▼
[FinnhubAdapter] [AlphaVantageAdapter]  ← FinancialDataProvider
     │
     ▼
[AnalysisService] → assembles Stock entities
     │
     ▼
[BarbellService] → classifies SAFE_CORE / SATELLITE / EXCLUDED
     │
     ▼
[ShortlistService] → risk-reward scored + Groq reasoning
     │
     ▼
[AllocationService] → 60/40 capital split + Groq rationale
     │
     ▼
[StateLogWriter] → NDJSON + Supabase   ← written BEFORE Discord
     │
     ▼
[DiscordAdapter] → delivers notification
```

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | — | Groq API key |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model name |
| `FINNHUB_API_KEY` | — | Finnhub API key |
| `ALPHA_VANTAGE_API_KEY` | — | Alpha Vantage key |
| `REDDIT_CLIENT_ID` | — | Reddit app client ID |
| `REDDIT_CLIENT_SECRET` | — | Reddit app secret |
| `REDDIT_USER_AGENT` | `investment-guidance-app/0.1` | Reddit user agent |
| `REDDIT_SUBREDDITS` | `["investing","stocks","economics"]` | Subreddits to poll |
| `DISCORD_BOT_TOKEN` | — | Discord bot token (DMs active users listed in Supabase `users` table) |
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_KEY` | — | Supabase anon/service key |
| `STATE_LOG_PATH` | `~/.investment-guidance/state.ndjson` | Local audit log path |
| `STOCK_TICKERS` | `[]` | JSON list of tickers to analyse |
| `RSS_FEED_URLS` | `[]` | JSON list of RSS feed URLs |
| `BARBELL_SAFE_CORE_RATIO` | `0.60` | Safe-core capital fraction (0–1) |
| `CAPITAL_MIN_POSITION_USD` | `500` | Minimum position size |
| `SENTIMENT_CRITICAL_DELTA` | `0.3` | Sentiment shift to trigger alert |
| `MONITOR_INTERVAL_HIGH_VOL_MINUTES` | `15` | Monitor interval for high-beta stocks |
| `MONITOR_INTERVAL_MED_VOL_MINUTES` | `30` | Monitor interval for mid-beta stocks |
| `MONITOR_INTERVAL_LOW_VOL_MINUTES` | `60` | Monitor interval for low-beta stocks |

## Licence

MIT
