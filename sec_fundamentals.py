"""Conservative SEC companyfacts adapter. Explicitly verified issuers; no inferred custom concepts."""
import json
import math
import os
import re
import threading
import time
from datetime import date,datetime,timezone
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

CIKS={'DE':'0000315189','LRCX':'0000707549','PANW':'0001327567'}
REVENUE=('RevenueFromContractWithCustomerExcludingAssessedTax','Revenues',
         'SalesRevenueNet','RevenueFromContractWithCustomerIncludingAssessedTax')
_cache={}
CACHE_MAX_ENTRIES=4
CACHE_MAX_RESPONSE_BYTES=1000000
_guard=threading.Lock()
_last_request=0.0


class SECDataError(ValueError):
    def __init__(self,message,details=None):
        super().__init__('SEC fundamental evidence unavailable: '+message)
        self.details=details or {}


def fetch_json(path):
    """Fixed SEC host, identified requests, one request/second, bounded small-response cache."""
    global _last_request
    if path!='company_tickers.json' and not re.fullmatch(r'(submissions|api/xbrl/companyfacts)/CIK\d{10}\.json',path):
        raise SECDataError('Unsupported SEC endpoint')
    agent=os.getenv('SEC_USER_AGENT','').strip()
    if not agent or '@' not in agent or '\n' in agent or '\r' in agent:
        raise SECDataError('Configure SEC_USER_AGENT with app name and contact email')
    with _guard:
        now=time.monotonic()
        # Companyfacts expands substantially when decoded; do not retain it.
        for key,(saved_at,_) in list(_cache.items()):
            if not 0<=now-saved_at<3600 or key.startswith('api/xbrl/companyfacts/'):
                del _cache[key]
        cached=_cache.get(path)
        if cached and 0<=now-cached[0]<3600:return cached[1]
        time.sleep(max(0,1-(now-_last_request)))
        _last_request=time.monotonic()
        try:
            endpoint='https://www.sec.gov/files/company_tickers.json' if path=='company_tickers.json' else 'https://data.sec.gov/'+path
            request=Request(endpoint,
                            headers={'User-Agent':agent,'Accept':'application/json'})
            with urlopen(request,timeout=30) as response:
                raw=response.read(25000001)
            if len(raw)>25000000:raise SECDataError('SEC response exceeds size limit')
            result=json.loads(raw)
        except HTTPError as error:
            raise SECDataError('SEC request failed (HTTP '+str(error.code)+'); no stale-cache substitution') from None
        except (URLError,TimeoutError,OSError,ValueError):
            raise SECDataError('SEC request failed or returned invalid JSON') from None
        if not path.startswith('api/xbrl/companyfacts/') and len(raw)<=CACHE_MAX_RESPONSE_BYTES:
            while len(_cache)>=CACHE_MAX_ENTRIES:
                del _cache[min(_cache,key=lambda key:_cache[key][0])]
            _cache[path]=(time.monotonic(),result)
        return result


def annual_payload(symbol,submissions,companyfacts,today):
    """Select one 10-K accession, exact USD facts and comparable full-year revenue."""
    audit={'source':'SEC EDGAR companyfacts','symbol':symbol,'fields':{}}
    def fail(message):raise SECDataError(message,audit)
    if symbol not in CIKS:fail('Symbol not enabled for SEC fallback')
    try:
        cik=int(CIKS[symbol])
        if int(submissions['cik'])!=cik or int(companyfacts['cik'])!=cik:
            fail('SEC entity identifier mismatch')
        if symbol not in submissions['tickers']:fail('SEC ticker/entity mismatch')
        recent=submissions['filings']['recent']
        names=('form','reportDate','filingDate','accessionNumber','primaryDocument')
        if any(not isinstance(recent[k],list) for k in names):fail('Unsupported SEC submission arrays')
        if len({len(recent[k]) for k in names})!=1:fail('SEC submission arrays have different lengths')
        records=[dict(zip(names,row)) for row in zip(*(recent[k] for k in names))]
        known=[r for r in records if r['form'] in ('10-K','10-K/A')
               and date.fromisoformat(r['filingDate'])<=today]
        annuals=[r for r in known if r['form']=='10-K']
        if not annuals:fail('No 10-K in recent SEC submissions; older files not substituted')
        filing=max(annuals,key=lambda r:(r['reportDate'],r['filingDate']))
        end=date.fromisoformat(filing['reportDate'])
        age=(today-end).days
        audit.update(period=str(end),filed_at=filing['filingDate'],age_days=age,
                     max_age_days=550,access_number=filing['accessionNumber'])
        if not 0<=age<=550:fail('Latest SEC annual period outside 0–550 days')
        if any(r['form']=='10-K/A' and r['reportDate']==filing['reportDate']
               and r['filingDate']>=filing['filingDate'] for r in known):
            fail('Latest annual filing has an amendment; context review required')
        accession=filing['accessionNumber']
        if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession):fail('Invalid SEC accession')
        doc=filing['primaryDocument']
        if not re.fullmatch(r'[A-Za-z0-9_.-]+',doc):fail('Invalid SEC document name')
        audit['filing_url']='https://www.sec.gov/Archives/edgar/data/'+str(cik)+'/'+accession.replace('-','')+'/'+doc
        facts=companyfacts['facts']['us-gaap']
    except (KeyError,TypeError,ValueError) as error:
        if isinstance(error,SECDataError):raise
        fail('Missing or invalid SEC entity, submission or taxonomy fields')

    def rows(tag,duration):
        values=facts.get(tag,{}).get('units',{}).get('USD',[])
        if not isinstance(values,list):fail('Unsupported USD facts for '+tag)
        selected=[]
        for row in values:
            if row.get('accn')!=accession or row.get('form')!='10-K':continue
            try:
                if date.fromisoformat(row['filed'])>today:continue
                rowend=date.fromisoformat(row['end'])
                if duration:
                    start=date.fromisoformat(row['start'])
                    if not 330<=(rowend-start).days<=400:continue
                elif row.get('start'):continue
            except (KeyError,TypeError,ValueError):fail('Invalid period metadata for '+tag)
            selected.append(row)
        return selected

    def exact(matches,tag,label):
        if not matches:fail('Missing exact SEC annual fact: '+label)
        try:
            values=[float(row['val']) for row in matches]
            if any(isinstance(row['val'],bool) for row in matches):fail('Boolean fact: '+label)
        except (KeyError,TypeError,ValueError) as error:
            if isinstance(error,SECDataError):raise
            fail('Invalid numeric SEC fact: '+label)
        if not all(math.isfinite(v) for v in values):fail('Non-finite SEC fact: '+label)
        if len(set(values))!=1:fail('Conflicting SEC values: '+label)
        contexts={(r.get('start'),r['end']) for r in matches}
        if len(contexts)!=1:fail('Ambiguous annual duration: '+label)
        audit['fields'][label]={'concept':tag,'value':values[0],'unit':'USD',
                                'start':matches[0].get('start'),'end':matches[0]['end'],
                                'accession':accession}
        return values[0]

    def choose(tags,label,duration=True,required=True):
        for tag in tags:
            matches=[r for r in rows(tag,duration) if r['end']==str(end)]
            if matches:return tag,exact(matches,tag,label)
        audit.setdefault('missing_fields',[]).append(label)
        if required:fail('No supported SEC fact for '+label)
        return None,None

    revtag,revenue=choose(REVENUE,'revenue')
    annualstart=audit['fields']['revenue']['start']
    previous=[r for r in rows(revtag,True) if 300<=(end-date.fromisoformat(r['end'])).days<=430]
    if not previous:fail('No comparable prior annual revenue in the same 10-K')
    prior_end=max(r['end'] for r in previous)
    previous=[r for r in previous if r['end']==prior_end]
    prior=exact(previous,revtag,'prior_revenue')
    def duration_fact(tags,label):
        for tag in tags:
            matches=[r for r in rows(tag,True) if r['end']==str(end) and r['start']==annualstart]
            if matches:return tag,exact(matches,tag,label)
        fail('Missing cash-flow fact matching revenue duration: '+label)
    ocftag,ocf=duration_fact(('NetCashProvidedByUsedInOperatingActivities',),'operating_cash_flow')
    captag,capex=duration_fact(('PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets'),'capital_expenditure')
    bs=[]
    for tags,label,required in [
        (('StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest',),'total_equity',False),
        (('StockholdersEquity',),'parent_equity',False),
        (('MinorityInterest',),'noncontrolling_interest',False),
        (('Liabilities',),'total_liabilities',False),
        (('Assets',),'total_assets',False),
        (('AssetsCurrent',),'current_assets',True),
        (('LiabilitiesCurrent',),'current_liabilities',True)]:
        tag,value=choose(tags,label,False,required)
        if tag:bs.append({'concept':tag,'value':value})
    current={'endDate':str(end),'filedDate':filing['filingDate'],'accessNumber':accession,
             'report':{'ic':[{'concept':revtag,'value':revenue}],
                       'cf':[{'concept':ocftag,'value':ocf},{'concept':captag,'value':capex}],'bs':bs}}
    old={'endDate':prior_end,'filedDate':filing['filingDate'],'accessNumber':accession,
         'report':{'ic':[{'concept':revtag,'value':prior}]}}
    audit['retrieved_at']=datetime.now(timezone.utc).isoformat()
    return {'data':[current,old]},audit


def load_annual_payload(symbol,today):
    if symbol not in CIKS:raise SECDataError('Symbol not enabled for SEC fallback')
    cik=CIKS[symbol]
    submissions=fetch_json('submissions/CIK'+cik+'.json')
    facts=fetch_json('api/xbrl/companyfacts/CIK'+cik+'.json')
    return annual_payload(symbol,submissions,facts,today)
