import math
from pullback import pullback_zone
from datetime import date, datetime, timezone

def indicators(days):
    if len(days)<65: raise ValueError('At least 65 completed daily bars required')
    for i,b in enumerate(days):
        try:
            values={k:float(b[k]) for k in ('high','low','close','volume')}
            if 'open' in b:values['open']=float(b['open'])
        except (KeyError,TypeError,ValueError):
            raise ValueError('Daily bar '+str(i)+' has missing or invalid OHLCV fields') from None
        if (not all(math.isfinite(v) for v in values.values()) or
            values['low']<=0 or values['volume']<0 or
            not values['low']<=values['close']<=values['high'] or
            ('open' in values and not values['low']<=values['open']<=values['high'])):
            raise ValueError('Daily bar '+str(i)+' has non-finite or inconsistent OHLCV fields')
    if sum(float(x['volume']) for x in days[-21:-1])<=0:
        raise ValueError('Average daily volume must be positive')
    close=[float(x['close']) for x in days]
    tr=[max(float(a['high'])-float(a['low']),abs(float(a['high'])-float(b['close'])),abs(float(a['low'])-float(b['close']))) for a,b in zip(days[1:],days)]
    return dict(ma20=sum(close[-20:])/20,ma50=sum(close[-50:])/50,atr=sum(tr[-14:])/14,avgvol=sum(float(x['volume']) for x in days[-21:-1])/20,rvol=float(days[-1]['volume'])/(sum(float(x['volume']) for x in days[-21:-1])/20))

def swing(price,days,cfg,reasons=None):
    def reject(reason):
        if reasons is not None:reasons.append(reason)
        return None
    m=indicators(days)
    if not (price>=cfg['min_price'] and m['avgvol']>=cfg['min_avg_volume']): return reject('Price or average volume')
    zone=pullback_zone(price,days,m['atr'])
    if not zone or not zone['in_zone']:return reject('Outside 38.2%–61.8% verified swing pullback or anchors unavailable')
    trend_failed=not m['ma20']>m['ma50']
    volume_failed=not m['rvol']>=cfg['swing_min_rvol']
    if trend_failed:
        reject(f"Uptrend failed: 20-day average ${m['ma20']:.4f} must exceed 50-day average ${m['ma50']:.4f}")
    if volume_failed:
        reject(f"Completed-day relative volume failed: {m['rvol']:.4f}x; minimum {cfg['swing_min_rvol']:.4f}x (latest volume {float(days[-1]['volume']):,.0f} / prior 20-day average {m['avgvol']:,.0f})")
    if trend_failed or volume_failed:return None
    last,prev=days[-1],days[-2]
    if 'open' not in last or not(float(last['close'])>float(last['open']) and float(last['close'])>float(prev['high']) and price>float(prev['high'])):
        return reject('No completed bullish reversal and current-price hold')
    if min(float(d['low']) for d in days[-3:])<zone['zone_low']-.5*m['atr']:return reject('Pullback support breached')
    stop=min(float(d['low']) for d in days[-5:])-.1*m['atr']
    risk=price-stop
    if risk<=0 or risk>2*m['atr']: return reject('Stop risk outside limits')
    resistance=sorted(set(float(d['high']) for d in days[:-2] if float(d['high'])>price))
    # Targets are actual historical resistance, never manufactured to meet R/R.
    if len(resistance)<2: return reject('Insufficient historical targets')
    t1=resistance[0];t2=next((v for v in resistance if v>=t1+.5*m['atr']),None)
    if t2 is None or (t1-price)/risk<cfg['swing_min_rr'] or t1-price>4*m['atr']: return reject('Target spacing or reward/risk')
    zone['entry_confirmed']=True
    return dict(entry=price,stop=round(stop,2),target1=t1,target2=t2,rr=round((t1-price)/risk,2),rvol=round(m['rvol'],2),ma20=round(m['ma20'],2),score=round(min(100,50+10*(t1-price)/risk+5*m['rvol']),1),pullback=zone,risk='Gaps can exceed the stop. Resistance may not be reached within several days to a few weeks.')

def put_candidate(price,option,cfg,today,zone=None,reasons=None):
    def reject(reason):
        if reasons is not None:reasons.append(reason)
        return None
    if option.get('option_type')!='put' or option.get('contract_size')!=100: return reject('Not a standard put')
    try:
        strike=float(option['strike']);bid=float(option['bid']);ask=float(option['ask']);delta=abs(float(option['greeks']['delta']));oi=int(option['open_interest'])
        dte=(date.fromisoformat(option['expiration_date'])-today).days
        stamps=[float(option[k])/1000 for k in ('bid_date','ask_date')]
        if any(abs(datetime.now(timezone.utc).timestamp()-t)>900 for t in stamps): return reject('Stale option quote')
    except (KeyError,TypeError,ValueError): return reject('Missing or invalid option fields')
    if not (cfg['put_dte_min']<=dte<=cfg['put_dte_max'] and cfg['put_delta_min']<=delta<=cfg['put_delta_max']): return reject('DTE or delta outside range')
    if not(0<bid<=ask and strike<price and strike*100<=cfg['cash_per_position'] and oi>=cfg['put_min_oi']): return reject('Bid/ask, collateral or open interest')
    otm=(price-strike)/price
    if not cfg['put_otm_min']-1e-9<=otm<=cfg['put_otm_max']+1e-9: return reject('Strike not 5–10% OTM')
    if zone is not None and strike>float(zone['high']): return reject('Strike above demand zone')
    spread=(ask-bid)/((ask+bid)/2)
    if ask-bid>cfg['put_max_spread_dollars']+1e-9: return reject('Dollar spread too wide')
    if spread>cfg['put_max_spread_fraction'] or bid/strike<cfg['put_min_yield']: return reject('Relative spread or premium yield')
    return dict(otm_pct=round(100*otm,2),spread_dollars=round(ask-bid,4),bid=bid,ask=ask,quote_timestamp=min(stamps),contract=option['symbol'],strike=strike,expiry=option['expiration_date'],dte=dte,delta=delta,premium=bid,collateral=strike*100,breakeven=round(strike-bid,2),yield_pct=round(100*bid/strike,2),max_profit=bid*100,max_loss=(strike-bid)*100,oi=oi,spread_pct=round(100*spread,2),score=round(100*bid/strike*20+(1-delta)*30-spread*20,1),risk='Assignment requires buying 100 shares. Maximum loss assumes the stock reaches zero; no stop guarantees an option exit.')



def fundamental_gate(research,cfg,today,reasons=None):
    """Fail closed on missing, old, or uncomputable fiscal evidence."""
    f=research.get('quality',{})
    try:
        age=(today-date.fromisoformat(f['period'][:10])).days
        vals=[float(f[k]) for k in ('revenue_growth_pct','fcf','current_ratio','debt_equity')]
        if not all(math.isfinite(v) for v in vals) or not 0<=age<=550:
            if reasons is not None:reasons.append('Non-finite metrics or annual period outside 0–550 days')
            return None
        growth,fcf,current,debt=vals
        failures=[]
        if growth<=0:failures.append('Annual revenue is not increasing')
        if fcf<=0:failures.append('Annual free cash flow is not positive')
        if current<cfg['min_current_ratio']:failures.append('Current ratio below minimum')
        if not 0<=debt<=cfg['max_debt_equity']:failures.append('Total liabilities/equity '+str(round(debt,4))+' outside 0–'+str(cfg['max_debt_equity']))
        if failures:
            if reasons is not None:reasons.extend(failures)
            return None
        return f
    except (KeyError,TypeError,ValueError):
        if reasons is not None:reasons.append('Required fundamental metric missing or invalid')
        return None

def demand_zone(price,days,cfg,reasons=None,diagnostics=None,*,retest_window=5):
    """Confirmed pivot, subsequent retest and bullish close; never a forward-looking pivot."""
    if isinstance(retest_window,bool) or not isinstance(retest_window,int) or not 1<=retest_window<=45:
        raise ValueError('Retest window must be an integer from 1 to 45')
    m=indicators(days);a=m['atr']
    if not math.isfinite(price) or price<=0:raise ValueError('Current price must be finite and positive')
    if any('open' not in b for b in days):raise ValueError('Demand confirmation requires daily open prices')
    if a<=0:
        if reasons is not None:reasons.append('ATR must be positive')
        return None
    audit=diagnostics if diagnostics is not None else {}
    audit.update(bars=len(days),atr=a,price=price,lookback_bars=45,
                 retest_window_bars=retest_window,max_distance_atr=cfg['demand_max_distance_atr'],
                 candidates=[])
    pivots=retests=intact=0
    # Two right-hand confirmation bars, then at least one later retest bar.
    # Index n-4 is eligible: n-3/n-2 confirm and n-1 can retest.
    for i in range(len(days)-4,max(2,len(days)-45)-1,-1):
        low=float(days[i]['low'])
        if not all(low<float(days[j]['low']) for j in (i-2,i-1,i+1,i+2)):continue
        pivots+=1
        upper=low+.5*a
        candidate=dict(pivot_date=days[i].get('date'),low=low,high=upper,
                       distance_atr=(price-upper)/a,outcome='No recent bullish retest')
        audit['candidates'].append(candidate)
        invalid=next((x for x in days[i+1:] if float(x['low'])<low),None)
        if invalid is not None:
            candidate.update(outcome='Invalidated by lower low',invalidated_date=invalid.get('date'))
        for j in range(max(i+3,len(days)-retest_window),len(days)):
            b=days[j]
            if not(low<=float(b['low'])<=upper and float(b['close'])>upper and float(b['close'])>float(b.get('open',b['close']))):continue
            retests+=1
            candidate['retest_date']=b.get('date')
            if invalid is not None:continue
            intact+=1
            candidate['outcome']='Current price outside zone distance limits'
            if upper<price<=upper+cfg['demand_max_distance_atr']*a:
                candidate['outcome']='Confirmed'
                audit.update(pivots=pivots,bullish_retests=retests,intact_retests=intact)
                # Keep exact boundaries for strike eligibility; round only in the UI.
                return dict(low=low,high=upper,pivot_date=days[i].get('date'),confirmed_date=b.get('date'),method='Daily pivot + retest + bullish close above zone')
    audit.update(pivots=pivots,bullish_retests=retests,intact_retests=intact)
    if reasons is not None:
        reasons.append('No confirmed pivot in lookback' if not pivots else
                       ('No bullish retest within last five completed sessions' if retest_window==5 else
                        'No bullish retest within last '+str(retest_window)+' completed sessions') if not retests else
                       'Retested zones invalidated by a lower low' if not intact else
                       'Current price not above intact zone within configured ATR distance')
    return None


def demand_watch_candidate(audit):
    """Research only: intact pivot within distance, still missing confirmation."""
    candidates=[c for c in audit.get('candidates',[])
                if c.get('outcome')=='No recent bullish retest'
                and 'invalidated_date' not in c
                and 0<c['distance_atr']<=audit['max_distance_atr']]
    if not candidates:return None
    candidate=min(candidates,key=lambda c:c['distance_atr'])
    return dict(zone={k:candidate[k] for k in ('low','high','pivot_date')},
                distance_atr=candidate['distance_atr'],trade_eligible=False,
                pending='Bullish retest within five completed sessions',
                unchecked=['Fundamentals','Trend and swing rules','Options liquidity and risk','Earnings'],
                note='Watchlist only. A new scan must pass every trade filter before qualification.')
