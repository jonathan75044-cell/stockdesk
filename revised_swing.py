"""Offline swing-checklist trial. No application imports this module; no orders/alerts.

Run: python revised_swing.py case.json
Input contract and limitations: REVISED_SWING_TRIAL.md.
"""
import json
import math
import sys
from datetime import date, datetime, timedelta
from engine import indicators
from pullback import pullback_zone
from resistance import resistance_levels


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def stamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError('Evidence timestamps must include timezone')
    return result


def recent(evidence, now, days):
    try:
        return bool(evidence.get('source')) and 0 <= (now-stamp(evidence['checked_at'])).total_seconds() <= days*86400
    except (KeyError, ValueError, TypeError):
        return False


def technical(days, price, expected_session, config):
    """Only completed, dated bars. Touch anchors are frozen at the touch date."""
    dates = [date.fromisoformat(b['date']) for b in days]
    if any(a >= b for a, b in zip(dates, dates[1:])):
        raise ValueError('Daily dates must strictly increase')
    if not dates or dates[-1] != date.fromisoformat(expected_session):
        raise ValueError('History must end at the expected completed exchange session')
    if not finite(price) or price <= 0:
        raise ValueError('Positive finite price required')
    m = indicators(days)
    if any('open' not in b for b in days):
        raise ValueError('Open prices required for reversal checks')
    checks = []
    def add(stage, name, passed, detail):
        checks.append(dict(stage=stage, name=name, status='unknown' if passed is None else 'pass' if passed else 'fail', detail=detail))
    closes = [float(b['close']) for b in days]
    lows = [float(days[i]['low']) for i in range(max(2,len(days)-90),len(days)-2)
            if all(float(days[i]['low']) < float(days[j]['low']) for j in (i-2,i-1,i+1,i+2))]
    add('watch', 'Liquidity', m['avgvol'] >= max(5000000,config['min_avg_volume']), f"Average daily volume {m['avgvol']:.0f}")
    add('watch', 'Minimum price', price >= config['min_price'], f'Price {price:.2f}')
    add('watch', 'Rising 50-day average', m['ma50'] > sum(closes[-55:-5])/50, 'Compare current average with five completed sessions earlier')
    add('watch', 'Higher confirmed swing low', lows[-1] > lows[-2] if len(lows)>1 else None, 'Two-sided confirmed pivots; missing pivots remain unknown')
    touch = None
    # Search the latest five completed sessions, retaining only evidence available then.
    for end in range(len(days), max(64,len(days)-5), -1):
        prefix=days[:end]; pm=indicators(prefix)
        zone=pullback_zone(float(prefix[-1]['close']),prefix,pm['atr'])
        if zone and zone['in_zone']:
            touch=dict(zone, touch_date=prefix[-1]['date'], index=end-1, atr=pm['atr'])
            break
    add('watch','Recent completed close in pullback band',bool(touch),'38.2%–61.8% within five completed sessions; 50%–61.8% is a preference')
    support = bool(touch) and min([price]+[float(b['low']) for b in days[touch['index']:]]) >= touch['zone_low']-.5*touch['atr']
    add('watch','Pullback support intact',support,'No breach of frozen zone floor minus half the touch-day ATR')
    reversal = None
    if touch:
        # The latest valid reversal following the touch; trigger may occur on a later day.
        for i in range(touch['index'],len(days)):
            b=days[i]
            if float(b['close'])>float(b['open']) and float(b['close'])>float(days[i-1]['high']):
                reversal=i
    add('ready','Completed bullish reversal',reversal is not None,'Close above its open and the prior daily high, on or after the zone touch')
    rvol=None
    threshold=None
    if reversal is not None:
        avg=sum(float(b['volume']) for b in days[reversal-20:reversal])/20
        rvol=float(days[reversal]['volume'])/avg if avg>0 else None
        threshold=float(days[reversal]['high'])
    add('ready','Reversal-day volume',rvol>=config['min_rvol'] if rvol is not None else None,f'Reversal-day ratio {rvol}; minimum {config["min_rvol"]}')
    add('ready','Break above reversal high',price>threshold if threshold is not None else None,f'Completed reversal high {threshold}')
    add('ready','Recover 20-day average',price>m['ma20'],'Recovery required at entry, not at discovery')
    stop=math.floor((min(float(b['low']) for b in days[-5:])-.1*m['atr'])*100)/100
    entry=math.ceil(max(price,(threshold+.01) if threshold is not None else price)*100)/100
    risk=entry-stop
    resistance=resistance_levels(days,entry,m['atr'])
    target=resistance['target1']['price'] if resistance['target1'] else None
    obstacle=resistance['nearest_overhead_high']
    effective_target=min(target,obstacle['price']) if target and obstacle else target
    cost=config['round_trip_cost_per_share']
    rr=(effective_target-entry-cost)/(risk+cost) if effective_target and risk>0 else None
    add('ready','Stop and risk',stop>0 and 0<risk<=2*m['atr'],'Stop below five-day low; maximum distance 2 ATR')
    add('ready','Reward/risk after assumed costs',rr>=max(2,config['min_rr']) if rr is not None else None,f'Net ratio {rr}; nearest overhead high constrains room; costs are assumptions, not fill guarantees')
    add('ready','Reachable first target',target is not None and 0<target-entry<=4*m['atr'],'Nearest confirmed resistance within 4 ATR; no target moved to pass')
    return dict(checks=checks,touch=touch,reversal_date=days[reversal]['date'] if reversal is not None else None,
                entry=entry,stop=stop,target=target,effective_target=effective_target,reward_risk=rr,
                risk_per_share=risk+cost,relative_volume=rvol,resistance=resistance)


DEFAULTS=dict(min_price=10,min_avg_volume=5000000,min_rr=2,min_rvol=1.3,
              holding_days=14,earnings_buffer_days=2,benchmark='SPY',round_trip_cost_per_share=.05)


def assess(case):
    config={**DEFAULTS,**case.get('config',{})}
    for name in ('min_price','min_avg_volume','min_rr','min_rvol','holding_days','earnings_buffer_days','round_trip_cost_per_share'):
        if not finite(config[name]) or config[name]<0:
            raise ValueError('Invalid config: '+name)
    if config['holding_days']<1 or config['min_rvol']<=0:
        raise ValueError('Positive holding period and relative-volume threshold required')
    if config['benchmark'] not in ('SPY','QQQ'):
        raise ValueError('Select SPY or QQQ explicitly')
    now=stamp(case['as_of']);session=case['expected_completed_session']
    if date.fromisoformat(session)>=now.date():
        raise ValueError('Trial entry assessment requires prior-session completed bars')
    result=technical(case['days'],case['price'],session,config)
    checks=result['checks']
    def add(stage,name,value,detail):
        checks.append(dict(stage=stage,name=name,status='unknown' if value is None else 'pass' if value else 'fail',detail=detail))
    benchmark=case.get('benchmarks',{}).get(config['benchmark'],{})
    valid=benchmark.get('data_date')==session and benchmark.get('source')
    add('ready','Primary benchmark trend',benchmark.get('trend')=='Uptrend' if valid else None,config['benchmark']+' is the selected benchmark; the other is informational')
    difference=benchmark.get('relative_strength_pp')
    add('ready','Relative strength',difference>=0 if valid and finite(difference) else None,'Stock versus selected benchmark over identical 20-session dates')
    value=case.get('valuation',{})
    intrinsic=value.get('intrinsic_value')
    valid=recent(value,now,90) and value.get('supported') is True and finite(intrinsic) and intrinsic>0
    add('confirm','Supported undervaluation',case['price']<intrinsic if valid else None,'Supported, dated estimate above price; unavailable never passes')
    financial=case.get('financial_review',{})
    valid=recent(financial,now,90) and financial.get('sector') and financial.get('policy') and financial.get('evidence')
    add('confirm','Sector-appropriate financial review',financial['passed'] if valid and type(financial.get('passed')) is bool else None,'Requires documented industry policy and evidence; generic ratio limits are not silently waived')
    earnings=case.get('earnings',{})
    try:
        event=date.fromisoformat(earnings['next_date'])
        verified=recent(earnings,now,1) and earnings.get('verified') is True and event>=now.date()
    except (KeyError,ValueError,TypeError):
        verified=False;event=None
    end=now.date()+timedelta(days=config['holding_days']+config['earnings_buffer_days'])
    add('confirm','Verified earnings outside holding window',event>end if verified else None,f'No earnings through {end}; empty calendar is unknown')
    quote=case.get('quote',{})
    try:
        live=quote.get('session')=='open' and 0<=(now-stamp(quote['at'])).total_seconds()<=900 and now<stamp(quote['session_end'])
    except (KeyError,ValueError,TypeError):
        live=False
    add('confirm','Fresh regular-session quote',live,'Positive price validated; quote age at most 15 minutes and session open')
    sizing=case.get('sizing',{});cash=sizing.get('cash');budget=sizing.get('maximum_loss');allocation=sizing.get('allocation_cash')
    shares=0
    if all(finite(x) and x>0 for x in (cash,budget,allocation,result['risk_per_share'])):
        shares=max(0,math.floor(min(cash/result['entry'],allocation/result['entry'],budget/result['risk_per_share'])))
    add('confirm','Personal risk and allocation budget',shares>=1 if sizing else None,'Whole shares bounded by cash, maximum planned loss, and allocation; gaps can exceed planned loss')
    passed=lambda stages:all(c['status']=='pass' for c in checks if c['stage'] in stages)
    result.update(stage='All required checks passed' if passed(('watch','ready','confirm')) else 'Ready to review' if passed(('watch','ready')) else 'Watch' if passed(('watch',)) else 'Not ready for watchlist',
                  hypothetical_shares=shares,config=config,experimental=True,trade_eligible=False,
                  note='Offline trial only. No change to live screening, alerts, or orders. Passing is not a forecast.')
    return result


if __name__=='__main__':
    with open(sys.argv[1],encoding='utf-8-sig') as source:
        print(json.dumps(assess(json.load(source)),indent=2,allow_nan=False))
