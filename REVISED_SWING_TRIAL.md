# Revised swing checklist — offline trial

This trial is deliberately **not connected to the live dashboard, scanner, configuration, alerts, or orders**. Merging these files does not switch live trading rules. It evaluates supplied evidence and returns an experimental assessment with `trade_eligible: false`, even when all trial checks pass.

## Plain-language stages

1. **Watch:** enough shares trade, the longer trend is rising, and price recently rested in a valid pullback area without breaking support.
2. **Ready to review:** a completed reversal has appeared, price has broken its high and recovered the 20-day average, volume supports the reversal, the selected benchmark supports the trade, and a realistic target offers at least twice the planned risk after assumed costs.
3. **All required checks passed:** supported undervaluation, documented industry financial review, verified earnings outside the holding window, a fresh regular-session quote, and personal loss/cash/allocation limits also pass. This is a checklist result, not a promise of profit or an order.

Missing evidence stays unknown and prevents progression through that stage. Failed discovery is labeled **Not ready for watchlist**.

## Changes under test

| Rule | Trial |
|---|---|
| Average volume | Hard floor of 5 million shares; a higher configured minimum is respected |
| Trend discovery | Rising 50-day average versus five sessions earlier and a higher confirmed swing low |
| Entry recovery | Price above 20-day average, completed reversal and break above its high |
| Pullback | Completed close in 38.2%–61.8% during the last five completed sessions; anchors frozen using only history available at that touch; 50%–61.8% remains a preference |
| Support | No subsequent low or current price below the frozen zone floor minus half the touch-day ATR |
| Volume confirmation | Latest qualifying reversal day's volume versus its own preceding 20 sessions; 1.3× remains the default, not a proven optimal threshold |
| Benchmark | Explicit SPY or QQQ selection, default SPY; matching daily date and nonnegative 20-session relative strength required; the other benchmark is informational |
| Targets | Nearest confirmed historical resistance; a closer daily overhead high constrains available reward; second target is optional |
| Risk | Stop below the latest five-day low by 0.1 ATR; positive risk no greater than 2 ATR; confirmed first target within 4 ATR; no target manufactured to satisfy the rule |
| Reward/risk | At least 2:1 after round-trip per-share cost allowance; stricter configured minimum respected |
| Undervaluation | Positive supported intrinsic estimate above snapshot price; no fallback from missing values |
| Financial review | Documented sector, review policy, source, evidence, date and explicit pass/fail; no universal bank/software ratio equivalence and no automatic waiver |
| Earnings | Verified future event date beyond holding days plus buffer; empty response never passes |
| Sizing | Whole shares limited by uncommitted cash, allocation cash and maximum planned dollar loss |

These are hypotheses for testing. Default cost allowance is **$0.05 per share round trip**, an editable modeling assumption, not a broker fee or estimate of actual execution. Stops and gaps can produce larger losses. Financial and valuation reviews expire after 90 days; verified earnings checks expire after one day. These lifetimes also require validation before any production rollout.

## Input / execution

Run `python revised_swing.py case.json`. All inputs must concern the **same stock**, with a positive finite `price` and complete OHLCV `days` sorted by date. The last day must equal `expected_completed_session`, obtained from an exchange calendar, and precede the date in `as_of`. The trial rejects same-day partial bars. Timestamps require timezones. Output includes every gate and its stage, frozen zone evidence, entry/stop/target, cost-adjusted reward/risk and hypothetical shares.

Required evidence fields:

- `as_of`: timezone-aware assessment timestamp.
- `expected_completed_session`: exchange session date, `YYYY-MM-DD`.
- `days`: at least 65 completed bars, each with `date`, `open`, `high`, `low`, `close`, `volume`.
- `price`: the quote value corresponding to `quote.at`.
- `quote`: `session` (open/closed), `at`, `session_end`.
- `benchmarks.SPY` and/or `benchmarks.QQQ`: `source`, `data_date`, `trend` (Uptrend/Mixed/Downtrend), `relative_strength_pp`. Compute relative strength over the same 20 completed sessions as the stock, using only data available at `as_of`.
- `valuation`: `source`, `checked_at`, `supported` (boolean), `intrinsic_value`.
- `financial_review`: `source`, `checked_at`, `sector`, `policy`, `evidence`, `passed` (boolean). This is an explicitly documented human/validated research result, not inferred from a missing provider field.
- `earnings`: `source`, `checked_at`, `verified` (boolean), `next_date`.
- `sizing`: `cash`, `maximum_loss`, `allocation_cash` (positive dollar amounts).
- Optional `config`: keys/defaults in `revised_swing.DEFAULTS`, including holding period, benchmark and execution-cost assumption.

The module does not download or independently authenticate evidence. Do not populate missing facts with optimistic defaults. Current financial research cannot be substituted for historical financial research in a replay.

## Validation and next step

Unit tests exercise staged eligibility, unsupported/overvalued estimates, missing and expired evidence, earnings boundaries, alternate benchmarks, stale/future quotes, cash/risk sizing, duplicate/incomplete bars, frozen historical touch evaluation, reversal-day volume, and resistance/cost constraints. A passing synthetic scenario is a software test, not a successful historical trade.

**No historical profitability or paper-trading result is claimed.** Before adopting the trial, assemble point-in-time adjusted OHLCV, verified earnings histories, valuation/financial evidence available at each date, and benchmark histories. Compare both rule sets over the same universe and dates, with out-of-sample periods, fees/slippage, gap fills, ambiguous intraday stop/target ordering, delistings, drawdowns and a documented exit policy. Paper-trade prospective signals afterward. Do not enable automatic qualification based only on these unit tests.

The live checklist remains unchanged until that evaluation and a separate rollout decision. The trial does not solve existing SEC data gaps; it reports unsupported evidence as unknown.
