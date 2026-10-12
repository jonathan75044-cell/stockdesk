# Schwab market-data setup — start here

This version replaces Tradier with Charles Schwab for real-time stock quotes,
completed daily history, JD intraday confirmation, option chains/Greeks and
regular-session market hours. Finnhub remains required for financial statements,
earnings calendars and news. IBKR portfolio support is preserved. Schwab account
balances/holdings are NOT imported by this version. No order endpoints exist.

1. In the Schwab developer portal confirm your approved application has **Market
   Data Production** access. Accounts and Trading access alone is insufficient.
   Changing app settings can require further approval.
2. Extract this ZIP. Upload the CONTENTS of stockdesk into your private GitHub
   repository, with app.py and render.yaml at the root. Replace the earlier version.
   Never upload .env, token files, the data directory or brokerage secrets.
3. In Render choose New > Blueprint and connect this repository. Review paid
   hosting and disk costs before deploying. Keep the persistent disk: OAuth tokens
   and configuration must survive restarts. Run one service instance/worker only.
4. Enter SCHWAB_APP_KEY, SCHWAB_APP_SECRET and FINNHUB_TOKEN in Render's private
   environment settings. Set SCHWAB_CALLBACK_URL to
   https://YOUR-SERVICE.onrender.com/auth/schwab/callback
   using your actual service URL. If Render has not assigned it yet, deploy first
   with this setting blank, then set the exact URL and redeploy. Scanning stays off
   until all required settings and authorization are complete.
5. Register exactly the SAME HTTPS callback URL in your Schwab developer app.
   Wait until the app is approved/ready again if Schwab requires review.
6. Retrieve DASHBOARD_PASSWORD from Render's environment settings. Open the service
   URL and log in with username admin and that password. Click Connect / reauthorize
   Schwab. Authenticate only on Schwab's own site, review consent, then return to
   your dashboard. Keep the same browser so the authorization cookie is retained.
7. During a trading session run a scan and inspect errors and the status timestamp.
   Real-time entitlements and actual API responses must be verified using your app.
   A lack of candidates may mean strict rules or missing data; inspect scan errors.
8. Configure ALERT_WEBHOOK_URL for a compatible webhook receiving {"text":"..."}
   and enable notifications in dashboard settings if external alerts are wanted.
   Delivery must be tested separately. Without it, results appear only in the site.

Schwab access tokens are refreshed automatically; refresh-token authorization
normally expires after seven days. Reconnect through the dashboard periodically.
The site displays disconnected when local authorization expires. It cannot bypass
Schwab authentication. Revocation or entitlement failure can occur earlier and will
appear as scan errors. Tokens are stored server-side in a mode-0600 file on the
persistent disk, not in GitHub or the browser. Restrict hosting/account access.

Morning scan starts at 9:45 America/New_York on open trading days; hourly scans
continue during regular market hours. Results appear when the scan finishes.
The universe is the configurable starter list, NOT every listed U.S. stock. Only
up to 50 passing stocks are surfaced, and missing fundamental evidence excludes
candidates. Quality rules and put constraints from the prior package remain.
Schwab quoteTimeInLong is used for both bid and ask freshness because the chain
supplies a single quote timestamp. Real-time chain flags are required.

Read IBKR_SETUP.md for the separate local portfolio bridge. Cash shown there does
not automatically establish uncommitted cash or position sizing.

Verification: local mocked API tests validate normalization and OAuth behavior;
no live Schwab access, Finnhub coverage, account authorization, deployment or
notification delivery has been tested by the author of this update.

API reference: https://developer.schwab.com/products/trader-api--individual
OAuth client documentation: https://schwab-py.readthedocs.io/en/latest/auth.html
