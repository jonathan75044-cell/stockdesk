from datetime import datetime,timezone
import math

def validate_snapshot(data):
    if not isinstance(data,dict) or data.get('source')!='IBKR Client Portal Gateway':raise ValueError()
    at=datetime.fromisoformat(data['captured_at'])
    age=(datetime.now(timezone.utc)-at).total_seconds()
    if not -60<=age<=600:raise ValueError()
    accounts=data['accounts']
    if not isinstance(accounts,list) or len(accounts)>100:raise ValueError()
    for account in accounts:
        if not isinstance(account.get('label'),str) or len(account['label'])>40:raise ValueError()
        if not isinstance(account.get('summary'),dict) or not isinstance(account.get('ledger'),dict):raise ValueError()
        if not isinstance(account.get('positions'),list) or len(account['positions'])>10000:raise ValueError()
        for row in account['positions']:
            if not isinstance(row,dict):raise ValueError()
            for key in ('position','mktPrice','mktValue'):
                if key in row and not math.isfinite(float(row[key])):raise ValueError()
    return data

def portfolio_status(data):
    if not data:return {'connected':False,'stale':True,'accounts':[]}
    age=(datetime.now(timezone.utc)-datetime.fromisoformat(data['captured_at'])).total_seconds()
    return {**data,'connected':True,'stale':age>900,'age_seconds':max(0,int(age))}
