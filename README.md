# Stockdesk — Schwab market data + IBKR portfolio

Start with **SCHWAB_SETUP.md** for current deployment instructions. This release replaces Tradier; do not configure TRADIER_TOKEN. Finnhub research data is still required.

# Stockdesk — hosted research and screening agent

Status: deployable application, not deployed from this workspace. Live provider integration requires your credentials and entitlements. No simulated stock selections are displayed. The app has no order-placement routes.

## Deploy online (Render)
1. Put the contents of this folder in a private GitHub repository.
2. In Render, choose New → Blueprint and connect that repository. Render reads render.yaml. Review the current hosting charge before provisioning; an always-on paid service with a persistent disk is required. Use one instance only.
3. Set SCHWAB_APP_KEY, SCHWAB_APP_SECRET, SCHWAB_CALLBACK_URL to your production Schwab market-data token and FINNHUB_TOKEN to a Finnhub key with U.S. earnings calendar, company news and basic financial metrics access. Do not use delayed sandbox data. Confirm your data agreements allow this private personal-use dashboard; redistribution requires separate rights.
4. Set ALERT_WEBHOOK_URL to a Slack incoming webhook if desired (the payload uses a `text` field). If unused, leave blank. Credentials belong only in Render environment variables, never browser code or Git.
5. Open Render's assigned HTTPS URL. Sign in as `admin` using the generated DASHBOARD_PASSWORD from the environment settings. The health endpoint intentionally exposes no account information.
6. Review criteria, click Run screen during regular U.S. hours, and inspect Agent activity. Verify actual market prices and option contracts against your broker before enabling notifications. Notifications default OFF; enable in Screen criteria after verification.

## Local preview
Python 3.11+ is required. Run `pip install -r requirements.txt`, then `python app.py`; visit http://localhost:8000. Without keys the dashboard shows its honest setup state. Production refuses access if DASHBOARD_PASSWORD is missing. Local mode without a password is for a trusted local machine only. Keep the server behind your hosting provider's HTTPS endpoint.

## Screening rules and assumptions
- Screens a configurable curated universe of approximately 100 liquid U.S.-listed stocks and ADRs. This is NOT an exhaustive exchange-wide top-50 scan. Up to 50 unique qualifying names, ranked by a transparent heuristic score, are returned. Fewer than 50 is expected with strict filters. Neither score nor delta is a predicted return or guaranteed probability.
- A stock may qualify for puts OR swings. Tabs separate strategies. No portfolio optimization, suitability determination, total capital allocation or automatic execution is performed.
- Put defaults: $10,000 cash per position, price >= $10, average volume >= 1m, 21–45 calendar DTE, absolute delta 0.15–0.30, open interest >=500, spread <=15% of midpoint, bid yield >=0.5%, standard 100-share contracts, strike below stock price, stock above rising-order MA20 > MA50. Reserve gross strike ×100, use the bid for conservative premium. No earnings returned through expiration plus two days. Verify calendars independently. Cash yield is period yield, not annualized. Maximum loss=(strike−premium)×100; this is fundamentally different from swing 2:1 stop-based risk.
- Swing defaults: 5–10 trading-session intent; last completed daily close above previous 20-session high; current price still above that high; price > MA20 > MA50; within 2 ATR of MA20; last completed day volume >=1.3× prior 20-session average; stop below five-day low minus 0.1 ATR; risk <=2 ATR. First target is the nearest older historical daily high above entry; second is the next high at least 0.5 ATR above target 1. Target 1 must offer >=2:1 and be within 4 ATR. Historical highs are a conservative resistance proxy, not guaranteed tradable supply or a guarantee of a two-week move. Earnings next 14 days plus buffer exclude swings.
- JD additionally requires three hourly closes above 27.15, followed by a crossing above 27.60 and a complete subsequent hour with low above 27.60 and relative hourly volume >=1.3. Hours are assembled from 15-minute bars anchored at 09:30 ET. The final 30-minute session fragment is excluded. This event gate is conservative and can miss setups between scans or when intraday history coverage is insufficient. No JD alert bypasses the general swing filters. JD can separately qualify for a put screen; turn off notifications if you want JD-specific swing alerts only.
- MA/ATR calculations use completed daily history. Unadjusted corporate actions can affect calculations; review split events. Generic swing confirmation uses daily bars, not JD’s hourly rule; these assumptions await your acceptance.
- Data unavailable, stale quote (>15 minutes), missing metrics/earnings response, insufficient history, or invalid option timestamps blocks that candidate. Greeks supplied by the provider may update less frequently than quotes. No event returned does not guarantee no earnings announcement.
- Ranking: swing score=min(100,50+10×R/R+5×RVOL); put score=20×period-yield-percent+30×(1−absolute-delta)−20×spread-fraction. Mixed strategy scores are heuristic and not directly comparable economic expected returns. Filters can be adjusted; no stock is added just to fill 50 slots.

## Agent and reporting
Single Python web process with an hourly monitoring thread and persistent SQLite state. The exchange clock is polled each minute and drives U.S. holidays, DST and early closes. One scan per regular-session hour slot starting at 09:30 ET; a restart can start within the current slot. Long scans can delay subsequent checks. Scan errors are visible in the dashboard. Data adapters throttle requests; account-specific quotas may require a smaller universe. Only qualified rows with fresh quotes at dispatch are eligible for external notifications. One successful alert per stock/strategy combination per market date is persisted across restarts. Webhooks can duplicate on a process crash after delivery but before persistence; exactly-once delivery is not promised. Failed delivery is logged and can be retried at the next scan. A rejected or partial hourly scan is not falsely marked as successful.

Reports include sourced financial metrics, trade levels, put contract economics, trend watch zones and headlines. These are deterministic research summaries, not independent AI analyst agents. They do not produce a DCF/fair-value verdict, personalized staged allocations, or a verified interpretation of catalysts. Missing metrics appear as unavailable. Fundamental data is dated by retrieval, not necessarily its fiscal reporting period.

## Validation and remaining activation work
Local tests cover screening rejection, valid option economics, credential-free setup, saving settings, browser rendering, and production password blocking. Live Schwab/Finnhub coverage, deployment, holiday scheduling against live clock, and external webhook delivery cannot be verified without connected accounts. Check these before treating the app as operational. No market data API keys or hosting credentials were available when this package was built.

Provider and deployment references:
https://docs.tradier.com/docs/market-data
https://docs.tradier.com/reference/brokerage-api-markets-get-options-chains
https://finnhub.io/docs/api
https://render.com/docs/blueprint-spec
https://render.com/docs/disks


## Updated required rules and morning digest
Both screens now require positive annual revenue growth, positive annual free cash flow (operating cash flow minus capital expenditure), current ratio >= 1.5, and total liabilities / equity <= 0.5. The latter is a deliberately conservative proxy for debt / equity; it includes non-debt liabilities. These are editable assumptions for “strong balance sheet.” Annual reported financials must be <=550 days old; missing fields, unsupported filing formats, negative equity, and inaccessible provider coverage exclude the stock. These strict generic rules may exclude banks and foreign issuers. Annual figures do not guarantee recent quarterly improvement. Finnhub financials-reported API access is additionally required; coverage depends on account entitlement.

Demand confirmation uses completed daily candles: a strict two-bar pivot low in the recent 45-bar window, a subsequent retest in the last five bars, a bullish close above the zone, no intervening low below the pivot, and current price above the zone but within three ATR. The zone spans the pivot low to pivot low + 0.5 ATR. This is a reproducible heuristic, not proof of institutional demand. Put strikes need not sit within this zone.

Puts additionally require 5–10% OTM, absolute delta 0.20–0.30, open interest >=500, and spread <=10% of midpoint AND <=$0.15, with a positive bid. Existing 21–45 DTE, collateral limit, yield, uptrend, earnings, and quote-freshness checks remain. Option volume is not a required gate because the early-morning count can be small. OTM/delta rules do not apply to swing stock entries; swings still require two historical resistance targets and first-target R/R >=2.

A morning scan becomes due at 09:45 America/New_York on exchange trading days; the digest is published when the scan finishes. It remains available under Agent activity, independently of notifications. If the process starts late, it catches up before noon. DST and holidays follow New York time and the live exchange clock. Existing hourly scans continue. Only nonempty morning digests are sent to the configured generic JSON webhook when notifications are enabled. Empty results cause no external alert. A generic webhook must accept a JSON `text` field; platform message-length limits may require a relay for long digests. Failed morning sends retry before noon. Other hourly qualifying alerts retain their prior behavior.

Final results exclude quotes older than 15 minutes at scan completion, including option quotes. A large universe or slow provider can therefore yield fewer results; counts are never padded. The universe is configurable, not a complete US-market scan. No live credentials, hosting connection, or notification account was supplied for this update. Deploy the new package and configure the existing environment variables to activate it; this archive does not itself run online.
