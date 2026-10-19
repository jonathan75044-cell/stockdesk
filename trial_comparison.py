"""Read-only shadow assessment; no changes to ranking, alerts, or eligibility."""
from datetime import datetime, timezone
from revised_swing import technical, assess, DEFAULTS
from market_context import relative_strength


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
    return dict(plan=plan,price=price,quote_at=quote_at,data_date=days[-1]['date'],config=settings,benchmarks=benchmarks)


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
            except (KeyError,ValueError,TypeError) as error:
                row['reason']='Trial evidence unavailable: '+str(error)
        result.append(row)
    return result
