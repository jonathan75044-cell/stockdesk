"""Preferred swing setup assessment, separate from legacy screening eligibility."""
import math
from datetime import datetime, timezone


def trend_checks(price, days):
    """Five-session MA slope and strict 2-left/2-right pivots, using completed bars."""
    if len(days) < 55:
        return [{'name': 'Rising averages and higher swing highs/lows', 'passed': None}]
    closes = [float(b['close']) for b in days]
    ma20, ma50 = sum(closes[-20:])/20, sum(closes[-50:])/50
    previous20, previous50 = sum(closes[-25:-5])/20, sum(closes[-55:-5])/50
    bars = days[-90:]
    highs, lows = [], []
    for i in range(2, len(bars)-2):
        neighbors = [bars[j] for j in (i-2, i-1, i+1, i+2)]
        if all(float(bars[i]['high']) > float(b['high']) for b in neighbors):
            highs.append(float(bars[i]['high']))
        if all(float(bars[i]['low']) < float(b['low']) for b in neighbors):
            lows.append(float(bars[i]['low']))
    return [
        {'name': 'Price above 20-day average above 50-day average', 'passed': price > ma20 > ma50},
        {'name': 'Both averages rising versus five sessions ago', 'passed': ma20 > previous20 and ma50 > previous50},
        {'name': 'Last two confirmed swing highs and lows rising',
         'passed': highs[-1] > highs[-2] and lows[-1] > lows[-2] if len(highs) >= 2 and len(lows) >= 2 else None},
    ]


def assess_setup(item, state, now=None):
    now = now or datetime.now(timezone.utc)
    checks = []
    def add(name, passed, detail):
        checks.append(dict(name=name, status='unknown' if passed is None else 'pass' if passed else 'fail', detail=detail))
    plan = item.get('entry_plan') or {}
    technical = plan.get('preferred_checks')
    if technical is None:
        add('Technical entry plan', None, 'Run a fresh scan; a current pullback plan is required.')
    else:
        for check in plan.get('checks', []) + technical:
            add(check['name'], check.get('passed'), 'Completed daily bars through ' + plan.get('data_date', 'unknown'))
    add('At least 5 million average daily shares', plan.get('average_volume', 0) >= 5000000 if 'average_volume' in plan else None, 'Preferred setup liquidity floor.')
    rr = plan.get('reward_risk')
    add('At least 2:1 to first historical resistance', rr >= 2 if isinstance(rr, (int, float)) and math.isfinite(rr) else None, 'Use the nearest confirmed resistance; do not move targets to manufacture reward.')
    research = item.get('watchlist_research', {})
    for field, label in [('financial', 'Financial checks'), ('earnings', 'Earnings window')]:
        result = research.get(field, {})
        status = result.get('status')
        try:
            fresh = 0 <= (now-datetime.fromisoformat(result['checked_at'])).total_seconds() < 3600
        except (KeyError, TypeError, ValueError):
            fresh = False
        if not fresh:
            add(label, None, 'Research unavailable or older than one hour; rescan.')
            continue
        valid = status in ('passed', 'no_event_returned')
        add(label, valid if status in ('passed', 'failed', 'blocked', 'no_event_returned') else None,
            result.get('reason', 'Research unavailable'))
    value = item.get('valuation') or {}
    pct = value.get('valuation_pct')
    usable = value.get('status') == 'estimated' and isinstance(pct, (int, float)) and math.isfinite(pct)
    add('Supported undervaluation', value.get('classification') == 'undervalued' and pct > 0 if usable else None,
        f'Model undervaluation: {pct:.2f}%' if usable and value.get('classification') == 'undervalued' and pct > 0 else 'Not undervalued' if usable else value.get('reason', 'Valuation evidence unavailable'))
    for symbol in ('SPY', 'QQQ'):
        benchmark = state.get('market_context', {}).get(symbol, {})
        matched = benchmark.get('available') and benchmark.get('data_date') == plan.get('data_date') and benchmark.get('freshness') != 'Latest completed session missing'
        add(symbol + ' supportive trend', benchmark.get('trend') == 'Uptrend' if matched else None, benchmark.get('trend', 'Benchmark unavailable'))
        relative = plan.get('relative_strength', {}).get(symbol, {})
        difference = relative.get('difference_pp')
        valid = relative.get('available') and relative.get('end_date') == plan.get('data_date') and isinstance(difference, (int, float)) and math.isfinite(difference)
        add('20-session strength versus ' + symbol, difference >= 0 if valid else None,
            f'{difference:+.2f} percentage points' if valid else 'Matching comparison unavailable')
    try:
        quote_age = (now - datetime.fromisoformat(item['quote_at'])).total_seconds()
        end = datetime.fromisoformat(state['market_clock']['regular_session_end'])
        live = not state.get('research_only', True) and state['market_clock'].get('state') == 'open' and now < end and 0 <= quote_age <= 900
    except (KeyError, TypeError, ValueError):
        live = False
    add('Fresh regular-session quote', live, 'Recheck during regular market hours; quote must be at most 15 minutes old.')
    add('Completed current scan', bool(state.get('completed_at')) and not state.get('stale', True), 'Refresh after a completed scan; stale results cannot confirm an entry.')
    passed = all(c['status'] == 'pass' for c in checks)
    return {'status': 'Entry checks passed' if passed else 'Watchlist candidate', 'checks': checks,
            'passed': sum(c['status'] == 'pass' for c in checks), 'total': len(checks),
            'note': 'Preferred setup checklist, separate from ranked screening. Estimates and calendar results require verification; this is not an order or a guarantee.'}
