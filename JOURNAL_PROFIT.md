# Journal profit

Schwab activity now includes Profit / loss per close and a calculation note.
The total includes only matched closing transactions across retained imported
history and accounts. Manual totals stay separate to avoid double counting.

Estimates use FIFO allocation of opening net cash and the closing net cash,
including posted costs. Partial closes consume only their matching quantity.
No price multiplier is guessed for options: reported transaction cash is used.
Only VALID, single-instrument, explicit OPENING/CLOSING activity is eligible.
Missing opening lots, missing dates, inconsistent directions, pending activity,
multiple legs, assignments and expirations remain unavailable. Ambiguity blocks
later matching for that account/instrument rather than guessing a remaining lot.

The import starts with 30 days of history and retains imported records. Older
positions may have no entry in that window. These are bookkeeping estimates,
not tax-lot or account performance: tax adjustments, corporate actions and
assignment share basis are not reconciled. No profit is invented for open trades.
CSV exports include the estimate and explanation. No database migration is needed.
Revised imported rows are recalculated when read. No broker orders are submitted.

After deployment, refresh the journal. Existing imported records are evaluated
immediately; Sync now can retrieve recent activity. Manual profit labels now say
Profit / loss per trade and Total manual profit / loss.
