"""Conditional watchlist plans. Never changes trade eligibility or submits orders."""
import math


def swing_entry_plan(price,days,metrics,zone,cfg):
    atr=metrics['atr'];last,prev=days[-1],days[-2]
    ceil_cent=lambda n:math.ceil(n*100-1e-9)/100
    floor_cent=lambda n:math.floor(n*100+1e-9)/100
    reversal=('open' in last and float(last['close'])>float(last['open'])
              and float(last['close'])>float(prev['high']))
    threshold=float(prev['high'] if reversal else last['high'])
    entry=ceil_cent(max(price,threshold+.01))
    stop=floor_cent(min(float(b['low']) for b in days[-5:])-.1*atr)
    risk=entry-stop
    resistance=sorted(set(float(b['high']) for b in days[:-2] if float(b['high'])>entry))
    t1=resistance[0] if resistance else None
    t2=next((v for v in resistance if t1 is not None and v>=t1+.5*atr),None)
    minimum_rr=float(cfg['swing_min_rr'])
    rr=(t1-entry)/risk if t1 is not None and risk>0 else None
    max_entry=floor_cent((t1+minimum_rr*stop)/(1+minimum_rr)) if t1 is not None and stop>0 else None
    checks=[
        ('Minimum price',price>=cfg['min_price']),
        ('Average daily volume',metrics['avgvol']>=cfg['min_avg_volume']),
        ('20-day average above 50-day average',metrics['ma20']>metrics['ma50']),
        ('Completed-day relative volume',metrics['rvol']>=cfg['swing_min_rvol']),
        ('Completed bullish reversal',reversal),
        ('Current price holds above reversal threshold',reversal and price>threshold),
        ('Planning entry inside pullback zone',zone['zone_low']<=entry<=zone['zone_high']),
        ('Pullback support intact',min(float(b['low']) for b in days[-3:])>=zone['zone_low']-.5*atr),
        ('Positive stop and risk no greater than 2 ATR',stop>0 and 0<risk<=2*atr),
        ('Two historical resistance targets',t1 is not None and t2 is not None),
        ('First-target reward/risk meets minimum',rr is not None and rr>=minimum_rr),
        ('First target within 4 ATR',t1 is not None and 0<t1-entry<=4*atr),
    ]
    return {'status':'Conditional research plan','data_date':days[-1]['date'],
            'entry':entry,'stop':stop if stop>0 else None,'target1':t1,'target2':t2,
            'risk_per_share':round(risk,4) if stop>0 and risk>0 else None,
            'reward_risk':round(rr,4) if rr is not None else None,'minimum_rr':minimum_rr,
            'max_entry_for_rr':max_entry,'reversal_threshold':threshold,
            'trigger':('Reversal is present in the latest completed bar. Recheck a live price above '+str(round(threshold,2))+'.'
                       if reversal else 'Wait for a NEW completed daily bar to close above '+str(round(threshold,2))+' and above its own open; then rescan. These levels must be recalculated.'),
            'checks':[{'name':name,'passed':bool(passed)} for name,passed in checks],
            'average_volume':round(metrics['avgvol']),'minimum_average_volume':cfg['min_avg_volume'],
            'relative_volume':round(metrics['rvol'],3),'minimum_relative_volume':cfg['swing_min_rvol'],
            'financial_status':'Not evaluated','earnings_status':'Not evaluated',
            'method':'Planning entry: higher of snapshot price or confirmation threshold plus $0.01, rounded up. Stop: lowest of five completed daily lows minus 0.1 ATR, rounded down. Targets: historical highs before the last two bars; second at least 0.5 ATR above first.',
            'invalidation':'Rebuild after a new daily bar, a support break, or a price gap. Skip if first-target reward/risk is below the configured minimum. Stops can fill below the planned level.',
            'eligible':False}
