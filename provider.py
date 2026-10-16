import os,time,requests,math
from datetime import date,timedelta,datetime,timezone

def many(x): return [] if x is None else x if isinstance(x,list) else [x]
class Data:
    def __init__(self):
        from schwab import Schwab
        self.schwab=Schwab();self.finn=os.getenv('FINNHUB_TOKEN','')
    @property
    def token(self):return self.schwab.connected()
    def fh(self,path,**params):
        time.sleep(1.1)
        r=requests.get('https://finnhub.io/api/v1/'+path,params={**params,'token':self.finn},timeout=25)
        if r.status_code>=400:
            raise ValueError('Finnhub '+path+' request failed (status '+str(r.status_code)+'); check access, key or rate limits')
        payload=r.json()
        if isinstance(payload,dict) and payload.get('error'):
            raise ValueError('Finnhub '+path+' returned an error; check access, key or rate limits')
        return payload
    def clock(self):return self.schwab.clock()
    def quotes(self,symbols):return self.schwab.quotes(symbols)
    def days(self,symbol,today):return self.schwab.days(symbol,today)
    def options(self,symbol,today,cfg):return self.schwab.options(symbol,today,cfg)
    def research(self,symbol,today,horizon):
        earnings=self.fh('calendar/earnings',symbol=symbol,**{'from':str(today),'to':str(today+timedelta(days=horizon))})
        if 'earningsCalendar' not in earnings: raise ValueError('Earnings coverage unavailable')
        metrics=self.fh('stock/metric',symbol=symbol,metric='all').get('metric',{})
        news=self.fh('company-news',symbol=symbol,**{'from':str(today-timedelta(days=7)),'to':str(today)})
        if not metrics or not isinstance(news,list): raise ValueError('Research data unavailable')
        quality=self.quality(symbol,today)
        return dict(quality=quality,earnings=earnings['earningsCalendar'],metrics=metrics,news=[{'headline':n.get('headline'),'url':n.get('url'),'datetime':n.get('datetime'),'source':n.get('source')} for n in news[:4]])
    def jd_hold(self,today):
        # 15-minute regular-session bars combined into complete 9:30-anchored hours.
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now=datetime.now(ZoneInfo('America/New_York'))
        raw=self.schwab.intraday(today)
        groups={}
        for b in sorted(raw,key=lambda x:x['datetime']):
            t=datetime.fromtimestamp(b['datetime']/1000,ZoneInfo('America/New_York'))
            minutes=t.hour*60+t.minute-570
            if not 0<=minutes<360 or (now-t).total_seconds()<900: continue
            groups.setdefault((t.date(),minutes//60),[]).append(b)
        bars=[]
        for k,v in sorted(groups.items()):
            if len(v)==4: bars.append((k,{'close':float(v[-1]['close']),'low':min(float(x['low']) for x in v),'volume':sum(float(x['volume']) for x in v)}))
        if len(bars)<5 or bars[-1][0][0]!=today: return False
        recent=[b for _,b in bars[-5:]]
        baseline=[b['volume'] for k,b in bars[:-1] if k[1]==bars[-1][0][1]]
        return len(baseline)>=10 and all(b['close']>27.15 for b in recent[:3]) and recent[2]['close']<=27.60 and recent[3]['close']>27.60 and recent[4]['low']>27.60 and recent[4]['volume']>sum(baseline)/len(baseline)*1.3

    def quality(self,symbol,today=None):
        today=today or date.today()
        try:
            payload=self.fh('stock/financials-reported',symbol=symbol,freq='annual')
            if not hasattr(self,'_annual_reports'):self._annual_reports={}
            self._annual_reports[symbol]={'cik':payload.get('cik')} if isinstance(payload,dict) else {}
            return parse_annual_quality(payload,today)
        except (ValueError,requests.RequestException) as original:
            if symbol!='DE':raise
            from sec_fundamentals import load_annual_payload,SECDataError
            original_audit=getattr(original,'details',{})
            audit={}
            try:
                payload,audit=load_annual_payload(symbol,today)
                quality=parse_annual_quality(payload,today)
            except (SECDataError,FundamentalDataError) as fallback:
                details={'finnhub':original_audit,'sec':{**audit,**fallback.details}}
                raise FundamentalDataError(str(fallback),details) from None
            quality.update(source='SEC EDGAR annual 10-K companyfacts',
                           filing_url=audit['filing_url'],sec_audit=audit,
                           fallback_reason='Finnhub annual evidence unavailable or invalid',
                           finnhub_audit=original_audit)
            return quality

    def display_metadata(self,symbol,metrics=None):
        """Optional display context. Its availability never changes eligibility."""
        result={'sector':None,'pe_ttm':None,'source':'Finnhub gsector / peTTM',
                'retrieved_at':datetime.now(timezone.utc).isoformat(),'notes':[]}
        try:
            profile=self.fh('stock/profile',symbol=symbol)
            if isinstance(profile,dict):
                result['company_description']=profile.get('description')[:2000] if isinstance(profile.get('description'),str) else None
                result['industry']=profile.get('gind') or profile.get('finnhubIndustry')
            sector=profile.get('gsector') if isinstance(profile,dict) else None
            if isinstance(sector,str) and sector.strip() and not sector.strip().isdigit():
                result['sector']=sector.strip()[:100]
            else:result['notes'].append('Sector classification unavailable; industry is not substituted')
        except (ValueError,requests.RequestException):
            result['notes'].append('Sector profile unavailable; endpoint may require additional account access')
        try:
            if metrics is None:metrics=self.fh('stock/metric',symbol=symbol,metric='all').get('metric',{})
            result['pe_ttm']=positive_pe(metrics.get('peTTM'))
            if result['pe_ttm'] is None:result['notes'].append('P/E TTM missing, non-finite or non-positive')
        except (ValueError,TypeError,AttributeError,requests.RequestException):
            result['notes'].append('P/E metrics unavailable')
        return result


def positive_pe(value):
    if isinstance(value,bool):return None
    try:result=float(value)
    except (TypeError,ValueError):return None
    return result if math.isfinite(result) and result>0 else None


class FundamentalDataError(ValueError):
    """Only public accounting metadata; never request URLs or credentials."""
    def __init__(self, message, details):
        super().__init__('Fundamental data unavailable: '+message)
        self.details=details


def parse_annual_quality(payload,today=None):
    """Conservative annual US-GAAP parser; no fuzzy matching of custom concepts."""
    audit={'basis':'Annual filings, not quarterly or TTM','fields':{}}
    def fail(message):
        raise FundamentalDataError(message,audit)
    if not isinstance(payload,dict) or not isinstance(payload.get('data'),list):
        fail('Unsupported financials-reported response')
    filings=sorted(payload['data'],key=lambda f:(str(f.get('endDate','')),str(f.get('filedDate',''))),reverse=True)
    unique=[]
    for f in filings:
        if f.get('endDate') not in [x.get('endDate') for x in unique]:unique.append(f)
    if len(unique)<2:fail('Fewer than two annual reporting periods')
    current=unique[0]
    try:
        end=date.fromisoformat(current['endDate'][:10])
    except (KeyError,TypeError,ValueError):
        fail('Invalid latest annual reporting period')
    age=((today or date.today())-end).days
    audit.update(period=str(end),filed_at=current.get('filedDate'),age_days=age,max_age_days=550)
    if not 0<=age<=550:
        fail('Latest available annual period '+str(end)+' is outside 0–550 days; fresh fundamental evidence required')
    try:
        previous=next(f for f in unique[1:] if 300<=(end-date.fromisoformat(f['endDate'][:10])).days<=430)
    except (KeyError,TypeError,ValueError,StopIteration):
        fail('No comparable annual period 300–430 days earlier')
    audit['period']=str(end)
    def value(f,section,tags,label,required=True):
        rows=f.get('report',{}).get(section,[])
        if not isinstance(rows,list):fail('Unsupported '+section+' report shape')
        # Match only unqualified or US-GAAP concepts. Custom namespaces may
        # use a familiar name with a different definition.
        def concept(row):
            raw=str(row.get('concept',''))
            for prefix in ('us-gaap_','us-gaap:'):
                if raw.startswith(prefix):return raw[len(prefix):]
            return raw if ':' not in raw and '_' not in raw else ''
        for tag in tags:
            matches=[r for r in rows if isinstance(r,dict) and concept(r)==tag]
            if matches:
                try:values=[float(r['value']) for r in matches]
                except (KeyError,TypeError,ValueError):fail('Invalid numeric field: '+label)
                if not all(math.isfinite(v) for v in values):fail('Non-finite field: '+label)
                if len(set(values))!=1:fail('Conflicting values for '+label+'; context selection required')
                audit['fields'][label]={'concept':tag,'value':values[0],'period':f.get('endDate')}
                return values[0]
        if required:
            audit['missing_field']=label
            audit['available_concepts']=sorted({str(r.get('concept',''))[:180] for r in rows if isinstance(r,dict)})
            fail('Missing '+label+' in annual '+section+'; inspect available_concepts in diagnostics')
        return None
    rev=['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet','RevenueFromContractWithCustomerIncludingAssessedTax']
    revenue=value(current,'ic',rev,'revenue')
    prior=value(previous,'ic',rev,'prior_revenue')
    ocf=value(current,'cf',['NetCashProvidedByUsedInOperatingActivities'],'operating_cash_flow')
    capex=value(current,'cf',['PaymentsToAcquirePropertyPlantAndEquipment','PaymentsToAcquireProductiveAssets'],'capital_expenditure')
    if capex<0:fail('capital_expenditure is negative ('+str(capex)+'); sign convention requires review')
    equity=value(current,'bs',['StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'],'total_equity',False)
    total_equity_known=equity is not None
    if equity is None:
        parent=value(current,'bs',['StockholdersEquity'],'parent_equity')
        nci=value(current,'bs',['MinorityInterest'],'noncontrolling_interest',False)
        total_equity_known=nci is not None
        equity=parent+(nci if nci is not None else 0)
        audit['equity_basis']='Parent equity plus reported noncontrolling interest; absent NCI treated as zero'
    debt=value(current,'bs',['Liabilities'],'total_liabilities',False)
    if debt is None:
        if not total_equity_known:fail('Cannot derive liabilities: consolidated total equity or explicit noncontrolling interest is missing')
        assets_total=value(current,'bs',['Assets'],'total_assets')
        debt=assets_total-equity
        audit['fields']['total_liabilities']={'derivation':'Assets minus total equity','value':debt,'period':str(end)}
    assets=value(current,'bs',['AssetsCurrent'],'current_assets')
    liabilities=value(current,'bs',['LiabilitiesCurrent'],'current_liabilities')
    for name,v in [('prior_revenue',prior),('current_liabilities',liabilities),('total_equity',equity)]:
        if v<=0:fail(name+' is non-positive ('+str(v)+'); required ratio cannot pass')
    if debt<0 or assets<0:fail('Negative total liabilities or current assets; review filing')
    return dict(period=str(end),filed_at=current.get('filedDate'),revenue_growth_pct=100*(revenue/prior-1),fcf=ocf-capex,current_ratio=assets/liabilities,debt_equity=debt/equity,balance_measure='Total liabilities / total equity (conservative debt proxy)',source='Finnhub annual financials as reported',access_number=current.get('accessNumber'),accounting_audit=audit)
