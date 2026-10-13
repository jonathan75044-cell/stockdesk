import math
from datetime import date, datetime, timezone

def indicators(days):
    if len(days)<65: raise ValueError('At least 65 completed daily bars required')
    close=[float(x['close']) for x in days]
    tr=[max(float(a['high'])-float(a['low']),abs(float(a['high'])-float(b['close'])),abs(float(a['low'])-float(b['close']))) for a,b in zip(days[1:],days)]
    return dict(ma20=sum(close[-20:])/20,ma50=sum(close[-50:])/50,atr=sum(tr[-14:])/14,avgvol=sum(float(x['volume']) for x in days[-21:-1])/20,rvol=float(days[-1]['volume'])/(sum(float(x['volume']) for x in days[-21:-1])/20))

def swing(price,days,cfg,reasons=None):
    def reject(reason):
        if reasons is not None:reasons.append(reason)
        return None
    m=indicators(days)
    if not (price>=cfg['min_price'] and m['avgvol']>=cfg['min_avg_volume']): return reject('Price or average volume')
    if not(price>m['ma20']>m['ma50'] and price<=m['ma20']+2*m['atr'] and m['rvol']>=cfg['swing_min_rvol']): return reject('Trend, MA distance or relative volume')
    # Completed daily breakout; current price must still hold that level.
    breakout=max(float(d['high']) for d in days[-21:-1])
    if min(price,float(days[-1]['close']))<=breakout: return reject('No completed breakout')
    stop=min(float(d['low']) for d in days[-5:])-.1*m['atr']
    risk=price-stop
    if risk<=0 or risk>2*m['atr']: return reject('Stop risk outside limits')
    resistance=sorted(set(float(d['high']) for d in days[:-21] if float(d['high'])>price))
    # Targets are actual historical resistance, never manufactured to meet R/R.
    if len(resistance)<2: return reject('Insufficient historical targets')
    t1=resistance[0];t2=next((v for v in resistance if v>=t1+.5*m['atr']),None)
    if t2 is None or (t1-price)/risk<cfg['swing_min_rr'] or t1-price>4*m['atr']: return reject('Target spacing or reward/risk')
    return dict(entry=price,stop=round(stop,2),target1=t1,target2=t2,rr=round((t1-price)/risk,2),rvol=round(m['rvol'],2),ma20=round(m['ma20'],2),score=round(min(100,50+10*(t1-price)/risk+5*m['rvol']),1),risk='Gaps can exceed the stop. Resistance may not be reached within 5–10 sessions.')

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



def fundamental_gate(research,cfg,today):
    """Fail closed on missing, old, or uncomputable fiscal evidence."""
    f=research.get('quality',{})
    try:
        age=(today-date.fromisoformat(f['period'][:10])).days
        vals=[float(f[k]) for k in ('revenue_growth_pct','fcf','current_ratio','debt_equity')]
        if not all(math.isfinite(v) for v in vals) or not 0<=age<=550:return None
        growth,fcf,current,debt=vals
        if not(growth>0 and fcf>0 and current>=cfg['min_current_ratio'] and 0<=debt<=cfg['max_debt_equity']):return None
        return f
    except (KeyError,TypeError,ValueError):return None

def demand_zone(price,days,cfg):
    """Confirmed pivot, subsequent retest and bullish close; never a forward-looking pivot."""
    m=indicators(days);a=m['atr']
    if a<=0:return None
    for i in range(len(days)-5,max(2,len(days)-45)-1,-1):
        low=float(days[i]['low'])
        if not all(low<float(days[j]['low']) for j in (i-2,i-1,i+1,i+2)):continue
        upper=low+.5*a
        for j in range(max(i+3,len(days)-5),len(days)):
            b=days[j]
            if not(low<=float(b['low'])<=upper and float(b['close'])>upper and float(b['close'])>float(b.get('open',b['close']))):continue
            if any(float(x['low'])<low for x in days[i+1:]):continue
            if upper<price<=upper+cfg['demand_max_distance_atr']*a:
                return dict(low=round(low,2),high=round(upper,2),pivot_date=days[i].get('date'),confirmed_date=b.get('date'),method='Daily pivot + retest + bullish close above zone')
    return None
