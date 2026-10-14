"""Bounded, authenticated research signals. Never grant trade eligibility."""
import hashlib,hmac,json,math,re,time
from contextlib import closing
from datetime import datetime,timezone

class AlertError(ValueError):
    def __init__(self,message,code=400):super().__init__(message);self.code=code

def validate_alert(payload,secret,universe,now=None):
    now=time.time() if now is None else now
    if not secret or len(secret)<32:raise AlertError('TradingView alerts are not configured',503)
    if not isinstance(payload,dict):raise AlertError('Invalid alert')
    supplied=payload.get('token')
    if not isinstance(supplied,str) or not hmac.compare_digest(supplied.encode(),secret.encode()):raise AlertError('Unauthorized',401)
    if set(payload)-{'token','symbol','exchange','time','trigger','price'}:raise AlertError('Unexpected alert fields')
    symbol=payload.get('symbol');exchange=payload.get('exchange')
    if not isinstance(symbol,str) or not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',symbol):raise AlertError('Use the Stockdesk stock symbol')
    if symbol not in universe:raise AlertError('Symbol is not in the configured stock universe')
    if exchange not in ('NYSE','NASDAQ','AMEX','BATS','ARCA','NYSEARCA'):raise AlertError('Unsupported stock exchange')
    trigger=payload.get('trigger')
    if not isinstance(trigger,str) or not re.fullmatch(r'[A-Za-z0-9 _.-]{1,80}',trigger):raise AlertError('Use a short trigger label')
    try:
        when=datetime.fromisoformat(payload['time'].replace('Z','+00:00'))
        if when.tzinfo is None:raise ValueError()
        ts=when.timestamp()
    except (KeyError,ValueError,TypeError,AttributeError):raise AlertError('Use the TradingView timenow placeholder')
    if not 0<=now-ts<=300:raise AlertError('Alert timestamp is stale or future-dated')
    price=payload.get('price')
    if price is not None:
        try:price=float(price)
        except (ValueError,TypeError):raise AlertError('Invalid alert price')
        if isinstance(payload['price'],bool) or not math.isfinite(price) or price<=0:raise AlertError('Invalid alert price')
    event={'symbol':symbol,'exchange':exchange,'trigger':trigger,'signal_at':when.astimezone(timezone.utc).isoformat(),'received_at':now,'signal_price':price,'status':'Pending review'}
    event['id']=hashlib.sha256(json.dumps([symbol,exchange,trigger,event['signal_at']],separators=(',',':')).encode()).hexdigest()
    return event

def enqueue(conn,event):
    with closing(conn()) as c:
        try:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('select v from kv where k=?',('tradingview_events',)).fetchone()
            events=json.loads(row[0]) if row else []
            if any(e['id']==event['id'] for e in events):return {'accepted':True,'duplicate':True}
            if sum(e['received_at']>=event['received_at']-60 for e in events)>=10 or sum(e['status']=='Pending review' for e in events)>=50:raise AlertError('Alert queue is full; retry later',429)
            events.append(event)
            # Retain pending work plus up to 100 recently completed events.
            pending=[e for e in events if e['status']=='Pending review']
            done=[e for e in events if e['status']!='Pending review'][-100:]
            c.execute('insert or replace into kv values (?,?)',('tradingview_events',json.dumps(sorted(done+pending,key=lambda e:e['received_at']))))
            c.commit()
            return {'accepted':True,'duplicate':False}
        finally:c.close()

def update(conn,event_id,changes):
    with closing(conn()) as c:
        try:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('select v from kv where k=?',('tradingview_events',)).fetchone()
            events=json.loads(row[0]) if row else []
            for event in events:
                if event['id']==event_id:event.update(changes)
            c.execute('insert or replace into kv values (?,?)',('tradingview_events',json.dumps(events)));c.commit()
        finally:c.close()
