# Phase 2 Roadmap: Multi-Tenant Platform & Unit Economics

**Status**: Proposed — not yet implemented
**Builds on**: Phase 1 (`specs/001-investment-guidance-pipeline/`) — single-user CLI/service, proven end-to-end pipeline (macro sentiment → barbell classification → shortlist → allocation → Discord delivery)

## Why This Phase Exists

Phase 1 deliberately scoped out multi-user support (Constitution Principle IV — YAGNI until the core pipeline is proven). It succeeded at that: the signal-generation logic works end-to-end. But two things are now true:

1. The `DiscordAdapter` already queries a `users` table for *multiple* active recipients — multi-tenant-shaped code that shipped ahead of a multi-tenant schema, because Phase 1 never needed one. That gap is a bug today, not a future concern.
2. Turning this into something with subscribers means the "informational, not financial advice" posture (see disclaimer note below) has to be backed by real technical isolation, not just a README caveat.

This document is the direct answer to both. Specifically, it's the rebuttal to three criticisms of the current state:

| Criticism (of Phase 1 as-is) | Neutralized by |
|---|---|
| "There's no tenant isolation — every table is keyed by `run_id`, not `user_id`" | Phase 2A |
| "Discord recipients come from a `users` table that was never given a real onboarding flow" | Phase 2B |
| "A subscription model was mentioned with no cost model behind the price" | Phase 2C |

None of this is retroactive — it's why the critique applies to Phase 1 *today* and stops applying once 2A–2C ship.

---

## Phase 2A — Tenant Isolation & Data Model

**Problem**: `pipeline_runs`, `stocks`, `allocations`, `macro_signals`, and `state_log` have no `user_id` column. There is no `users` table in the migration at all, despite `discord_adapter.py` querying one. Nothing in the current schema could enforce that User A can't read User B's capital, allocations, or API usage.

**Scope**:
- Add a `users` table: `id`, `discord_user_id`, `email`, `plan_tier`, `is_active`, `created_at`.
- Add `user_id` (FK → `users.id`) to every existing table that currently only has `run_id`.
- Enable Supabase Row-Level Security (RLS) on every table, policy: `user_id = auth.uid()`. No table is queryable cross-tenant, including from the service role key in application code paths that serve user-facing reads.
- Move per-user secrets (BYO premium API keys, if offered — see 2C) into an encrypted vault (Supabase Vault or a KMS-encrypted column), never plaintext in a shared `.env`. The current single shared `discord_bot_token` remains fine for the bot's own token — it's *user* secrets that need per-tenant encryption, not the bot's own credential.
- Backfill migration: existing Phase 1 rows get a single `user_id` representing the original single-user account, so no history is lost.

**Why it's cheap relative to its payoff**: this is schema + RLS policy work, not new business logic. The adapter pattern (Constitution Principle II) means `FinancialDataProvider`/`MacroSignalProvider`/`NotificationProvider` interfaces don't change — only what gets passed into their queries (a `user_id` instead of an implicit global scope).

---

## Phase 2B — Discord OAuth Account Linking

**Problem**: today, getting into the `users` table (once it exists) would mean manually inserting a `discord_user_id` — there's no user-facing way to link a Discord account to the app.

**Scope**:
- Discord OAuth2 (`identify` scope) login flow, fronted by a minimal FastAPI endpoint (already a listed dependency, currently unused — `fastapi`, `uvicorn` in `pyproject.toml`).
- On successful OAuth callback: upsert into `users`, mark `is_active = true`, store `discord_user_id`.
- `DiscordAdapter.send_message` continues to work exactly as today (DM per active user) — this phase only fixes *how* a user gets into that table, not the delivery mechanism.
- Unlink/deactivate flow (sets `is_active = false`) so a user can opt out without a support ticket.

**Explicitly not in scope for 2B**: Discord slash-command interactions, guild-based (server) delivery, or anything beyond DM notification. That's a distinct, larger surface (interaction webhooks, signature verification) and isn't needed to close the current gap.

---

## Phase 2C — Subscription Model & Unit Economics

This is the section that answers "does the price cover the cost, plus margin" — not just "there's a subscription."

### Cost drivers (per active user, monthly)

The figures below are **illustrative placeholders based on each provider's general public pricing shape** — verify current numbers at each provider's pricing page before using these in an interview or a real launch. Treat the *structure* of this table as the deliverable, not the specific dollar figures.

| Cost driver | Free tier | Paid tier (approx.) | Notes |
|---|---|---|---|
| Groq (LLM reasoning) | Generous free-tier request/token allowance | Low per-million-token rate on paid tier | Cost scales with pipeline runs/month × tokens per run (~2–3 calls per run: sentiment batch, shortlist reasoning, allocation rationale) |
| Finnhub | 60 calls/min, delayed data | ~$50+/mo for real-time/extended fundamentals | Shared across all users if using one bot-level key; becomes per-user cost only if users BYO keys |
| Alpha Vantage | Free tier daily request cap (verify current limit — code currently assumes 75/day, some AV plans cap lower) | ~$50+/mo for higher throughput | Same shared-vs-BYO consideration as Finnhub |
| Supabase | Free tier (small DB, limited rows) | Pro ~$25/mo baseline | Fixed cost, amortized across all users, not per-user |
| Discord Bot API | Free | Free | No cost driver |
| Hosting (FastAPI + scheduler) | — | ~$5–20/mo hobby tier | Fixed cost, amortized across all users |

### Unit economics model

```
Fixed monthly cost (Supabase + hosting)     = F
Variable cost per user per month            = (LLM tokens/run × runs/month × $/token)
                                             + (shared API overage risk, if any)
Total cost for N users                      = F + N × Variable
Cost per user                               = F/N + Variable
Price per tier                              = Cost per user / (1 − target gross margin)
```

At low N (e.g., first 20–50 users), `F/N` dominates — the fixed Supabase/hosting cost is the real driver, not the LLM calls. This argues for a **free tier gated by usage frequency** (e.g., on-demand runs only, no recurring monitor) rather than a fully free unlimited tier, since the monitor's recurring polling is what multiplies API calls and cost per user.

### Proposed tiers (structure, not final pricing)

| Tier | What's included | Cost driver exposure | Target |
|---|---|---|---|
| Free | On-demand pipeline runs only, capped per month, Reddit+RSS only | Minimal — bounded by rate cap | Acquisition / portfolio demo |
| Pro | Recurring monitor + Discord alerts, shared API keys | Bot-level Finnhub/AV/Groq usage scales with active user count | Priced to cover `F/N + Variable` at target N, plus margin |
| Premium | + X/Twitter sentiment, + 13F institutional-flow signal | Twitter/X API cost is real and non-trivial — must be priced to cover it directly, not cross-subsidized by Pro tier | Priced to fully cover its own incremental cost driver |

The key discipline: **Premium-tier costs (X/Twitter API) must be priced into the Premium tier itself**, not smeared across all users — otherwise Free/Pro users are subsidizing a feature they don't use, which is the kind of unit-economics mistake that gets caught immediately in a PM interview.

### Required: reasoning-text framing constraint (do not skip this)

Charging money for delivery/tooling is legally different from charging for individualized investment advice — but that distinction lives entirely in *what the product's text says*, not in the disclaimer. "Apple hit its 20-day moving average" is data. "Apple is the best buy today" is advice, and a paid subscription delivering advice-framed text is a materially different regulatory posture (investment-advisor registration territory), disclaimer or not.

This is an engineering requirement for Phase 2C, not a legal footnote:
- Audit every LLM prompt that generates user-facing reasoning text (`shortlist_service.py`'s `_call_llm_reasoning`, `allocation_service.py`'s `_call_llm_rationale`) and constrain the system prompt to data-framed language: report what indicators/signals triggered, not imperative recommendations.
- Add this as an explicit acceptance check before Phase 2C ships: read a sample of generated reasoning text and confirm it reads as "here's what the data shows," never "you should buy/sell X."
- Revisit this specifically if subscription pricing ever moves from "pay for delivery/tooling" toward "pay for the recommendation itself" — that reframing changes the legal analysis regardless of prompt wording.

---

## Phase 2D — Premium Data Sources (contingent, not committed)

Ordered by cost-to-value, cheapest first:

1. **SEC EDGAR 13F filings** (institutional holdings deltas) — free, public, quarterly. Slots into the existing `MacroSignalProvider` adapter interface as one more source. Ship this first regardless of subscription traction — it's free.
2. **X/Twitter sentiment** — gated behind the Premium tier explicitly because of real API cost (see 2C). Do not ship until at least a handful of Premium subscribers justify the fixed API spend.
3. **Crypto / whale-wallet tracking** — not scoped in this phase. Revisit only if (a) Premium tier has validated demand and (b) a user explicitly asks for crypto coverage. On-chain indexing is materially more complex than anything else in this roadmap.

## Explicitly Deferred / Killed (carried over from the Phase 1 roadmap review)

- Location-based money-transfer/execution directions — regulatory exposure (money transmission, broker-dealer registration) outweighs the value; not revisited here.
- Swapping to open-source ML models in place of the current rule-based + LLM-reasoning approach — no stated hypothesis of what's broken with the current approach, no eval framework. Not scoped.
- Full crypto asset coverage beyond the contingent whale-tracking item above — different volatility/classification assumptions than the equity barbell logic.

---

## Success Metrics (North Star)

Carried over from the existing interview-pitch framing (`Product Roadmap/Pitch to Interviews.pdf`), corrected for the current stack (Discord, not Telegram; Groq, not an unnamed LLM):

- **Alert delivery latency** — signal detection to Discord DM delivered (existing SC-002 target: ≤60s).
- **User retention rate** — post-2B, once there's an actual account concept to retain against.
- **API cost per user per month** — the output of the Phase 2C model above; this is the number that should appear on a pricing slide, not a guess.

## Disclaimer Note (carried over, still applies)

This remains a portfolio/engineering project. The README disclaimer added in Phase 1 stays accurate as long as the product surfaces data and reasoning ("aggregate sentiment shifted," "this stock passed the barbell filter") rather than direct personalized buy/sell instructions — see the reasoning-text framing requirement in Phase 2C above, which is what actually keeps this true once the subscription model ships, not the disclaimer text itself.
