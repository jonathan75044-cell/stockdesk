import live_import
import os,json,time,threading,hashlib,hmac,base64,sqlite3,secrets
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
from schwab import Schwab
import journal
import requests
from provider import Data
from broker import validate_snapshot,portfolio_status
from engine import indicators,swing,put_candidate,fundamental_gate,demand_zone
ROOT=Path(__file__).parent
STORE=Path(os.getenv('DATA_DIR',str(ROOT/'data')));STORE.mkdir(exist_ok=True,parents=True)
DB=STORE/'state.db'
lock=threading.Lock()
def conn():
    c=sqlite3.connect(DB);c.execute('create table if not exists kv (k text primary key,v text)');return c
def get(k,default=None):
    with conn() as c:r=c.execute('select v from kv where k=?',(k,)).fetchone()
    return json.loads(r[0]) if r else default
def save(k,v):
    with conn() as c:c.execute('insert or replace into kv values (?,?)',(k,json.dumps(v)))
def config():
    defaults=json.loads((ROOT/'config.json').read_text())
    saved=get('config',{})
    if get('rules_version')!=3:
        # One-time migration of the requested filters; preserve universe, cash and notification preferences.
        keys=('put_delta_min','put_delta_max','put_otm_min','put_otm_max',
              'put_min_oi','put_max_spread_fraction','put_max_spread_dollars',
              'min_avg_volume','min_current_ratio','max_debt_equity','swing_min_rr')
        saved.update({k:defaults[k] for k in keys})
        save('config',saved);save('rules_version',3)
        previous=get('state',{})
        previous.update(status='Rules updated · awaiting fresh scan',rows=[],completed_at=None)
        save('state',previous);save('morning_digest',None)
    return {**defaults,**saved}
def stamp():return datetime.now(timezone.utc).isoformat()
def status():
    state=get('state',{'status':'Setup required','rows':[],'errors':[]})
    state['configured']=bool(Schwab().connected() and os.getenv('FINNHUB_TOKEN'))
    state['market_data_source']='Charles Schwab'
    state['schwab']={'configured':Schwab().configured(),'connected':Schwab().connected()}
    state['notification_configured']=bool(os.getenv('ALERT_WEBHOOK_URL'))
    state['morning_digest']=get('morning_digest');state['config']=config();state['alerts']=get('alerts',[])[-30:]
    state['stale']=not state.get('completed_at') or (datetime.now(timezone.utc)-datetime.fromisoformat(state['completed_at'])).total_seconds()>4200
    return state

def scan(morning=False):
    if not lock.acquire(False):return
    try:
        cfg=config();data=Data()
        if not data.token or not data.finn:
            save('state',{'status':'Setup required · connect Schwab and configure Finnhub','rows':[],'errors':[]});return
        if data.clock()['state']!='open':
            s=get('state',{'rows':[]});s['status']='Market closed · agent waiting';save('state',s);return
        today=datetime.now(ZoneInfo('America/New_York')).date()
        symbols=list(dict.fromkeys(cfg['universe'].split()))
        state={'status':'Scanning','started_at':stamp(),'rows':[],'errors':[],'scanned':0,'total':len(symbols),'diagnostics':[]};save('state',state)
        for symbol in symbols:
            detail={'symbol':symbol,'outcome':'Processing','stage':'Quote'}
            state['diagnostics'].append(detail)
            try:
                q=data.quotes([symbol])[0]
                ts=float(q['trade_date'])/1000
                if abs(time.time()-ts)>900:raise ValueError('Stale underlying quote')
                detail['stage']='Daily history'
                price=float(q['last']);days=data.days(symbol,today);m=indicators(days)
                if not days or (today-datetime.fromisoformat(days[-1]['date']).date()).days>5: raise ValueError('Daily history stale')
                if price<cfg['min_price']:
                    detail['outcome']='Below minimum price';continue
                if m['avgvol']<cfg['min_avg_volume']:
                    detail['outcome']='Below minimum average volume';continue
                detail['stage']='Demand zone'
                detail['demand_rejections']=[]
                zone=demand_zone(price,days,cfg,detail['demand_rejections'])
                if not zone:
                    detail['outcome']='No confirmed demand zone';continue
                detail['stage']='Finnhub research'
                research=data.research(symbol,today,cfg['put_dte_max']+cfg['earnings_buffer_days'])
                detail['fundamental_rejections']=[]
                quality=fundamental_gate(research,cfg,today,detail['fundamental_rejections'])
                if not quality:
                    detail['outcome']='Fundamentals failed or missing';detail['fundamentals']=research.get('quality',{});continue
                detail['stage']='Swing and options'
                detail['swing_rejections']=[];detail['put_rejections']={}
                sw=swing(price,days,cfg,detail['swing_rejections'])
                puts=[];detail['contracts_checked']=0
                detail['put_trend_passed']=price>m['ma20']>m['ma50']
                if price>m['ma20']>m['ma50']:
                    for opt in data.options(symbol,today,cfg):
                        reasons=[];detail['contracts_checked']+=1
                        candidate=put_candidate(price,opt,cfg,today,zone,reasons)
                        for reason in reasons:detail['put_rejections'][reason]=detail['put_rejections'].get(reason,0)+1
                        if candidate:puts.append(candidate)
                if not(sw or puts):
                    detail['outcome']='No qualifying swing or put';continue
                dates=[datetime.fromisoformat(e['date']).date() for e in research['earnings'] if e.get('date')]
                if any(d<=today+timedelta(days=14+cfg['earnings_buffer_days']) for d in dates):sw=None
                puts=[c for c in puts if not any(d<=datetime.fromisoformat(c['expiry']).date()+timedelta(days=cfg['earnings_buffer_days']) for d in dates)]
                if not(sw or puts):
                    detail['outcome']='Earnings exclusion';continue
                best=max(puts,key=lambda c:c['score']) if puts else None
                row={'quality':quality,'demand_zone':zone,'symbol':symbol,'name':q.get('description',symbol),'price':price,'volume':q.get('volume'),'quote_at':datetime.fromtimestamp(ts,timezone.utc).isoformat(),'swing':sw,'put':best,'score':max(sw['score'] if sw else 0,best['score'] if best else 0),'research':research,'ma20':m['ma20'],'ma50':m['ma50'],'asof':stamp(),'earnings_note':'No scheduled event returned in the screened horizon; calendar may change.'}
                state['rows'].append(row);detail['outcome']='Qualified before final freshness and result limit'
            except Exception as e:
                detail['outcome']='Data or processing error'
                detail['error_type']=type(e).__name__
                # Do not expose URLs containing API keys.
                state['errors'].append({'symbol':symbol,'reason':str(e) if isinstance(e,ValueError) else type(e).__name__+' · data unavailable'})
            finally:
                state['scanned']+=1;save('state',state)
        state['rows']=[r for r in state['rows'] if time.time()-datetime.fromisoformat(r['quote_at']).timestamp()<=900 and (not r['put'] or time.time()-r['put']['quote_timestamp']<=900)]
        state['rows']=sorted(state['rows'],key=lambda x:x['score'],reverse=True)[:cfg['max_results']]
        selected={r['symbol'] for r in state['rows']}
        for detail in state['diagnostics']:
            if detail['outcome']=='Qualified before final freshness and result limit':
                detail['outcome']='Displayed' if detail['symbol'] in selected else 'Final freshness or result limit exclusion'
        state['status']='Monitoring';state['completed_at']=stamp();save('state',state)
        if morning:
            digest={'date':str(today),'completed_at':stamp(),'rows':state['rows'],'errors':state['errors'],'note':'Qualified at scan time; recheck live quotes before acting.'}
            save('morning_digest',digest);save('morning_done',str(today))
        if cfg['notifications_enabled'] and os.getenv('ALERT_WEBHOOK_URL') and data.clock()['state']=='open':
            if morning and state['rows'] and get('morning_sent')!=str(today):
                try:
                    brief=[{'symbol':r['symbol'],'price':r['price'],'put':r['put'],'swing':r['swing'],'demand_zone':r['demand_zone']} for r in state['rows']]
                    response=requests.post(os.environ['ALERT_WEBHOOK_URL'],json={'text':json.dumps({'message':'Morning qualifying setups','date':str(today),'setups':brief})},timeout=15);response.raise_for_status();save('morning_sent',str(today))
                except requests.RequestException:
                    state['errors'].append({'reason':'Morning digest delivery failed'});save('state',state);save('morning_done',None)
            for row in ([] if morning else state['rows']):
                if (datetime.now(timezone.utc)-datetime.fromisoformat(row['quote_at'])).total_seconds()>900:continue
                kinds=','.join(k for k in ('swing','put') if row[k]);key=str(today)+':'+row['symbol']+':'+kinds
                if get('sent:'+key):continue
                payload={'text':json.dumps({'message':'Qualified screen · review before trading','stock':row,'sources':['Tradier market data','Finnhub research'],'risks':'Earnings schedules can change; price gaps, assignment, concentration and liquidity risk.'},indent=2)}
                try:
                    response=requests.post(os.environ['ALERT_WEBHOOK_URL'],json=payload,timeout=15);response.raise_for_status()
                    save('sent:'+key,True);alerts=get('alerts',[]);alerts.append({'at':stamp(),'symbol':row['symbol'],'type':kinds});save('alerts',alerts[-200:])
                except requests.RequestException:state['errors'].append({'symbol':row['symbol'],'reason':'Notification delivery failed'});save('state',state)
    except Exception as e:
        s=get('state',{'rows':[]});s['status']='Data connection error';s['errors']=[{'reason':type(e).__name__}];save('state',s)
    finally:lock.release()

def cfg_morning_due(now,cfg,done):
    return cfg['morning_scan_minute']<=now.hour*60+now.minute<720 and done!=str(now.date())

def agent():
    # Exchange clock handles U.S. holidays, weekends, and early closes.
    while True:
        if Schwab().connected() and os.getenv('FINNHUB_TOKEN'):
            try:
                now=datetime.now(ZoneInfo('America/New_York'))
                slot=str(now.date())+':'+str((now.hour*60+now.minute-570)//60)
                minute=now.hour*60+now.minute
                morning=cfg_morning_due(now,config(),get('morning_done'))
                if Data().clock()['state']=='open' and (morning or get('last_slot')!=slot):
                    save('last_slot',slot);scan(morning=morning)
            except Exception:pass
        time.sleep(60)

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def auth(self):
        password=os.getenv('DASHBOARD_PASSWORD','')
        if not password and os.getenv('APP_ENV')=='production':
            self.send_error(503,'Configure DASHBOARD_PASSWORD');return False
        if not password:return True
        expected='Basic '+base64.b64encode(('admin:'+password).encode()).decode()
        if not hmac.compare_digest(self.headers.get('Authorization',''),expected):
            self.send_response(401);self.send_header('WWW-Authenticate','Basic realm="Stockdesk"');self.end_headers();return False
        return True
    def respond(self,value,code=200):
        raw=json.dumps(value).encode();self.send_response(code);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if urlparse(self.path).path=='/health':self.respond({'ok':True});return
        if not self.auth():return
        path=urlparse(self.path).path
        if path=='/auth/schwab/start':
            try:
                state=secrets.token_urlsafe(32)
                url=Schwab().authorize_url(state)
                save('oauth:'+hashlib.sha256(state.encode()).hexdigest(),time.time()+600)
                self.send_response(302);self.send_header('Location',url)
                self.send_header('Set-Cookie','schwab_state='+state+'; Secure; HttpOnly; SameSite=Lax; Path=/auth/schwab; Max-Age=600')
                self.send_header('Cache-Control','no-store');self.end_headers()
            except Exception:self.respond({'error':'Configure Schwab credentials and HTTPS callback in Render first'},400)
            return
        if path=='/auth/schwab/callback':
            try:
                query=parse_qs(urlparse(self.path).query)
                state=query.get('state',[''])[0]
                cookies=SimpleCookie();cookies.load(self.headers.get('Cookie',''))
                cookie=cookies.get('schwab_state')
                if not state or not cookie or not hmac.compare_digest(state,cookie.value):raise ValueError()
                key='oauth:'+hashlib.sha256(state.encode()).hexdigest()
                # Atomically consume state to prevent concurrent replay.
                with conn() as c:
                    c.execute('BEGIN IMMEDIATE')
                    row=c.execute('select v from kv where k=?',(key,)).fetchone()
                    c.execute('delete from kv where k=?',(key,))
                if not row or json.loads(row[0])<time.time():raise ValueError()
                Schwab().finish(query['code'][0])
                self.send_response(302);self.send_header('Location','/')
                self.send_header('Set-Cookie','schwab_state=; Secure; HttpOnly; SameSite=Lax; Path=/auth/schwab; Max-Age=0')
                self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.end_headers()
            except Exception:self.respond({'error':'Schwab authorization failed or expired. Start Connect Schwab again.'},400)
            return
        if path=='/api/journal/schwab':self.respond({'entries':live_import.rows(conn),'status':get('schwab_import_status',{}),'enabled':get('schwab_import_enabled',True)});return
        if path=='/api/journal':self.respond({'entries':journal.rows(conn)});return
        if path=='/diagnostics':
            raw=(ROOT/'diagnostics.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
        if path=='/journal':
            raw=(ROOT/'journal.html').read_bytes();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
        if self.path=='/api/portfolio':self.respond(portfolio_status(get('ibkr_portfolio')));return
        if self.path=='/api/state':self.respond(status());return
        if self.path!='/':self.send_error(404);return
        raw=(ROOT/'index.html').read_bytes().replace(b'</header>',b'<a href="/journal" style="margin:0 18px;color:inherit">Trade journal</a><a href="/diagnostics" style="margin:0 18px;color:inherit">Scan diagnostics</a></header>',1);self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        if self.path=='/api/broker/snapshot':
            token=os.getenv('BROKER_SYNC_TOKEN','')
            if len(token)<32 or not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
                self.respond({'error':'Unauthorized'},401);return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=2000000:raise ValueError()
                data=validate_snapshot(json.loads(self.rfile.read(n)))
                save('ibkr_portfolio',data);self.respond({'ok':True})
            except Exception:self.respond({'error':'Invalid portfolio snapshot'},400)
            return
        if not self.auth():return
        if self.headers.get('X-Stockdesk')!='1':self.respond({'error':'Request rejected'},403);return
        if self.path=='/api/journal/schwab/sync':
            threading.Thread(target=live_import.sync,args=(conn,get,save,Schwab()),daemon=True).start();self.respond({'queued':True});return
        if self.path=='/api/journal/schwab/toggle':
            save('schwab_import_enabled',not get('schwab_import_enabled',True));self.respond({'ok':True});return
        if self.path=='/api/journal':
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=32000:raise ValueError('Entry is too large')
                identifier=journal.write(conn,json.loads(self.rfile.read(n)))
                self.respond({'ok':True,'id':identifier})
            except (ValueError,TypeError,OverflowError):self.respond({'error':'Invalid entry. Check dates, quantity, prices, and required put fields. Closed trades need an exit price and close date.'},400)
            return
        if self.path=='/api/scan':threading.Thread(target=scan,daemon=True).start();self.respond({'queued':True});return
        if self.path=='/api/config':
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<16000:raise ValueError()
                data=json.loads(self.rfile.read(n));base=json.loads((ROOT/'config.json').read_text())
                if set(data)!=set(base):raise ValueError()
                import re
                if not isinstance(data['universe'],str) or not 1<=len(data['universe'].split())<=500 or any(not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',s) for s in data['universe'].split()):raise ValueError()
                for k,v in base.items():
                    if isinstance(v,bool):
                        if not isinstance(data[k],bool):raise ValueError()
                    elif isinstance(v,(int,float)):
                        if isinstance(data[k],bool) or not isinstance(data[k],(int,float)) or not 0<float(data[k])<1000000000:raise ValueError()
                if not 1<=data['max_results']<=50 or int(data['max_results'])!=data['max_results']:raise ValueError()
                data['max_results']=int(data['max_results'])
                if not 0<data['put_delta_min']<=data['put_delta_max']<1 or data['put_dte_min']>data['put_dte_max']:raise ValueError()
                if data['swing_min_rr']<2:raise ValueError()
                if not 0<data['put_otm_min']<=data['put_otm_max']<1:raise ValueError()
                if not 570<=data['morning_scan_minute']<720 or int(data['morning_scan_minute'])!=data['morning_scan_minute']:raise ValueError()
                save('config',data);self.respond({'ok':True})
            except Exception:self.respond({'error':'Invalid settings. Use positive numbers, delta below 1, R/R ≥2, and a result limit of 1–50.'},400)
            return
        self.send_error(404)
if __name__=='__main__':
    threading.Thread(target=live_import.worker,args=(conn,get,save,Schwab),daemon=True).start()
    threading.Thread(target=agent,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT','8000'))),Handler).serve_forever()
