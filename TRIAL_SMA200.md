# Trial comparison: 200-day average

After deploying, run a new scan and open **Current rules vs. Trial rules**.
Compare **Trial without 200-day filter** with **Trial with 200-day filter**.
The added watch-stage check requires the scan price strictly above the simple
average of the latest 200 completed daily closes. Equality does not pass.
Fewer than 200 valid closes means unknown, never a passing filter.

The direction compares that average with five sessions earlier (205 bars needed).
Rising, falling, or flat is informational only. Live rules, rankings, alerts,
configuration and trade eligibility are unchanged. Old scans require a fresh scan.
Both columns reuse the same history, price, benchmark and research evidence;
there are no extra provider calls and no additional stored history arrays.

A higher trial stage is not evidence of better returns. Review both columns
across scans before deciding whether to adopt a rule. No adoption switch is added.
