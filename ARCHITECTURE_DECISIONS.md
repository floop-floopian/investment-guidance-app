# Architecture Decisions

Living log of decisions made on this project, why, and what was ruled out. Newest at top.

## Phase 2A — Tenant Isolation

| # | Decision | Choice | Why | Ruled out |
|---|---|---|---|---|
| 5 | Secrets storage | Deferred, not built in 2A | BYO API key feature is unconfirmed (depends on 2C tier design) — building vault infra for a feature that may not ship is speculative | Supabase Vault / KMS now |
| 4 | Historical data ownership | Backfill existing rows to one bootstrap account after first real login | RLS makes ownerless rows invisible once enabled — old Phase 1 data needs an explicit owner or it's lost from view | Leaving old rows unowned |
| 3 | RLS bypass boundary | Pipeline/scheduler writes use the service role key (trusted system, bypasses RLS); any user-facing read uses anon key + that user's session JWT | Keeps a clear, auditable line between "system writes" and "user reads" — sloppy service-role use elsewhere would make RLS decorative | Service role key everywhere for simplicity |
| 2 | Isolation granularity | `user_id` only on `pipeline_runs` and `allocations`. `macro_signals`/`stocks` stay shared/global | Signal generation and stock analysis are identical for every user on a given day — isolating them would multiply LLM/API cost per signup for no benefit | `user_id` on every table |
| 1 | Auth provider | Supabase Auth, using its built-in Discord OAuth provider | RLS policy `user_id = auth.uid()` only populates correctly under Supabase-issued sessions; hand-rolled OAuth would silently break it. Also collapses Phase 2B into a config flip instead of a custom OAuth build | Hand-rolled Discord OAuth + custom JWT |

## Phase 1 — Core Pipeline

| # | Decision | Choice | Why | Ruled out |
|---|---|---|---|---|
| 3 | Notification channel | Discord Bot API | Free indefinitely, no template-approval friction, multi-user DM support out of the box | Telegram (chat-ID UX broke for non-technical users), WhatsApp (no genuinely free official path) |
| 2 | LLM provider | Groq (`llama-3.3-70b-versatile`) | Free tier sufficient for sentiment scoring + reasoning generation at this scale | Anthropic API (paid, not required for a portfolio-stage build) |
| 1 | External integrations | Adapter pattern (`FinancialDataProvider`, `MacroSignalProvider`, `NotificationProvider`) | Lets any provider swap (Discord→Slack, Alpha Vantage→yfinance) without touching pipeline/business logic | Direct SDK calls inline in services |
