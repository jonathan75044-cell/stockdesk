"""Read live Schwab transactions into a separate broker ledger; never submit orders."""
import hashlib,json,threading,time
from datetime import datetime,timedelta,timezone
from urllib.parse import quote
import requests
LOCK=threading.Lock()

def read_api(client,path,**params):
    r=requests.get('https://api.schwabapi.com/trader/v1/'+path,params=params,
                   headers={'Authorization':'Bearer '+client.access()},timeout=30)
    if not r.ok:raise ValueError('Account history unavailable. Check Schwab authorization and Accounts and Trading Production access.')
    return r.json()

def table(c):
    c.execute('CREATE TABLE IF NOT EXISTS schwab_ledger (id TEXT PRIMARY KEY, data TEXT NOT NULL)')

def normalize(account,tx):
    if tx.get('type')!='TRADE':return None
    aid=tx.get('activityId')
    if aid is None:raise ValueError('Broker transaction is missing its stable identifier')
    legs=[]
    for item in tx.get('transferItems',[]):
        ins=item.get('instrument') or {}
        if ins.get('assetType') not in ('EQUITY','OPTION'):continue
        legs.append({'symbol':ins.get('symbol','Unknown'),'asset':ins['assetType'],
                     'quantity':item.get('amount'),'price':item.get('price'),
                     'effect':item.get('positionEffect',''),'put_call':ins.get('putCall','')})
    if not legs:return None
    return {'id':hashlib.sha256((account+'|'+str(aid)).encode()).hexdigest(),
            'account':'Account '+hashlib.sha256(account.encode()).hexdigest()[:8],
            'activity_id':str(aid),'date':tx.get('tradeDate') or tx.get('time',''),
            'description':tx.get('description',''),'net_amount':tx.get('netAmount'),
            'status':tx.get('status',''),'legs':legs}

def sync(connect,get,save,client,reader=read_api):
    if not LOCK.acquire(False):return
    try:
        now=datetime.now(timezone.utc)
        # Re-read a rolling window so delayed postings and revisions update existing rows.
        start=now-timedelta(days=30)
        accounts=reader(client,'accounts/accountNumbers')
        if not isinstance(accounts,list) or not accounts:raise ValueError('No authorized live Schwab accounts returned')
        records=[]
        for account in accounts:
            hashed=account.get('hashValue')
            if not hashed:raise ValueError('Account identifier unavailable')
            txs=reader(client,'accounts/'+quote(hashed,safe='')+'/transactions',
                       startDate=start.isoformat(timespec='milliseconds').replace('+00:00','Z'),
                       endDate=now.isoformat(timespec='milliseconds').replace('+00:00','Z'),types='TRADE')
            if not isinstance(txs,list):raise ValueError('Unexpected account history response')
            for tx in txs:
                row=normalize(hashed,tx)
                if row:records.append(row)
        added=0
        with connect() as c:
            table(c)
            for row in records:
                added+=not bool(c.execute('SELECT 1 FROM schwab_ledger WHERE id=?',(row['id'],)).fetchone())
                c.execute('INSERT OR REPLACE INTO schwab_ledger VALUES (?,?)',(row['id'],json.dumps(row)))
        save('schwab_import_status',{'ok':True,'at':now.isoformat(),'new':added,'accounts':len(accounts),'message':'Live account history synced; postings may lag execution.'})
    except Exception:
        save('schwab_import_status',{'ok':False,'at':datetime.now(timezone.utc).isoformat(),'message':'Sync failed. Check Schwab connection and Accounts and Trading Production permission. Prior imported records are retained.'})
    finally:LOCK.release()

def rows(connect):
    with connect() as c:
        table(c)
        return sorted([json.loads(r[0]) for r in c.execute('SELECT data FROM schwab_ledger')],key=lambda r:r['date'],reverse=True)

def worker(connect,get,save,client_factory):
    while True:
        if get('schwab_import_enabled',True):sync(connect,get,save,client_factory())
        time.sleep(300)
