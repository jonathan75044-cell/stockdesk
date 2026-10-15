"""Dated daily-bar pullbacks, separate from valuation and entry eligibility."""
import math
from datetime import date

METHOD='Latest confirmed 2-left/2-right pivot high in 90 completed sessions; lowest preceding confirmed pivot low 5–60 bars earlier; upward leg at least 2 ATR'

def pullback_zone(price, days, atr):
    if not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0:
        raise ValueError('Invalid pullback price')
    if not math.isfinite(atr) or atr<=0 or len(days)<9:return None
    bars=days[-90:]
    if any(not b.get('date') for b in bars):return None
    dates=[date.fromisoformat(b['date']) for b in bars]
    if any(a>=b for a,b in zip(dates,dates[1:])):raise ValueError('Daily dates must increase')
    for b in bars:
        lo,hi=float(b['low']),float(b['high'])
        if not all(math.isfinite(v) for v in (lo,hi)) or not 0<lo<=hi:raise ValueError('Invalid swing bar')
    highs=[i for i in range(2,len(bars)-2) if all(float(bars[i]['high'])>float(bars[j]['high']) for j in (i-2,i-1,i+1,i+2))]
    if not highs:return None
    hi=highs[-1]
    lows=[i for i in range(max(2,hi-60),hi-4) if all(float(bars[i]['low'])<float(bars[j]['low']) for j in (i-2,i-1,i+1,i+2))]
    if not lows:return None
    li=min(lows,key=lambda i:float(bars[i]['low']))
    low,high=float(bars[li]['low']),float(bars[hi]['high'])
    if high-low<2*atr:return None
    r=(high-price)/(high-low)
    inside=.382-1e-10<=r<=.618+1e-10
    return dict(low=low,high=high,low_date=bars[li]['date'],high_date=bars[hi]['date'],
                last_bar_date=bars[-1]['date'],retracement=r,zone_low=high-.618*(high-low),
                zone_high=high-.382*(high-low),priority_high=high-.5*(high-low),
                in_zone=inside,priority=inside and r>=.5-1e-10,
                source='Schwab completed daily OHLC history',method=METHOD,
                entry_confirmed=False,valuation_status='Separate valuation assessment required',
                holding_period='Several days to a few weeks')
