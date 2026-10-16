"""Shared dated resistance evidence; targets are selected without reference to desired R/R."""
import math
from datetime import date

METHOD='Strict 2-left/2-right confirmed swing highs in the last 90 completed daily bars; nearest above entry first'

def resistance_levels(days,entry,atr):
    bars=days[-90:]
    dates=[date.fromisoformat(b['date']) for b in bars]
    highs=[float(b['high']) for b in bars]
    if any(a>=b for a,b in zip(dates,dates[1:])) or any(not math.isfinite(h) or h<=0 for h in highs):
        raise ValueError('Invalid resistance history')
    pivots=[i for i in range(2,len(bars)-2) if highs[i]>entry and all(highs[i]>highs[j] for j in (i-2,i-1,i+1,i+2))]
    # Equal-price pivots share one level; retain the most recent supporting date.
    levels={highs[i]:{'price':highs[i],'date':str(dates[i]),'confirmed_date':str(dates[i+2])} for i in pivots}
    ordered=[levels[h] for h in sorted(levels)]
    first=ordered[0] if ordered else None
    second=next((v for v in ordered[1:] if v['price']>=first['price']+.5*atr),None) if first else None
    obstacles=[{'price':h,'date':str(dates[i])} for i,h in enumerate(highs) if h>entry and (first is None or h<first['price'])]
    nearest=min(obstacles,key=lambda x:(x['price'],-date.fromisoformat(x['date']).toordinal()),default=None)
    return {'target1':first,'target2':second,'nearest_overhead_high':nearest,'method':METHOD}
