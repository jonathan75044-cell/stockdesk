import os,time,requests
from datetime import date,timedelta

def many(x): return [] if x is None else x if isinstance(x,list) else [x]
class Data:
    def __init__(self):
        self.token=os.getenv('TRADIER_TOKEN','');self.finn=os.getenv('FINNHUB_TOKEN','')
    def tradier(self,path,**params):
        time.sleep(.55)
        r=requests.get('https://api.tradier.com/v1/'+path,params=params,headers={'Authorization':'Bearer '+self.token,'Accept':'application/json'},timeout=25)
        r.raise_for_status();return r.json()
    def fh(self,path,**params):
        time.sleep(1.1)
        r=requests.get('https://finnhub.io/api/v1/'+path,params={**params,'token':self.finn},timeout=25)
        r.raise_for_status();return r.json()
    def clock(self): return self.tradier('markets/clock')['clock']
    def quotes(self,symbols): return many(self.tradier('markets/quotes',symbols=','.join(symbols)).get('quotes',{}).get('quote'))
    def days(self,symbol,today):
        raw=self.tradier('markets/history',symbol=symbol,start=str(today-timedelta(days=550)),end=str(today-timedelta(days=1)),interval='daily')
        return many((raw.get('history') or {}).get('day'))
    def options(self,symbol,today,cfg):
        raw=self.tradier('markets/options/expirations',symbol=symbol)
        exps=many((raw.get('expirations') or {}).get('date'))
        for exp in exps:
            if cfg['put_dte_min']<=(date.fromisoformat(exp)-today).days<=cfg['put_dte_max']:
                raw=self.tradier('markets/options/chains',symbol=symbol,expiration=exp,greeks='true')
                yield from many((raw.get('options') or {}).get('option'))
    def research(self,symbol,today,horizon):
        earnings=self.fh('calendar/earnings',symbol=symbol,**{'from':str(today),'to':str(today+timedelta(days=horizon))})
        if 'earningsCalendar' not in earnings: raise ValueError('Earnings coverage unavailable')
        metrics=self.fh('stock/metric',symbol=symbol,metric='all').get('metric',{})
        news=self.fh('company-news',symbol=symbol,**{'from':str(today-timedelta(days=7)),'to':str(today)})
        if not metrics or not isinstance(news,list): raise ValueError('Research data unavailable')
        quality=self.quality(symbol)
        return dict(quality=quality,earnings=earnings['earningsCalendar'],metrics=metrics,news=[{'headline':n.get('headline'),'url':n.get('url'),'datetime':n.get('datetime'),'source':n.get('source')} for n in news[:4]])
    def jd_hold(self,today):
        # 15-minute regular-session bars combined into complete 9:30-anchored hours.
        from datetime import datetime
        from zoneinfo import ZoneInfo
        now=datetime.now(ZoneInfo('America/New_York'))
        raw=self.tradier('markets/timesales',symbol='JD',interval='15min',start=str(today-timedelta(days=30))+' 09:30',end=now.strftime('%Y-%m-%d %H:%M'),session_filter='open')
        groups={}
        for b in many((raw.get('series') or {}).get('data')):
            t=datetime.fromisoformat(b['time']).replace(tzinfo=ZoneInfo('America/New_York'))
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

    def quality(self,symbol):
        # Annual filings avoid summing overlapping year-to-date cash-flow periods.
        filings=self.fh('stock/financials-reported',symbol=symbol,freq='annual').get('data',[])
        filings=sorted(filings,key=lambda x:x.get('endDate',''),reverse=True)
        unique=[]
        for f in filings:
            if f.get('endDate') not in [x.get('endDate') for x in unique]:unique.append(f)
        if len(unique)<2:return {}
        current=unique[0]
        def value(f,section,tags):
            rows=f.get('report',{}).get(section,[])
            if not isinstance(rows,list):raise ValueError('Unsupported financial report shape')
            for tag in tags:
                for r in rows:
                    if r.get('concept','').split('_',1)[-1].split(':')[-1]==tag:
                        return float(r['value'])
            raise ValueError('Required financial field unavailable')
        try:
            previous=next(f for f in unique[1:] if 300<=(date.fromisoformat(current['endDate'][:10])-date.fromisoformat(f['endDate'][:10])).days<=430)
            rev=['RevenueFromContractWithCustomerExcludingAssessedTax','Revenues','SalesRevenueNet','RevenueFromContractWithCustomerIncludingAssessedTax']
            revenue=value(current,'ic',rev);prior=value(previous,'ic',rev)
            ocf=value(current,'cf',['NetCashProvidedByUsedInOperatingActivities'])
            capex=value(current,'cf',['PaymentsToAcquirePropertyPlantAndEquipment'])
            assets=value(current,'bs',['AssetsCurrent']);liabilities=value(current,'bs',['LiabilitiesCurrent'])
            equity=value(current,'bs',['StockholdersEquity','StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'])
            # Total liabilities / equity is a stricter, explicit proxy for debt / equity.
            debt=value(current,'bs',['Liabilities'])
            if min(prior,liabilities,equity)<=0 or capex<0:return {}
            return dict(period=current['endDate'][:10],filed_at=current.get('filedDate'),revenue_growth_pct=100*(revenue/prior-1),fcf=ocf-capex,current_ratio=assets/liabilities,debt_equity=debt/equity,balance_measure='Total liabilities / equity (conservative debt proxy)',source='Finnhub annual financials as reported',access_number=current.get('accessNumber'))
        except (ValueError,TypeError,KeyError,StopIteration):return {}
