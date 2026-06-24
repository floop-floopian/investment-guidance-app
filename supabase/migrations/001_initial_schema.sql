-- Investment Guidance App — initial schema
-- Run this migration against your Supabase project.

-- pipeline_runs: top-level record per pipeline execution
create table if not exists pipeline_runs (
    id              text primary key,
    trigger_type    text not null check (trigger_type in ('ON_DEMAND', 'SCHEDULED')),
    started_at      timestamptz not null,
    completed_at    timestamptz,
    status          text not null check (status in ('RUNNING', 'COMPLETED', 'FAILED', 'PARTIAL')),
    capital_input   numeric,
    macro_signal_count integer not null default 0,
    shortlist_count    integer not null default 0,
    allocation_count   integer not null default 0,
    telegram_sent      boolean not null default false,
    error_message      text,
    created_at      timestamptz not null default now()
);

-- macro_signals: one row per ingested Reddit post or RSS item
create table if not exists macro_signals (
    id              text primary key,
    run_id          text not null references pipeline_runs(id) on delete cascade,
    source_type     text not null check (source_type in ('REDDIT', 'RSS')),
    source_id       text not null,
    title           text not null,
    summary         text,
    url             text,
    published_at    timestamptz,
    ingested_at     timestamptz not null,
    sentiment_score numeric check (sentiment_score >= -1.0 and sentiment_score <= 1.0),
    sentiment_label text check (sentiment_label in ('BEARISH', 'NEUTRAL', 'BULLISH')),
    created_at      timestamptz not null default now()
);

-- stocks: one row per ticker per pipeline run
create table if not exists stocks (
    id                  uuid primary key default gen_random_uuid(),
    run_id              text not null references pipeline_runs(id) on delete cascade,
    ticker              text not null,
    company_name        text,
    price               numeric,
    market_cap          numeric,
    pe_ratio            numeric,
    dividend_yield      numeric,
    beta                numeric,
    revenue_growth_yoy  numeric,
    debt_to_equity      numeric,
    rsi_14              numeric check (rsi_14 >= 0 and rsi_14 <= 100),
    sma_50              numeric,
    sma_200             numeric,
    momentum_90d        numeric,
    analyst_consensus   numeric,
    volatility_tier     text check (volatility_tier in ('HIGH', 'MED', 'LOW')),
    barbell_class       text not null check (barbell_class in ('SAFE_CORE', 'SATELLITE', 'EXCLUDED')),
    risk_reward_score   numeric check (risk_reward_score >= 0.0 and risk_reward_score <= 1.0),
    reasoning           text,
    data_source         text check (data_source in ('FINNHUB', 'ALPHA_VANTAGE', 'PARTIAL')),
    analyzed_at         timestamptz not null,
    created_at          timestamptz not null default now(),
    unique (run_id, ticker)
);

-- allocations: capital allocation per position per run
create table if not exists allocations (
    id          uuid primary key default gen_random_uuid(),
    run_id      text not null references pipeline_runs(id) on delete cascade,
    ticker      text not null,
    band        text not null check (band in ('SAFE_CORE', 'SATELLITE')),
    amount_usd  numeric not null check (amount_usd >= 0),
    percentage  numeric not null check (percentage >= 0 and percentage <= 100),
    rationale   text,
    created_at  timestamptz not null default now()
);

-- state_log: append-only audit trail
create table if not exists state_log (
    id          uuid primary key default gen_random_uuid(),
    run_id      text not null,
    action      text not null,
    timestamp   timestamptz not null,
    level       text not null check (level in ('INFO', 'WARNING', 'ERROR')),
    payload     jsonb not null default '{}',
    created_at  timestamptz not null default now()
);

-- feed_state: ETag / Last-Modified cache per RSS feed
create table if not exists feed_state (
    feed_url        text primary key,
    etag            text,
    last_modified   text,
    last_aggregate  numeric,  -- most recent sentiment aggregate for delta comparison
    last_checked_at timestamptz,
    updated_at      timestamptz not null default now()
);

-- indexes for common query patterns
create index if not exists idx_macro_signals_run_id on macro_signals(run_id);
create index if not exists idx_stocks_run_id on stocks(run_id);
create index if not exists idx_allocations_run_id on allocations(run_id);
create index if not exists idx_state_log_run_id on state_log(run_id);
create index if not exists idx_state_log_action on state_log(action);
create index if not exists idx_state_log_timestamp on state_log(timestamp desc);
