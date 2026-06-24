# Quickstart: Investment Guidance Pipeline

## Prerequisites

- Python 3.12+
- A Supabase project (free tier works)
- API keys: Anthropic, Finnhub, Alpha Vantage, Reddit app credentials, Telegram Bot

## 1. Environment Setup

```bash
# Clone the repo and create a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

**.env contents**:
```
ANTHROPIC_API_KEY=sk-ant-...
FINNHUB_API_KEY=...
ALPHA_VANTAGE_API_KEY=...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=investment-guidance-app/0.1
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-or-service-key
STATE_LOG_PATH=~/.investment-guidance/state.ndjson
STOCK_TICKERS=["AAPL","MSFT","JNJ","BRK-B","NVDA"]
RSS_FEED_URLS=[]
BARBELL_SAFE_CORE_RATIO=0.60
CAPITAL_MIN_POSITION_USD=500
```

## 2. Supabase Schema Setup

Run the migration against your Supabase project:

1. Open your Supabase dashboard → SQL Editor
2. Paste the contents of `supabase/migrations/001_initial_schema.sql`
3. Run — all 6 tables will be created

## 3. Running the Pipeline (On-Demand)

```bash
investment-guidance run-pipeline --capital 10000
```

Expected output:
```
Starting pipeline with capital $10,000.00...
✓ Pipeline completed — 3 stocks, 3 allocations, Telegram: ✓
```

Check your Telegram — you should receive a message with the shortlist and allocation breakdown.

## 4. Starting the Recurring Monitor

```bash
investment-guidance start-monitor
```

The monitor runs indefinitely (Ctrl+C to stop). It polls Reddit and RSS on the configured interval and sends a Telegram alert when macro sentiment shifts significantly.

## 5. Reading the Audit Log

```bash
# Last 20 entries
investment-guidance logs

# Filter by run
investment-guidance logs --run-id <first-8-chars-of-run-id>

# JSON output for scripting
investment-guidance logs --format json | jq '.action'

# Filter by action type
investment-guidance logs --action-type ALLOCATION_GENERATED
```

## 6. Running Tests

```bash
pytest tests/ -v
```

All 50 tests should pass. No API keys are required — all external adapters are mocked in tests.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No qualifying positions found` | Check STOCK_TICKERS and barbell thresholds in .env |
| Telegram not received | Verify BOT_TOKEN and CHAT_ID; check TELEGRAM_FAILED in logs |
| Alpha Vantage daily limit | Reduce STOCK_TICKERS count or upgrade AV plan |
| Finnhub rate limit errors | Pipeline auto-retries; reduce ticker count if persistent |
| Supabase connection error | State log still works locally; check SUPABASE_URL/KEY |
