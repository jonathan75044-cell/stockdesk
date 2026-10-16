"""Dated benchmark context; never used as an eligibility gate."""
import math
from datetime import date


def close_series(days):
    rows=[(str(b['date']),float(b['close'])) for b in days]
    dates=[d for d,c in rows]
    if dates!=sorted(set(dates)) or any(not math.isfinite(c) or c<=0 for d,c in rows):
        raise ValueError('Invalid daily closes')
    for d,c in rows:date.fromisoformat(d)
    return rows


def load_market_context(data,cutoff,today,completed_today=False):
    result={}
    for symbol in ('SPY','QQQ'):
        try:
            rows=close_series(data.days(symbol,cutoff))
            if len(rows)<50:raise ValueError('Insufficient history')
            day= date.fromisoformat(rows[-1][0])
            if day>=cutoff or not 0<=(today-day).days<=5:raise ValueError('History out of date')
            close=rows[-1][1];ma20=sum(c for d,c in rows[-20:])/20;ma50=sum(c for d,c in rows[-50:])/50
            result[symbol]={'available':True,'data_date':str(day),'close':close,'ma20':ma20,'ma50':ma50,
                'trend':'Uptrend' if close>ma20>ma50 else 'Downtrend' if close<ma20<ma50 else 'Mixed',
                'freshness':'Latest completed session missing' if completed_today and day!=today else 'Completed closing data; verify date',
                'recent_closes':rows[-21:]}
        except Exception:
            result[symbol]={'available':False,'reason':'Benchmark history unavailable or invalid; retry with a fresh scan.'}
    return result


def relative_strength(days,context):
    result={}
    try:rows=close_series(days)[-21:]
    except (ValueError,KeyError,TypeError):rows=[]
    for symbol in ('SPY','QQQ'):
        benchmark=context.get(symbol,{})
        series=benchmark.get('recent_closes',[])
        if len(rows)!=21 or len(series)!=21 or [d for d,c in rows]!=[d for d,c in series]:
            result[symbol]={'available':False,'reason':'Matching 20-session dates unavailable'}
            continue
        stock_return=100*(rows[-1][1]/rows[0][1]-1)
        benchmark_return=100*(series[-1][1]/series[0][1]-1)
        result[symbol]={'available':True,'start_date':rows[0][0],'end_date':rows[-1][0],
                        'stock_return':stock_return,'benchmark_return':benchmark_return,
                        'difference_pp':stock_return-benchmark_return}
    return result
