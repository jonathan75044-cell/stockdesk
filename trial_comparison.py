"""Read-only shadow assessment; no changes to ranking, alerts, or eligibility."""
import copy
from datetime import datetime, timezone
from revised_swing import technical, assess, DEFAULTS, finite
from market_context import relative_strength


def sma200_context(days, price):
    """Completed-bar average; five-session direction is informational only."""
    result=dict(value=None, distance_pct=None, direction='Unknown', above=None,
                data_date=days[-1]['date'] if days else None, bars=len(days))
    closes=[d.get('close') for d in days[-205:]]
    if len(closes)<200 or not all(finite(x) and x>0 for x in closes[-200:]):
        return result
    average=sum(closes[-200:])/200
    result['value']=average
    if finite(price) and price>0:
        result.update(above=price>average, distance_pct=(price/average-1)*100)
    if len(closes)>=205 and all(finite(x) and x>0 for x in closes):
        previous=sum(closes[-205:-5])/200
        result['direction']='Rising' if average>previous else 'Falling' if average<previous else 'Flat'
    return result


def capture_trial(days, price, quote_at, context, cfg):
    settings={**DEFAULTS,'min_price':cfg['min_price'],
              'min_avg_volume':max(5000000,cfg['min_avg_volume']),
              'min_rr':max(2,cfg['swing_min_rr']),'min_rvol':cfg['swing_min_rvol'],
              'earnings_buffer_days':cfg['earnings_buffer_days']}
    plan=technical(days,price,days[-1]['date'],settings)
    relative=relative_strength(days,context)
    benchmarks={}
    for symbol in ('SPY','QQQ'):
        b=context.get(symbol,{});r=relative.get(symbol,{})
        if b.get('available') and b.get('freshness')!='Latest completed session missing' and r.get('available'):
            benchmarks[symbol]=dict(source='Schwab completed daily bars',data_date=b['data_date'],trend=b['trend'],relative_strength_pp=r['difference_pp'])
    return dict(sma200=sma200_context(days,price),plan=plan,price=price,quote_at=quote_at,data_date=days[-1]['date'],config=settings,benchmarks=benchmarks)


def comparison_rows(state, now=None):
    now=now or datetime.now(timezone.utc)
    items={x['symbol']:x for x in state.get('watchlist',[])+state.get('golden_zones',[])+state.get('rows',[])}
    ranked={x['symbol'] for x in state.get('rows',[]) if x.get('swing')}
    result=[]
    for d in state.get('diagnostics',[]):
        symbol=d['symbol'];item=items.get(symbol,{})
        row=dict(symbol=symbol,current=d.get('outcome','Not evaluated'),
                 current_technical=d.get('swing_technical_pass'),current_ranked=symbol in ranked,
                 current_preferred=item.get('setup_assessment'),trial=None)
        captured=d.get('trial_capture')
        if not captured:
            row['reason']=d.get('trial_error','Run a new scan after deployment to collect trial evidence.')
        else:
            clock=state.get('market_clock',{})
            case=dict(as_of=now.isoformat(),expected_completed_session=captured['data_date'],price=captured['price'],
                      config=captured['config'],benchmarks=captured['benchmarks'],
                      quote=dict(at=captured['quote_at'],session='closed' if state.get('research_only') or state.get('stale') else clock.get('state'),session_end=clock.get('regular_session_end')))
            v=item.get('valuation',{})
            if v.get('status')=='estimated':
                case['valuation']=dict(source='Stockdesk supported valuation model',checked_at=state.get('completed_at'),supported=True,intrinsic_value=v.get('intrinsic_value'))
            # Existing ratio checks and an empty calendar are NOT verified sector/earnings evidence.
            # Personal risk inputs are not inferred from broker balances or saved unrelated preferences.
            try:
                row['trial']=assess(case,captured['plan'])
                row['trial']['data_date']=captured['data_date']
                row['trial']['quote_at']=captured['quote_at']
                context=captured.get('sma200',{})
                row['sma200']=context
                filtered=copy.deepcopy(captured['plan'])
                above=context.get('above')
                filtered['checks'].append(dict(stage='watch',name='Price above 200-day average',
                    status='pass' if above is True else 'fail' if above is False else 'unknown',
                    detail='Scan price must be strictly above the average of 200 completed daily closes. Direction is informational.' if context else 'Run a new scan to collect 200-day evidence.'))
                row['trial_with_sma200']=assess(case,filtered)
            except (KeyError,ValueError,TypeError) as error:
                row['reason']='Trial evidence unavailable: '+str(error)
        result.append(row)
    return result


def top_comparisons(state, now=None):
    members=set(state.get('sp500_universe',[]))
    rows=[r for r in comparison_rows(state,now) if r['symbol'] in members]
    stages={'All required checks passed':3,'Ready to review':2,'Watch':1}
    def key(row):
        base=row.get('trial') or {};filtered=row.get('trial_with_sma200') or {}
        a=stages.get(base.get('stage'),0);b=stages.get(filtered.get('stage'),0)
        checks=base.get('checks',[])
        passed=sum(c['status']=='pass' for c in checks)
        return (-max(a,b),-b,-passed,row['symbol'])
    rows.sort(key=key)
    for rank,row in enumerate(rows[:25],1):row['rank']=rank
    return rows[:25]
