# Scanner diagnosis and changes

The supplied screenshot reports first blocking stages, not every failed filter.
It cannot establish why all 86 stocks lacked a zone or what caused the seven errors.
No historical scan data, exception logs, or broker credentials were supplied.

## Confirmed defects

- The demand pivot loop began at index n-5. Index n-4 is also eligible: two
  completed bars confirm the strict pivot, and the last completed bar may retest.
  The corrected loop admits this case without using future or incomplete bars.
- Zone boundaries were rounded before the option strike check. Rounding the high
  upward could admit a strike slightly above the actual boundary. Boundaries now
  retain full precision; the existing dashboard controls display formatting.
- Missing opens previously looked like ordinary demand rejection. Malformed,
  non-finite OHLCV and zero baseline volume now produce explicit data errors.

## Diagnostics

Each evaluated pivot records exact bounds, ATR distance, retest date when present,
and lower-low invalidation date when present. Per-symbol metrics and demand stage
counts explain rejection. The diagnostics page summarizes demand subreasons.
Processing errors include their stage and safe missing-field information;
request exception text is withheld because it can contain credentials in URLs.

The rules remain strict: 45-bar pivot window, two bars on either side, retest
within the last five completed bars, bullish close above the zone, no later low
below the pivot, price above the zone within configured distance. Options
liquidity, spreads, quote freshness, OTM, delta, collateral, fundamentals and
earnings exclusions were not relaxed. Configuration is unchanged.

## Verification and use

19 focused scanner/risk tests passed, including nine new regression tests.
The full suite could not run because requests is absent from the bundled runtime;
the environment blocked downloading test dependencies. Live provider behavior
and the seven historical errors remain unverified.

This directory is a complete source copy. To update an existing installation,
replace engine.py, app.py, diagnostics.html and test_app.py, and add test_demand.py.
Keep the installation's existing secrets and data directory. Install the project's
requirements in its normal Python environment, then run `python -m unittest
discover -v`. On Windows, timezone data may also require the tzdata package.
Restart the app and run a fresh scan during market hours. Review demand subreasons
and stage-specific errors before considering any explicit rule changes.

The Downloads source directory was not modified. No deployment or notification
was performed.
