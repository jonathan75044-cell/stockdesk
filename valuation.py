"""Explicit per-share FCFE DCF model. Research only; never an eligibility gate."""
import math
import re
from datetime import date

FIELDS={'symbol','annual_fcfe_per_share','growth_pct','discount_pct','terminal_growth_pct','years','evidence_date','notes'}


def validate_model(data,today):
    if not isinstance(data,dict) or set(data)!=FIELDS:raise ValueError('Invalid valuation fields')
    if not isinstance(data['symbol'],str) or not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',data['symbol']):
        raise ValueError('Use the dashboard symbol, such as BRK.B')
    result=dict(data)
    for field in ('annual_fcfe_per_share','growth_pct','discount_pct','terminal_growth_pct','years'):
        value=data[field]
        if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
            raise ValueError('Valuation inputs must be finite numbers')
    if not 0<data['annual_fcfe_per_share']<=1000000:raise ValueError('Annual FCFE per share must be positive')
    if not -50<=data['growth_pct']<=30:raise ValueError('Forecast growth must be between -50% and 30%')
    if not 1<=data['discount_pct']<=50:raise ValueError('Cost of equity must be between 1% and 50%')
    if not 0<=data['terminal_growth_pct']<=5:raise ValueError('Terminal growth must be between 0% and 5%')
    if data['discount_pct']<=data['terminal_growth_pct']:raise ValueError('Cost of equity must exceed terminal growth')
    if not 1<=data['years']<=10 or int(data['years'])!=data['years']:raise ValueError('Forecast years must be an integer from 1 to 10')
    result['years']=int(data['years'])
    try:
        evidence=date.fromisoformat(data['evidence_date'])
    except (TypeError,ValueError):raise ValueError('Evidence date must be YYYY-MM-DD') from None
    if not 0<=(today-evidence).days<=550:raise ValueError('Cash-flow evidence date must be within the last 550 days')
    if not isinstance(data['notes'],str) or not 1<=len(data['notes'].strip())<=1000:
        raise ValueError('Add an evidence source and normalization note (up to 1000 characters)')
    result['notes']=data['notes'].strip()
    return result


def estimate(price,model,today):
    if model is None:return {'status':'unavailable','reason':'Add annual FCFE per share and DCF assumptions'}
    try:
        m=validate_model(model,today)
        if isinstance(price,bool) or not isinstance(price,(int,float)) or not math.isfinite(price) or price<=0:
            raise ValueError('A finite positive stock price is required')
        cash=m['annual_fcfe_per_share'];g=m['growth_pct']/100
        r=m['discount_pct']/100;t=m['terminal_growth_pct']/100;n=m['years']
        forecasts=[cash*(1+g)**year for year in range(1,n+1)]
        explicit=sum(value/(1+r)**year for year,value in enumerate(forecasts,1))
        terminal=forecasts[-1]*(1+t)/(r-t)/(1+r)**n
        fair=explicit+terminal
        if not math.isfinite(fair) or fair<=0:raise ValueError('Model does not produce a finite positive value')
        gap=100*(price/fair-1)
        classification='fairly valued' if abs(gap)<.005 else 'undervalued' if gap<0 else 'overvalued'
        return {'status':'estimated','method':'FCFE DCF estimate','currency':'USD',
                'intrinsic_value':fair,'valuation_pct':round(abs(gap),2),'classification':classification,
                'signed_gap_pct':round(gap,2),'price_used':price,'assumptions':m,
                'pv_forecast':explicit,'pv_terminal':terminal,
                'terminal_value_share_pct':100*terminal/fair,
                'note':'User-supplied normalized FCFE per share, fixed share-count assumption, and cost of equity. Model estimate, not a verified fair value. Percentage compares price with intrinsic value, not potential return.'}
    except ValueError as error:return {'status':'unavailable','reason':str(error)}
