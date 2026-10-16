import live_import
import os,json,time,threading,hashlib,hmac,base64,sqlite3,secrets,math,logging
from pathlib import Path
from datetime import datetime,timezone,timedelta
from zoneinfo import ZoneInfo
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from http.cookies import SimpleCookie
from contextlib import closing
from schwab import Schwab
import journal
import requests
from provider import Data,FundamentalDataError
from broker import validate_snapshot,portfolio_status
from engine import indicators,swing,put_candidate,fundamental_gate,demand_zone,demand_watch_candidate
from pullback import pullback_zone
BUILD='after-hours-research-2026-10-15'
logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
logger=logging.getLogger('stockdesk')
from valuation import validate_model,estimate
from decision import review_symbol
from auto_fcfe import estimate_automatic
from sec_fundamentals import SECDataError
import tradingview_alerts
review_lock=threading.Lock()
ROOT=Path(__file__).parent
STORE=Path(os.getenv('DATA_DIR',str(ROOT/'data')));STORE.mkdir(exist_ok=True,parents=True)
DB=STORE/'state.db'
lock=threading.Lock()
def conn():
    c=sqlite3.connect(DB);c.execute('create table if not exists kv (k text primary key,v text)');return c
def get(k,default=None):
    with closing(conn()) as c:r=c.execute('select v from kv where k=?',(k,)).fetchone()
    return json.loads(r[0]) if r else default
def save(k,v):
    with closing(conn()) as c, c:c.execute('insert or replace into kv values (?,?)',(k,json.dumps(v)))
def config():
    defaults=json.loads((ROOT/'config.json').read_text())
    saved=get('config',{})
    if get('rules_version')!=5:
        # One-time migration of the requested filters; preserve universe, cash and notification preferences.
        keys=('put_delta_min','put_delta_max','put_otm_min','put_otm_max',
              'put_min_oi','put_max_spread_fraction','put_max_spread_dollars',
              'min_avg_volume','min_current_ratio','max_debt_equity','swing_min_rr')
        if get('rules_version') not in (3,4):saved.update({k:defaults[k] for k in keys})
        save('config',saved);save('rules_version',5)
        previous=get('state',{})
        save('previous_scan',previous)
        previous=dict(status='Rules updated · awaiting fresh scan',rows=[],watchlist=[],golden_zones=[],completed_at=None,started_at=None,scanned=0,total=0,diagnostics=[],errors=[])
        save('state',previous);save('morning_digest',None)
        save('latest_review',None)
    if get('scan_state_version')!=1:
        previous=get('state',{})
        if not previous.get('completed_at') and previous.get('status')!='Scanning' and previous.get('scan_build')!=BUILD:
            if previous.get('diagnostics'):save('previous_scan',previous)
            save('state',dict(status=previous.get('status','Awaiting fresh scan'),rows=[],watchlist=[],golden_zones=[],completed_at=None,started_at=None,scanned=0,total=0,diagnostics=[],errors=[]))
        save('scan_state_version',1)
    return {**defaults,**saved}
def stamp():return datetime.now(timezone.utc).isoformat()
def json_evidence(value):
    """Keep optional malformed numeric evidence from breaking the browser JSON."""
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:json_evidence(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [json_evidence(v) for v in value]
    return value
def status():
    active_config=config()
    state=get('state',{'status':'Setup required','rows':[],'errors':[]})
    state['build']=BUILD
    state.setdefault('watchlist',[])
    state.setdefault('golden_zones',[])
    models=get('valuation_models',{})
    state['valuation_models']=models
    state['latest_review']=get('latest_review')
    state['tradingview']={'configured':len(os.getenv('TRADINGVIEW_WEBHOOK_TOKEN',''))>=32,'events':get('tradingview_events',[])[-100:]}
    review=state['latest_review']
    if review and review.get('status')=='Completed':
        session_end=(review.get('clock') or {}).get('regular_session_end')
        try:market_ready=datetime.now(timezone.utc)<datetime.fromisoformat(session_end)
        except (TypeError,ValueError):market_ready=False
        review['market_ready']=market_ready
        if not market_ready:
            review['swing_eligible']=False
            for condition in review.get('checks',[]):
                if condition['name']=='Regular market session':condition['status']='fail' if session_end else 'unknown'
        review_ts=review.get('quote',{}).get('trade_date')
        review['stale']=not isinstance(review_ts,(int,float)) or not 0<=time.time()-review_ts/1000<=900
        if review['stale']:review['swing_eligible']=False
        if review['stale']:
            for condition in review.get('checks',[]):
                if condition['name']=='Underlying quote freshness':condition['status']='fail'
        for opt in review.get('options',[]):
            opt_ts=opt.get('quote_timestamp')
            opt['stale']=not isinstance(opt_ts,(int,float)) or not 0<=time.time()-opt_ts<=900
            if review['stale'] or opt['stale'] or not market_ready:opt['trade_eligible']=False
            if opt['stale']:
                for condition in opt.get('checks',[]):
                    if condition['name']=='Quote freshness':condition['status']='fail'
        review['eligible_contract_count']=sum(o['trade_eligible'] for o in review.get('options',[]))
    state['decision_preferences']=get('decision_preferences',json.loads((ROOT/'decision_defaults.json').read_text()))
    valuation_today=datetime.now(ZoneInfo('America/New_York')).date()
    for item in state.get('rows',[])+state.get('watchlist',[]):
        review=get('review:'+item['symbol'],{})
        cached_auto=get('automatic_valuation:'+item['symbol'],{})
        automatic=cached_auto.get('value') or state.get('automatic_valuations',{}).get(item['symbol']) or (review.get('valuation',{}) if review.get('valuation',{}).get('input_source')=='Automatic SEC evidence' else {})
        automatic_model=automatic.get('assumptions')
        item['valuation']=estimate(item.get('price'),models.get(item['symbol']) or automatic_model,valuation_today)
        if item['symbol'] not in models and automatic and automatic.get('status')!='estimated':item['valuation']=automatic
        if automatic_model and item['symbol'] not in models:
            item['valuation']['input_source']='Automatic SEC evidence'
            item['valuation']['note']=automatic.get('note')
            item['valuation']['input_audit']=automatic.get('input_audit')
            item['valuation']['method']=automatic.get('method')
            share_end=automatic.get('input_audit',{}).get('facts',{}).get('EntityCommonStockSharesOutstanding',{}).get('end')
            try:share_fresh=0<=(valuation_today-datetime.fromisoformat(share_end).date()).days<=150
            except (TypeError,ValueError):share_fresh=False
            if not share_fresh:item['valuation']={'status':'unavailable','reason':'Automatic share-count evidence is stale or unavailable'}
    state['configured']=bool(Schwab().connected() and os.getenv('FINNHUB_TOKEN'))
    state['market_data_source']='Charles Schwab'
    state['schwab']={'configured':Schwab().configured(),'connected':Schwab().connected()}
    state['notification_configured']=bool(os.getenv('ALERT_WEBHOOK_URL'))
    state['morning_digest']=get('morning_digest');state['config']=active_config;state['alerts']=get('alerts',[])[-30:]
    state['stale']=not state.get('completed_at') or (datetime.now(timezone.utc)-datetime.fromisoformat(state['completed_at'])).total_seconds()>4200
    return state


def run_review(symbol):
    try:
        save('latest_review',{'symbol':symbol,'status':'Waiting for current scan','started_at':stamp()})
        with lock:
            save('latest_review',{'symbol':symbol,'status':'Reviewing','started_at':stamp()})
            today=datetime.now(ZoneInfo('America/New_York')).date()
            result=json_evidence(review_symbol(Data(),symbol,config(),today,get('valuation_models',{}).get(symbol)))
            if symbol not in get('valuation_models',{}):save('automatic_valuation:'+symbol,{'checked_at':time.time(),'value':result.get('valuation',{'status':'unavailable','reason':'Review evidence unavailable'})})
            save('review:'+symbol,result);save('latest_review',result)
    except Exception as error:
        save('latest_review',{'symbol':symbol,'status':'Unavailable','error':type(error).__name__+' · review failed'})
    finally:review_lock.release()

def tradingview_worker():
    while True:
        try:
            pending=[e for e in get('tradingview_events',[]) if e['status']=='Pending review']
            for event in pending:
                if time.time()-event['received_at']>900:
                    tradingview_alerts.update(conn,event['id'],{'status':'Expired — request a new review'});continue
                if lock.locked() or not review_lock.acquire(False):break
                run_review(event['symbol'])
                review=get('review:'+event['symbol'],{})
                latest=get('latest_review',{})
                complete=latest.get('status')=='Completed' and review.get('completed_at')==latest.get('completed_at')
                tradingview_alerts.update(conn,event['id'],{'status':'Reviewed' if complete else 'Review unavailable','reviewed_at':stamp(),'eligible_contract_count':review.get('eligible_contract_count',0) if complete else 0,'swing_eligible':bool(complete and review.get('swing_eligible'))})
        except Exception:pass  # Retry persisted pending work; do not log webhook credentials.
        time.sleep(2)

def request_scan():
    if not lock.acquire(False):
        return {'queued':False,'message':'A scan is already running.'},409
    worker_started=False
    try:
        config()
        data=Data()
        if not data.token or not data.finn:
            return {'queued':False,'message':'Connect Schwab and configure Finnhub before scanning.'},409
        research=data.clock()['state']!='open'
        threading.Thread(target=scan,kwargs={'lock_owned':True},daemon=True).start()
        worker_started=True
    except Exception as error:
        logger.error('Manual scan request failed (%s)',type(error).__name__)
        return {'queued':False,'message':'Unable to start scan. Check data connection and server logs.'},503
    else:
        return {'queued':True,'message':'After-hours research started. Closing prices only; live entry checks remain pending.' if research else 'Live scan started.'},202
    finally:
        # The worker owns the reservation only after a successful start.
        if not worker_started:lock.release()

def scan(morning=False,lock_owned=False):
    if not lock_owned and not lock.acquire(False):return
    try:
        cfg=config();data=Data()
        if not data.token or not data.finn:
            save('state',{'status':'Setup required · connect Schwab and configure Finnhub','rows':[],'errors':[]});return
        market=data.clock();research_mode=market['state']!='open'
        today=datetime.now(ZoneInfo('America/New_York')).date()
        symbols=list(dict.fromkeys('XYZ' if x.upper()=='SQ' else x.upper() for x in cfg['universe'].split()))
        state={'status':'Scanning','started_at':stamp(),'rows':[],'watchlist':[],'golden_zones':[],'scan_build':BUILD,'research_only':research_mode,'data_dates':[],'errors':[],'scanned':0,'total':len(symbols),'diagnostics':[]};save('state',state)
        logger.info('Scan started: %s symbols',len(symbols))
        for symbol in symbols:
            detail={'symbol':symbol,'outcome':'Processing','stage':'Quote'}
            state['diagnostics'].append(detail)
            try:
                detail['stage']='Daily history'
                cutoff=today+timedelta(days=1) if research_mode and market.get('completed_today') else today
                days=data.days(symbol,cutoff)
                if not days or not 0<=(today-datetime.fromisoformat(days[-1]['date']).date()).days<=5:raise ValueError('Daily history stale')
                if research_mode:
                    price=float(days[-1]['close'])
                    if not math.isfinite(price) or price<=0:raise ValueError('Invalid closing price')
                    ts=datetime.fromisoformat(days[-1]['date']).replace(tzinfo=ZoneInfo('America/New_York')).timestamp()
                    q={'description':symbol,'volume':days[-1]['volume']}
                    if days[-1]['date'] not in state['data_dates']:state['data_dates'].append(days[-1]['date'])
                else:
                    q=data.quotes([symbol])[0];ts=float(q['trade_date'])/1000
                    if abs(time.time()-ts)>900:raise ValueError('Stale underlying quote')
                    price=float(q['last'])
                m=indicators(days)
                pullback=pullback_zone(price,days,m['atr'])
                detail['pullback']=pullback
                if pullback and pullback['in_zone']:
                    state['golden_zones'].append(dict(symbol=symbol,name=q.get('description',symbol),price=price,research_only=research_mode,data_date=days[-1]['date'],quote_at=datetime.fromtimestamp(ts,timezone.utc).isoformat(),**pullback))
                if price<cfg['min_price']:
                    detail['outcome']='Below minimum price';continue
                if m['avgvol']<cfg['min_avg_volume']:
                    detail['outcome']='Below minimum average volume';continue
                detail['stage']='Demand zone'
                detail['demand_rejections']=[]
                detail['demand_diagnostics']={}
                zone=demand_zone(price,days,cfg,detail['demand_rejections'],detail['demand_diagnostics'])
                detail['put_demand_pass']=bool(zone)
                detail['swing_rejections']=[]
                sw=swing(price,days,cfg,detail['swing_rejections'])
                detail['swing_technical_pass']=bool(sw)
                detail['legacy_swing_technical_pass']=bool(sw and zone)
                detail['volume_comparison']={str(v):bool(swing(price,days,{**cfg,'swing_min_rvol':v})) for v in (1.0,1.1,1.3)}
                detail['market_metrics']={'price':price,**m,'last_daily_bar':days[-1]['date']}
                if not zone:
                    watch=demand_watch_candidate(detail['demand_diagnostics'])
                    if watch:
                        watch.update(symbol=symbol,name=q.get('description',symbol),price=price,research_only=research_mode,data_date=days[-1]['date'],
                                     quote_at=datetime.fromtimestamp(ts,timezone.utc).isoformat())
                        state['watchlist'].append(watch)
                        detail['watchlist']=watch
                    if not sw:
                        detail['outcome']='Swing confirmation blocked; put demand unconfirmed';continue
                detail['stage']='Finnhub research'
                research=data.research(symbol,today,cfg['put_dte_max']+cfg['earnings_buffer_days'])
                detail['fundamental_source']=research.get('quality',{}).get('source')
                if research.get('quality',{}).get('sec_audit'):
                    detail['sec_audit']=research['quality']['sec_audit']
                detail['fundamental_rejections']=[]
                quality=fundamental_gate(research,cfg,today,detail['fundamental_rejections'])
                detail['leverage_rule']={'metric':'Total liabilities / total equity',
                                        'maximum':cfg['max_debt_equity'],
                                        'value':research.get('quality',{}).get('debt_equity')}
                if not quality:
                    detail['outcome']='Fundamentals failed or missing';detail['fundamentals']=research.get('quality',{});continue
                detail['stage']='Swing and options'
                detail['put_rejections']={}
                puts=[];detail['contracts_checked']=0
                detail['put_trend_passed']=price>m['ma20']>m['ma50']
                if not research_mode and zone and price>m['ma20']>m['ma50']:
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
                row={'research_only':research_mode,'data_date':days[-1]['date'],'market_ready':not research_mode,'quality':quality,'demand_zone':zone,'symbol':symbol,'name':q.get('description',symbol),'price':price,'volume':q.get('volume'),'quote_at':datetime.fromtimestamp(ts,timezone.utc).isoformat(),'swing':sw,'put':best,'score':max(sw['score'] if sw else 0,best['score'] if best else 0),'research':research,'ma20':m['ma20'],'ma50':m['ma50'],'asof':stamp(),'earnings_note':'No scheduled event returned in the screened horizon; calendar may change.'}
                state['rows'].append(row);detail['outcome']='Qualified before final freshness and result limit'
            except Exception as e:
                detail['outcome']='Data or processing error'
                if isinstance(e,FundamentalDataError):
                    detail['outcome']='Fundamentals failed or missing'
                    detail['fundamental_rejections']=[str(e)]
                detail['error_type']=type(e).__name__
                # Only controlled provider errors are safe to show verbatim.
                # Other exceptions can contain request URLs or credentials.
                if isinstance(e,ValueError) and not isinstance(e,requests.RequestException):detail['error']=str(e)
                if isinstance(e,(KeyError,TypeError,IndexError,ZeroDivisionError)):
                    detail['error']='Missing or invalid data during '+detail['stage']
                if isinstance(e,KeyError):detail['missing_field']=str(e.args[0])[:80]
                if isinstance(e,requests.RequestException):detail['error']='Provider request failed; check connectivity, access and rate limits'
                if hasattr(e,'details'):detail['financial_diagnostics']=e.details
                # Do not expose URLs containing API keys.
                state['errors'].append({'symbol':symbol,'stage':detail['stage'],'reason':detail.get('error',type(e).__name__+' · data unavailable')})
            finally:
                detail['swing_stage']=('Research candidate · live checks pending' if research_mode else 'Meets trade checks') if any(r['symbol']==symbol and r.get('swing') for r in state['rows']) else 'Awaiting confirmation' if detail.get('pullback',{} ) and detail['pullback'].get('in_zone') else 'Outside zone / unverified'
                detail['swing_blockers']=detail.get('swing_rejections',[])+detail.get('fundamental_rejections',[])
                if detail['outcome']!='Qualified before final freshness and result limit':detail['swing_blockers'].append(detail['outcome'])
                for item in state['golden_zones']:
                    if item['symbol']==symbol:item.update(swing_stage=detail['swing_stage'],swing_blockers=detail['swing_blockers'],legacy_demand_confirmed=detail.get('put_demand_pass',False),volume_comparison=detail.get('volume_comparison',{}))
                state['scanned']+=1;save('state',state)
        state['rows']=[r for r in state['rows'] if research_mode or (0<=time.time()-datetime.fromisoformat(r['quote_at']).timestamp()<=900 and (not r['put'] or 0<=time.time()-r['put']['quote_timestamp']<=900))]
        state['rows']=sorted(state['rows'],key=lambda x:x['score'],reverse=True)[:cfg['max_results']]
        state['watchlist']=sorted([w for w in state['watchlist'] if
            research_mode or 0<=time.time()-datetime.fromisoformat(w['quote_at']).timestamp()<=900],
            key=lambda w:(w['distance_atr'],w['symbol']))[:cfg['max_results']]
        # Enrich displayed tables only; these fields are never screening gates.
        state['status']='Loading table metadata';save('state',state)
        metadata_deadline=time.monotonic()+120
        for item in state['rows']+state['watchlist']:
            metadata_key='display_metadata:'+item['symbol']
            cached=get(metadata_key)
            cached_age=(datetime.now(timezone.utc)-datetime.fromisoformat(cached['retrieved_at'])).total_seconds() if cached else None
            if cached is not None and 0<=cached_age<3600:
                item['display_metadata']=cached
            elif time.monotonic()<metadata_deadline:
                item['display_metadata']=data.display_metadata(item['symbol'],item.get('research',{}).get('metrics'))
                save(metadata_key,item['display_metadata'])
            else:
                item['display_metadata']={'sector':None,'pe_ttm':None,'notes':['Metadata time budget reached; retry on a later scan']}
            detail=next((d for d in state['diagnostics'] if d['symbol']==item['symbol']),None)
            if detail is not None:detail['display_metadata']=item['display_metadata']
        # Extra display requests must not extend the freshness of trade quotes.
        state['status']='Loading automatic valuations';state['automatic_valuations']={};save('state',state)
        auto_deadline=time.monotonic()+90
        for item in state['rows']+state['watchlist']:
            if item['symbol'] in get('valuation_models',{}):continue
            key='automatic_valuation:'+item['symbol'];cached=get(key)
            if cached and 0<=time.time()-cached['checked_at']<86400:
                value=cached['value']
            elif not os.getenv('SEC_USER_AGENT'):
                value={'status':'unavailable','reason':'Configure SEC_USER_AGENT to enable automatic valuation inputs'}
            elif time.monotonic()<auto_deadline:
                try:
                    raw=getattr(data,'_annual_reports',{}).get(item['symbol'],{})
                    value=estimate_automatic(item['symbol'],raw.get('cik'),item['price'],today)
                except SECDataError as error:
                    value={'status':'unavailable','reason':str(error),'input_audit':error.details}
                except Exception as error:
                    value={'status':'unavailable','reason':type(error).__name__+' · automatic valuation evidence unavailable'}
                save(key,{'checked_at':time.time(),'value':value})
            else:value={'status':'unavailable','reason':'Automatic-data time budget reached; use Review or wait for a later scan'}
            state['automatic_valuations'][item['symbol']]=value
        state['rows']=[r for r in state['rows'] if research_mode or (0<=time.time()-datetime.fromisoformat(r['quote_at']).timestamp()<=900
                       and (not r['put'] or 0<=time.time()-r['put']['quote_timestamp']<=900))]
        state['watchlist']=[w for w in state['watchlist'] if research_mode or 0<=time.time()-datetime.fromisoformat(w['quote_at']).timestamp()<=900]
        selected={r['symbol'] for r in state['rows']}
        for detail in state['diagnostics']:
            if detail['outcome']=='Qualified before final freshness and result limit':
                detail['outcome']='Displayed' if detail['symbol'] in selected else 'Final freshness or result limit exclusion'
        state['status']='After-hours research complete · live checks pending' if research_mode else 'Monitoring';state['completed_at']=stamp();save('state',state)
        logger.info('Scan completed: %s/%s processed, %s results, %s watchlist entries, %s errors',state['scanned'],state['total'],len(state['rows']),len(state['watchlist']),len(state['errors']))
        if morning and not research_mode:
            digest={'date':str(today),'completed_at':stamp(),'rows':state['rows'],'errors':state['errors'],'note':'Qualified at scan time; recheck live quotes before acting.'}
            save('morning_digest',digest);save('morning_done',str(today))
        if not research_mode and cfg['notifications_enabled'] and os.getenv('ALERT_WEBHOOK_URL') and data.clock()['state']=='open':
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
                payload={'text':json.dumps({'message':'Qualified screen · review before trading','stock':row,'sources':['Charles Schwab market data',row['quality'].get('source','Annual fundamentals'),'Finnhub earnings and research'],'risks':'Earnings schedules can change; price gaps, assignment, concentration and liquidity risk.'},indent=2)}
                try:
                    response=requests.post(os.environ['ALERT_WEBHOOK_URL'],json=payload,timeout=15);response.raise_for_status()
                    save('sent:'+key,True);alerts=get('alerts',[]);alerts.append({'at':stamp(),'symbol':row['symbol'],'type':kinds});save('alerts',alerts[-200:])
                except requests.RequestException:state['errors'].append({'symbol':row['symbol'],'reason':'Notification delivery failed'});save('state',state)
    except Exception as e:
        logger.error('Scan failed (%s)',type(e).__name__)
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
            except Exception as error:logger.error('Scheduler failed (%s)',type(error).__name__)
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
        if path in ('/review_ui.js','/confirmation_ui.js','/pullback_ui.js','/put_display.js','/strategy_summary.js'):
            raw=(ROOT/path[1:]).read_bytes();self.send_response(200);self.send_header('Content-Type','text/javascript; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw);return
        if self.path!='/':self.send_error(404);return
        raw=(ROOT/'index.html').read_bytes().replace(b'</header>',b'<a href="/journal" style="margin:0 18px;color:inherit">Trade journal</a><a href="/diagnostics" style="margin:0 18px;color:inherit">Scan diagnostics</a></header>',1);self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        if self.path=='/api/tradingview/alert':
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=4096:raise tradingview_alerts.AlertError('Invalid alert size')
                if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':raise tradingview_alerts.AlertError('Use a JSON alert message')
                payload=json.loads(self.rfile.read(n))
                universe={'XYZ' if s=='SQ' else s for s in config()['universe'].split()}
                event=tradingview_alerts.validate_alert(payload,os.getenv('TRADINGVIEW_WEBHOOK_TOKEN',''),universe)
                self.respond(tradingview_alerts.enqueue(conn,event),202)
            except tradingview_alerts.AlertError as error:self.respond({'error':str(error)},error.code)
            except (ValueError,TypeError):self.respond({'error':'Invalid alert JSON'},400)
            except Exception:self.respond({'error':'Alert storage unavailable'},503)
            return
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
        if self.path=='/api/review':
            try:
                import re
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=1024:raise ValueError()
                payload=json.loads(self.rfile.read(n))
                if not isinstance(payload,dict) or set(payload)!={'symbol'}:raise ValueError()
                symbol=payload['symbol']
                if not isinstance(symbol,str) or not re.fullmatch(r'[A-Z][A-Z0-9.\-]{0,9}',symbol):raise ValueError()
                if not review_lock.acquire(False):self.respond({'error':'Another stock review is in progress'},409);return
                save('latest_review',{'symbol':symbol,'status':'Queued','started_at':stamp()})
                try:threading.Thread(target=run_review,args=(symbol,),daemon=True).start()
                except RuntimeError:
                    review_lock.release();self.respond({'error':'Could not start stock review'},503);return
                self.respond({'queued':True,'symbol':symbol})
            except (ValueError,TypeError):self.respond({'error':'Use an uppercase dashboard stock symbol'},400)
            return
        if self.path=='/api/decision-preferences':
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=2048:raise ValueError()
                prefs=json.loads(self.rfile.read(n))
                if not isinstance(prefs,dict) or set(prefs)!={'total_cash','max_swing_loss','max_position_pct'}:raise ValueError()
                import math
                for key,value in prefs.items():
                    if value is not None and (isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or value<=0):raise ValueError()
                if prefs['max_position_pct'] is not None and prefs['max_position_pct']>100:raise ValueError()
                save('decision_preferences',prefs);self.respond({'ok':True})
            except (ValueError,TypeError):self.respond({'error':'Use positive amounts; allocation cap must be at most 100%'},400)
            return
        if self.path=='/api/valuation':
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=8000:raise ValueError('Valuation request too large')
                model=validate_model(json.loads(self.rfile.read(n)),datetime.now(ZoneInfo('America/New_York')).date())
                # Atomically update one model without losing another concurrent edit.
                with closing(conn()) as c, c:
                    c.execute('BEGIN IMMEDIATE')
                    row=c.execute('select v from kv where k=?',('valuation_models',)).fetchone()
                    models=json.loads(row[0]) if row else {}
                    if model['symbol'] not in models and len(models)>=500:raise ValueError('Maximum 500 valuation models')
                    models[model['symbol']]=model
                    c.execute('insert or replace into kv values (?,?)',('valuation_models',json.dumps(models)))
                self.respond({'ok':True})
            except (ValueError,TypeError):self.respond({'error':'Invalid DCF model. Use positive FCFE per share, a cost of equity above terminal growth, 1–10 years, fresh evidence and source notes.'},400)
            return
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
        if self.path=='/api/scan':
            result,code=request_scan();self.respond(result,code);return
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
    threading.Thread(target=tradingview_worker,daemon=True).start()
    threading.Thread(target=live_import.worker,args=(conn,get,save,Schwab),daemon=True).start()
    threading.Thread(target=agent,daemon=True).start()
    ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT','8000'))),Handler).serve_forever()
