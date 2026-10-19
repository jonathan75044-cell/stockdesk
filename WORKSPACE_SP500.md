# Watchlist workspace and S&P 500 trial comparison

After merge and deployment, run a fresh scan. Workspace now has a Watchlists &
trial rules page with Near-demand, Golden-zone, and Current rules vs. Trial rules
tabs. Existing controls and entry plans remain attached to their panels.

The trial comparison screens the bundled S&P 500 reference list (503 securities,
retrieved 2026-10-19 from datasets/s-and-p-500-companies, content SHA
b874b56c017a883f247b026446a06294d7ff57fa). This is a versioned snapshot, not a
live membership feed; update the CSV and retrieval date when constituents change.

Additional symbols get price/history and compact trial evidence only. They run
before saved live symbols, do not change saved screening criteria, and cannot
enter ranked opportunities or generate alerts. No extra SEC valuation work is
triggered for these trial-only symbols. Unverified financials/earnings/sizing
remain unknown. The larger universe adds scan time and market-data requests;
processing stays sequential and does not retain historical-bar arrays.

Top 25 sorting: best trial stage first (All checks, Ready, Watch, Not ready),
then the stage with SMA200, then baseline passed-check count, then ticker.
Stocks outside the S&P reference list are excluded from this comparison only.
Missing or failing checks are never promoted to Watch. Ranking is checklist
priority, not expected return. Old scans need refreshing for membership evidence.

The ranked table now explains recorded current-rule outcomes when empty.
Trial-only exclusions are excluded from that explanation. Full scan diagnostics
remain in Agent activity. Live data was inaccessible during this change, so no
claim is made about the latest production scan's specific blockers.
