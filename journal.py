"""Manual trade journal. Uses the application's existing persistent SQLite database."""
import json, re, uuid, math
from datetime import date, datetime, timezone

def validate(data):
    if not isinstance(data,dict): raise ValueError('Invalid entry')
    out={}
    for key,limit in [('symbol',12),('strategy',30),('status',20),('opened',10),('closed',10),('expiry',10),('thesis',6000),('review',6000)]:
        value=data.get(key,'')
        if not isinstance(value,str) or len(value)>limit: raise ValueError('Invalid '+key)
        out[key]=value.strip()
    out['symbol']=out['symbol'].upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,11}',out['symbol']): raise ValueError('Enter a valid ticker')
    if out['strategy'] not in ['Swing shares','Cash-secured put']: raise ValueError('Invalid strategy')
    if out['status'] not in ['Planned','Open','Closed','Assigned']: raise ValueError('Invalid status')
    for key in ['opened','closed','expiry']:
        if out[key]: date.fromisoformat(out[key])
    for key in ['quantity','entry','exit','fees','strike','delta','stop','target','demand','supply']:
        value=data.get(key)
        if value is None or value=='': out[key]=None;continue
        if isinstance(value,bool):raise ValueError('Invalid '+key)
        value=float(value)
        if not math.isfinite(value) or value<0 or value>1e9:raise ValueError('Invalid '+key)
        out[key]=value
    if not out['quantity'] or out['quantity']!=int(out['quantity']):raise ValueError('Quantity must be a positive whole number')
    if out['entry'] is None:raise ValueError('Entry price or premium is required')
    if out['delta'] is not None and out['delta']>1:raise ValueError('Absolute delta must be between 0 and 1')
    if out['strategy']=='Cash-secured put' and (not out['strike'] or not out['expiry']):raise ValueError('Put strike and expiry are required')
    if out['status']=='Assigned' and out['strategy']!='Cash-secured put':raise ValueError('Assigned applies only to puts')
    if out['status'] in ['Open','Closed','Assigned'] and not out['opened']:raise ValueError('Entry date is required')
    if out['status'] in ['Closed','Assigned'] and not out['closed']:raise ValueError('Close or assignment date is required')
    if out['status']=='Closed' and out['exit'] is None:raise ValueError('Enter exit price; use zero for an expired worthless put')
    if out['closed'] and out['opened'] and out['closed']<out['opened']:raise ValueError('Close date precedes entry')
    return out

def table(c): c.execute('CREATE TABLE IF NOT EXISTS journal (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
def rows(connect):
    with connect() as c:
        table(c); result=[dict(json.loads(r[1]),id=r[0]) for r in c.execute('SELECT id,data FROM journal')]
    for r in result:
        r['pnl']=None
        if r['status']=='Closed':
            sign=1 if r['strategy']=='Swing shares' else -1
            multiplier=1 if sign==1 else 100
            r['pnl']=round(sign*(r['exit']-r['entry'])*r['quantity']*multiplier-(r['fees'] or 0),2)
    return sorted(result,key=lambda r:r['updated_at'],reverse=True)
def write(connect,data):
    entry=validate(data); identifier=data.get('id') or str(uuid.uuid4())
    if not isinstance(identifier,str) or not re.fullmatch(r'[a-f0-9-]{36}',identifier):raise ValueError('Invalid entry ID')
    entry['updated_at']=datetime.now(timezone.utc).isoformat()
    with connect() as c:
        table(c)
        if data.get('id') and not c.execute('SELECT 1 FROM journal WHERE id=?',(identifier,)).fetchone():raise ValueError('Entry no longer exists')
        c.execute('INSERT OR REPLACE INTO journal VALUES (?,?)',(identifier,json.dumps(entry)))
    return identifier
