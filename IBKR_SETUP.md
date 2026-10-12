# IBKR portfolio connection

This package adds an account snapshot panel to Stockdesk. No account is connected and no online deployment is activated by this package. Schwab is not included in this update.

## Connection architecture

Run IBKR's Client Portal Gateway and `ibkr_bridge.py` on a trusted computer. Sign in directly through IBKR's gateway browser flow and complete its required authentication. The bridge reads accounts, summaries, currency ledgers and paginated positions every five minutes, then sends a snapshot over HTTPS to the hosted dashboard. The computer and gateway must remain running. IBKR session expiry or login requirements can interrupt updates; manual reauthentication may be needed. This is not an unattended cloud-only IBKR login solution.

Official documentation:
https://www.interactivebrokers.com/campus/ibkr-api-page/webapi-doc/
https://www.interactivebrokers.com/campus/trading-lessons/launching-and-authenticating-the-gateway/

Confirm your account is eligible for the Gateway with IBKR. Individual access generally requires a funded IBKR Pro account. Broker authentication and entitlements remain controlled by IBKR.

## Hosted dashboard

Follow README.md to deploy the application. Keep APP_ENV=production and set a strong DASHBOARD_PASSWORD. Render's blueprint generates BROKER_SYNC_TOKEN. For another host, generate a secret with `python3 -c "import secrets; print(secrets.token_urlsafe(48))"` and store it in the host's private environment settings. Use the same token in the local bridge environment. Do not paste secrets in chat or commit them to GitHub.

The snapshot endpoint uses its own bearer token; the portfolio viewing endpoint uses the dashboard password. Host the application behind HTTPS. Protect the hosting account and its persistent disk: portfolio snapshots are sensitive and are stored in the existing SQLite database, not application-level encrypted. Only the most recent snapshot is stored under the portfolio key. Full account IDs are not sent by the bridge. Rotate the sync token if exposed.

## Local bridge

Install the official Gateway according to IBKR's instructions. Keep its listener bound to localhost; do not expose it publicly. Install the package requirements and configure these environment variables in a local private environment:

- STOCKDESK_URL: your actual deployed HTTPS dashboard URL.
- BROKER_SYNC_TOKEN: the hosted sync secret (at least 32 characters).
- IBKR_GATEWAY_URL: defaults to https://localhost:5000/v1/api.
- IBKR_CA_BUNDLE: optional path to a PEM trust bundle for the Gateway's certificate. Gateway certificates may not be publicly trusted. Configure a trusted certificate or trust the verified local Gateway certificate; the bridge deliberately does not disable TLS verification. The certificate must match the hostname used.

Authenticate to the Gateway through IBKR's browser flow. Run `python ibkr_bridge.py` from this folder. Use an operating-system service if desired to restart the bridge, but service restarts do not bypass IBKR authentication. After a successful sync, refresh the dashboard. The panel updates every minute and labels snapshots stale after 15 minutes. Bridge failures preserve the last snapshot and let it age.

## Scope and limitations

The IBKR client in the bridge issues GET requests only to /portfolio/accounts and account summary, ledger and positions endpoints. It contains no order submission, modification or cancellation functionality. This application-level restriction does not imply that IBKR issued a read-only token. Use separate restricted credentials if IBKR supports them for your account configuration.

Open option positions means existing holdings, including shorts; pending orders are not fetched. Cash, settled cash, buying power and available funds are shown distinctly when supplied. No cash is labeled safe to spend on additional puts. Existing obligations, currency conversions and pending orders would need reconciliation before any portfolio-aware sizing. Screening continues to use the configured per-contract limit. Account snapshots do not replace market-data subscriptions used by the screener.

No live brokerage login or production deployment was tested. Tests use synthetic data. To disconnect, stop the bridge and remove/rotate BROKER_SYNC_TOKEN. To remove the stored snapshot, stop the app and delete the `ibkr_portfolio` key from the SQLite kv table, then restart; manage host backups separately.
