# CSP liquidity update

## Settings
- Minimum open interest: 500 contracts per option contract.
- Preferred open interest: 1,000 or more. Among otherwise qualifying contracts, preferred liquidity sorts first; 500-999 can still qualify.
- Minimum daily option volume: 100 contracts per option contract. Missing, invalid, or lower volume does not qualify.
- Expiration remains 7-45 calendar days. Existing delta, spread, collateral, earnings, trend and valuation checks remain in force.

The first startup migrates saved liquidity settings to these agreed values and invalidates ranked results and the cached review. Run a fresh scan after deployment. Subsequent changes to stricter settings are preserved. Daily option volume accumulates during the session, so fewer contracts may qualify early in the day.

## GitHub and Render
1. Review and merge this branch into main.
2. In Render, deploy that commit using the existing service configuration and persistent disk. No dependency or environment-variable changes are required.
3. Check /health, open Screen criteria, and confirm 500 minimum OI, 1,000 preferred OI, 100 daily option volume, and 7-45 DTE.
4. Run a fresh scan. In a stock review, inspect the Daily option volume check and the preferred open-interest note. A contract with 99 daily volume must fail; 100 meets this requirement only. All other checks must also pass.

Do not replace the persistent database or credentials with source files. This update does not submit orders. No live scan or trade was executed while preparing it.

## Validation
- 24 Python tests passed: test_csp_liquidity, test_put_setup_config, test_app.
- 17 preferred-put JavaScript assertions passed.
- All 13 dashboard scripts compile together.
- Additional Schwab suite: 6 tests passed; one existing POSIX file-permission assertion fails on Windows (0666 reported versus Linux 0600). schwab.py is unchanged; verify that permission test in Linux CI/Render-compatible staging.
- Uploaded provider.py, schwab.py, requirements.txt, engine.py and config.json matched the starting repository version. Only engine.py and config.json needed changes among those five uploads; supporting app/UI/tests are included.
