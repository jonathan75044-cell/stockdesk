"""Schwab OAuth and GET-only market-data adapter. No trading endpoints."""
import json, os, secrets, threading, time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import urlencode
import requests

GUARD=threading.RLock()
NY=ZoneInfo('America/New_York')
SCHWAB_SYMBOLS={'BRK.B':'BRK/B'}

def market_symbol(symbol):
    return SCHWAB_SYMBOLS.get(symbol,symbol)

class Schwab:
    def __init__(self):
        self.key=os.getenv('SCHWAB_APP_KEY','')
        self.secret=os.getenv('SCHWAB_APP_SECRET','')
        self.callback=os.getenv('SCHWAB_CALLBACK_URL','')
        self.path=Path(os.getenv('DATA_DIR',str(Path(__file__).parent/'data')))/'schwab_tokens.json'
    def read(self):
        with GUARD:
            try:return json.loads(self.path.read_text())
            except (FileNotFoundError,ValueError):return {}
    def configured(self):return bool(self.key and self.secret and self.callback.startswith('https://'))
    def connected(self):
        t=self.read()
        return self.configured() and bool(t.get('refresh_token')) and time.time()<t.get('authorized_at',0)+7*86400
    def authorize_url(self,state):
        if not self.configured():raise ValueError('Configure Schwab app credentials and HTTPS callback first')
        return 'https://api.schwabapi.com/v1/oauth/authorize?'+urlencode({'client_id':self.key,'redirect_uri':self.callback,'response_type':'code','state':state})
    def exchange(self,**form):
        with GUARD:
            response=requests.post('https://api.schwabapi.com/v1/oauth/token',auth=(self.key,self.secret),data=form,timeout=25)
            if not response.ok:raise ValueError('Schwab authorization failed; reconnect from the dashboard')
            token=response.json()
            if not token.get('access_token'):raise ValueError('Schwab returned no access token')
            old=self.read()
            token['authorized_at']=time.time() if form['grant_type']=='authorization_code' else old.get('authorized_at',0)
            token['expires_at']=time.time()+float(token.get('expires_in',1800))-90
            if not token.get('refresh_token'):token['refresh_token']=old.get('refresh_token')
            self.path.parent.mkdir(parents=True,exist_ok=True)
            temp=self.path.with_suffix('.tmp')
            fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as f:json.dump(token,f)
            os.replace(temp,self.path)
            return token
    def finish(self,code):return self.exchange(grant_type='authorization_code',code=code,redirect_uri=self.callback)
    def access(self):
        with GUARD:
            if not self.connected():raise ValueError('Schwab connection requires authorization')
            t=self.read()
            if time.time()>=t.get('expires_at',0):t=self.exchange(grant_type='refresh_token',refresh_token=t['refresh_token'])
            return t['access_token']
    def get(self,path,**params):
        # Fixed prefix and GET-only transport prevent use of account/order APIs.
        if path not in ('quotes','pricehistory','chains','markets/equity'):raise ValueError('Unsupported market-data endpoint')
        time.sleep(.55)
        r=requests.get('https://api.schwabapi.com/marketdata/v1/'+path,params=params,headers={'Authorization':'Bearer '+self.access()},timeout=25)
        if r.status_code==401:
            with GUARD:
                t=self.read();self.exchange(grant_type='refresh_token',refresh_token=t.get('refresh_token',''))
            r=requests.get('https://api.schwabapi.com/marketdata/v1/'+path,params=params,headers={'Authorization':'Bearer '+self.access()},timeout=25)
        if not r.ok:raise ValueError('Schwab market data unavailable; check connection and Market Data Production access')
        return r.json()
    def clock(self):
        now=datetime.now(NY)
        raw=self.get('markets/equity',date=str(now.date()))
        market=raw.get('equity',{}).get('EQ',{})
        regular=market.get('sessionHours',{}).get('regularMarket',[])
        opened=bool(market.get('isOpen')) and any(datetime.fromisoformat(p['start'])<=now<datetime.fromisoformat(p['end']) for p in regular)
        current_session=next((p for p in regular if datetime.fromisoformat(p['start'])<=now<datetime.fromisoformat(p['end'])),None)
        return {'state':'open' if opened else 'closed','regular_session_end':current_session['end'] if opened and current_session else None}
    def quotes(self,symbols):
        raw=self.get('quotes',symbols=','.join(market_symbol(s) for s in symbols),fields='quote,reference')
        result=[]
        for symbol in symbols:
            item=raw.get(market_symbol(symbol),{})
            if not isinstance(item,dict) or not item:raise ValueError('Schwab returned no quote for '+symbol+'; verify symbol and coverage')
            if item.get('realtime') is not True:raise ValueError('Schwab quote for '+symbol+' is delayed or has no real-time flag; verify entitlement')
            q=item.get('quote',{})
            result.append({'symbol':symbol,'description':item.get('reference',{}).get('description',symbol),'last':q.get('lastPrice'),'volume':q.get('totalVolume'),'trade_date':q.get('tradeTime')})
        return result
    def days(self,symbol,today):
        raw=self.get('pricehistory',symbol=market_symbol(symbol),periodType='year',period=2,frequencyType='daily',frequency=1,needExtendedHoursData='false')
        rows=[]
        for c in raw.get('candles',[]):
            d=datetime.fromtimestamp(c['datetime']/1000,NY).date()
            if d<today:rows.append({**c,'date':str(d)})
        if len({row['date'] for row in rows})!=len(rows):raise ValueError('Schwab returned duplicate daily dates; history requires review')
        return sorted(rows,key=lambda c:c['date'])
    def options(self,symbol,today,cfg):
        raw=self.get('chains',symbol=market_symbol(symbol),contractType='PUT',strategy='SINGLE',includeUnderlyingQuote='true',fromDate=str(today+timedelta(days=cfg['put_dte_min'])),toDate=str(today+timedelta(days=cfg['put_dte_max'])))
        if raw.get('isDelayed') is not False:raise ValueError('Real-time Schwab option chain required')
        for exp,strikes in raw.get('putExpDateMap',{}).items():
            for contracts in strikes.values():
                for c in contracts:
                    if c.get('nonStandard') is not False:continue
                    yield {'symbol':c.get('symbol'),'option_type':'put','contract_size':c.get('multiplier'),'strike':c.get('strikePrice'),'expiration_date':exp.split(':')[0],'bid':c.get('bid'),'ask':c.get('ask'),'greeks':{k:c.get(k) for k in ('delta','gamma','theta','vega','rho')},'open_interest':c.get('openInterest'),'volume':c.get('totalVolume'),'iv_pct':c.get('volatility'),'bid_date':c.get('quoteTimeInLong'),'ask_date':c.get('quoteTimeInLong')}
    def intraday(self,today):
        now=datetime.now(NY)
        return self.get('pricehistory',symbol='JD',periodType='day',frequencyType='minute',frequency=15,startDate=int(datetime.combine(today-timedelta(days=35),datetime.min.time(),NY).timestamp()*1000),endDate=int(now.timestamp()*1000),needExtendedHoursData='false').get('candles',[])
