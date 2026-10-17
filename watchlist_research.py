"""Independent research; never changes eligibility."""
import json,time,math
from datetime import date,datetime,timezone,timedelta
from engine import fundamental_gate
from provider import FundamentalDataError

def enrich_watchlists(state,data,cfg,today,get,save,budget=60):
    deadline=time.monotonic()+budget
    groups={}
    for item in state.get('golden_zones',[])+state.get('watchlist',[]):groups.setdefault(item['symbol'],[]).append(item)
    criteria=json.dumps([str(today),cfg['min_current_ratio'],cfg['max_debt_equity'],cfg['earnings_buffer_days']])
    for symbol,items in groups.items():
        report={}
        for field in ('financial','earnings'):
            key='watchlist_research:'+symbol+':'+field;cached=get(key,{})
            if cached.get('criteria')==criteria and 0<=time.time()-cached.get('checked_at',0)<3600:
                report[field]=cached['value'];continue
            if time.monotonic()>=deadline:
                report[field]={'status':'unavailable','reason':'Research time budget reached; retry on a later scan'};continue
            checked=datetime.now(timezone.utc).isoformat()
            try:
                if field=='financial':
                    q=data.quality(symbol,today)
                    vals=[float(q[k]) for k in ('revenue_growth_pct','fcf','current_ratio','debt_equity')]
                    age=(today-date.fromisoformat(q['period'][:10])).days
                    if not all(math.isfinite(v) for v in vals) or not 0<=age<=550:raise ValueError('Invalid annual evidence')
                    reasons=[];passed=bool(fundamental_gate({'quality':q},cfg,today,reasons))
                    value={'status':'passed' if passed else 'failed','reason':'; '.join(reasons) or 'Annual financial checks passed','period':q['period'],'source':q.get('source','Annual financial provider')}
                else:
                    end=today+timedelta(days=14+cfg['earnings_buffer_days'])
                    events=data.fh('calendar/earnings',symbol=symbol,**{'from':str(today),'to':str(end)})['earningsCalendar']
                    if not isinstance(events,list):raise ValueError('Invalid calendar')
                    dates=sorted(set(date.fromisoformat(e['date']) for e in events))
                    upcoming=[str(d) for d in dates if today<=d<=end]
                    value={'status':'blocked' if upcoming else 'no_event_returned','reason':('Earnings in exclusion window: '+', '.join(upcoming)) if upcoming else 'No event returned; calendar may be incomplete. Recheck before entry.','window_end':str(end)}
            except FundamentalDataError as error:value={'status':'unavailable','reason':str(error)[:600]}
            except Exception:value={'status':'unavailable','reason':('Annual financial evidence missing, invalid or provider unavailable' if field=='financial' else 'Earnings calendar missing, invalid or provider unavailable')}
            value['checked_at']=checked;report[field]=value
            save(key,{'criteria':criteria,'checked_at':time.time(),'value':value})
        for item in items:
            item['watchlist_research']=report
            if item.get('entry_plan'):
                item['entry_plan']['financial_status']=report['financial']['status']+': '+report['financial']['reason']
                item['entry_plan']['earnings_status']=report['earnings']['status']+': '+report['earnings']['reason']
