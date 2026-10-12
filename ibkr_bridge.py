"""Run beside the authenticated IBKR Client Portal Gateway. Portfolio GETs only."""
import os,time,hashlib
from datetime import datetime,timezone
from urllib.parse import quote,urlparse
import requests

FIELDS=('conid','contractDesc','ticker','position','mktPrice','mktValue','currency','avgCost','avgPrice','realizedPnl','unrealizedPnl','assetClass','expiry','putOrCall','strike','multiplier')
def snapshot(session,base,verify):
    def read(path):
        r=session.get(base+path,timeout=25,verify=verify);r.raise_for_status();return r.json()
    accounts=read('/portfolio/accounts')
    if not isinstance(accounts,list):raise ValueError('Account list unavailable')
    result=[]
    for account in accounts:
        aid=account.get('accountId') or account.get('id')
        if not aid:raise ValueError('Missing account identifier')
        prefix='/portfolio/'+quote(str(aid),safe='')
        summary=read(prefix+'/summary');ledger=read(prefix+'/ledger')
        positions=[]
        for page in range(100):
            rows=read(prefix+'/positions/'+str(page))
            if not isinstance(rows,list):raise ValueError('Positions unavailable')
            positions.extend({k:v for k,v in r.items() if k in FIELDS} for r in rows if float(r.get('position',0))!=0)
            if len(rows)<100:break
        else:raise ValueError('Position pagination incomplete')
        safe_summary={k:v for k,v in summary.items() if k.lower() in ('netliquidation','totalcashvalue','availablefunds','buyingpower','excessliquidity','grosspositionvalue')}
        safe_ledger={c:{k:v for k,v in r.items() if k in ('currency','cashbalance','settledcash','netliquidationvalue','stockmarketvalue','stockoptionmarketvalue','exchangerate')} for c,r in ledger.items() if isinstance(r,dict)}
        result.append({'label':'Account …'+str(aid)[-4:],'key':hashlib.sha256(str(aid).encode()).hexdigest()[:16], 'summary':safe_summary,'ledger':safe_ledger,'positions':positions})
    return {'source':'IBKR Client Portal Gateway','captured_at':datetime.now(timezone.utc).isoformat(),'accounts':result}

def main():
    base=os.getenv('IBKR_GATEWAY_URL','https://localhost:5000/v1/api').rstrip('/')
    dest=os.environ['STOCKDESK_URL'].rstrip('/')
    if urlparse(dest).scheme!='https':raise ValueError('Dashboard requires HTTPS')
    if urlparse(base).scheme!='https':raise ValueError('Gateway requires HTTPS')
    verify=os.getenv('IBKR_CA_BUNDLE') or True
    token=os.environ['BROKER_SYNC_TOKEN']
    session=requests.Session();session.trust_env=False
    while True:
        try:
            payload=snapshot(session,base,verify)
            r=requests.post(dest+'/api/broker/snapshot',json=payload,headers={'Authorization':'Bearer '+token},timeout=30,allow_redirects=False)
            if r.status_code!=200:raise ValueError('Snapshot delivery rejected')
            print('Portfolio snapshot synchronized.',flush=True)
        except Exception:
            print('Sync failed. Check gateway login, TLS trust, network, and sync settings. Dashboard snapshot will age.',flush=True)
        time.sleep(300)
if __name__=='__main__':main()
