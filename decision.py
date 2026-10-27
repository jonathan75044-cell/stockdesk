"""Independent research review with explicit pass/fail/unknown evidence."""
import math
import time
from datetime import datetime,timezone,timedelta
from engine import indicators,demand_zone,swing,put_candidate,fundamental_gate
from pullback import pullback_zone
from valuation import estimate
from sec_fundamentals import SECDataError


def number(value):
    if isinstance(value,bool):return None
    try:value=float(value)
    except (TypeError,ValueError):return None
    return value if math.isfinite(value) else None


def check(name,value,passed,requirement):
    return {'name':name,'value':value,'requirement':requirement,
            'status':'unknown' if passed is None else 'pass' if passed else 'fail'}


def put_payoff(strike,premium,stock_at_expiry,contracts=1,fees=0):
    vals=[number(v) for v in (strike,premium,stock_at_expiry,contracts,fees)]
    if any(v is None for v in vals) or strike<=0 or premium<0 or stock_at_expiry<0 or fees<0 or contracts<1 or int(contracts)!=contracts:
        raise ValueError('Invalid put scenario inputs')
    return contracts*100*(premium-max(strike-stock_at_expiry,0))-fees


def option_review(price,opt,cfg,today,zone,base_passed,earnings):
    reasons=[]
    candidate=put_candidate(price,opt,cfg,today,zone,reasons)
    strike=number(opt.get('strike'));bid=number(opt.get('bid'));ask=number(opt.get('ask'))
    delta=number((opt.get('greeks') or {}).get('delta'));oi=number(opt.get('open_interest'))
    try:dte=(datetime.fromisoformat(opt['expiration_date']).date()-today).days
    except (ValueError,TypeError,KeyError):dte=None
    quote_times=[number(opt.get(k)) for k in ('bid_date','ask_date')]
    fresh=all(t is not None and t>0 and abs(time.time()-t/1000)<=900 for t in quote_times)
    valid_prices=all(v is not None for v in (strike,bid,ask)) and 0<bid<=ask and 0<bid<strike
    spread=ask-bid if valid_prices else None
    relative=spread/((ask+bid)/2) if valid_prices else None
    otm=(price-strike)/price if strike is not None and price>0 else None
    collateral=strike*100 if strike is not None else None
    expiry=today+timedelta(days=dte) if dte is not None else None
    event_pass=None if earnings is None or expiry is None else not any(today<=d<=expiry+timedelta(days=cfg['earnings_buffer_days']) for d in earnings)
    checks=[
        check('Standard put',opt.get('contract_size'),opt.get('option_type')=='put' and opt.get('contract_size')==100,'Put, 100-share standard contract'),
        check('Quote freshness',str(round(max(abs(time.time()-t/1000) for t in quote_times)))+' seconds old' if all(t is not None for t in quote_times) else None,fresh,'Bid and ask timestamps within 15 minutes'),
        check('DTE',dte,None if dte is None else cfg['put_dte_min']<=dte<=cfg['put_dte_max'],str(cfg['put_dte_min'])+'–'+str(cfg['put_dte_max'])+' days'),
        check('Absolute delta',abs(delta) if delta is not None else None,None if delta is None else cfg['put_delta_min']<=abs(delta)<=cfg['put_delta_max'],str(cfg['put_delta_min'])+'–'+str(cfg['put_delta_max'])),
        check('Bid/ask validity',{'bid':bid,'ask':ask},valid_prices,'0 < bid ≤ ask'),
        check('Cash collateral',collateral,None if collateral is None else collateral<=cfg['cash_per_position'],'≤ $'+str(cfg['cash_per_position'])+' per position'),
        check('Open interest',oi,None if oi is None else oi>=max(500,cfg['put_min_oi']),'≥ '+str(max(500,cfg['put_min_oi']))),
        check('Daily option volume',number(opt.get('volume')),None if number(opt.get('volume')) is None else number(opt.get('volume'))>=max(100,cfg.get('put_min_volume',100)),'≥ '+str(max(100,cfg.get('put_min_volume',100)))+' contracts'),
        check('OTM distance %',100*otm if otm is not None else None,None if otm is None else cfg['put_otm_min']-1e-9<=otm<=cfg['put_otm_max']+1e-9,'Configured OTM range'),
        check('Demand-zone strike',strike,None if not zone or strike is None else strike<=zone['high'],'Strike at or below confirmed zone high'),
        check('Dollar spread',spread,None if spread is None else spread<=cfg['put_max_spread_dollars']+1e-9,'≤ $'+str(cfg['put_max_spread_dollars'])),
        check('Spread %',100*relative if relative is not None else None,None if relative is None else relative<=cfg['put_max_spread_fraction'],'≤ '+str(100*cfg['put_max_spread_fraction'])+'% of midpoint'),
        check('Premium yield %',100*bid/strike if valid_prices else None,None if not valid_prices else bid/strike>=cfg['put_min_yield'],'≥ '+str(100*cfg['put_min_yield'])+'%'),
        check('Earnings exclusion',None if earnings is None else 'No event returned' if not earnings else ', '.join(str(d) for d in earnings),event_pass,'No returned earnings event through expiry + buffer')]
    economics={}
    if valid_prices:
        economics={'collateral':collateral,'premium_total':bid*100,'breakeven':strike-bid,
                   'max_profit_before_fees':bid*100,'max_loss_before_fees':(strike-bid)*100,
                   'period_yield_pct':100*bid/strike,'breakeven_distance_pct':100*(price-(strike-bid))/price,
                   'simple_annualized_yield_pct':100*bid/strike*365/dte if dte and dte>0 else None,
                   'expiry_scenarios':[{'stock_change_pct':change,'stock_at_expiry':price*(1+change/100),
                                        'profit_before_fees':put_payoff(strike,bid,price*(1+change/100))}
                                       for change in (0,-5,-10,-20,-50,-100)]}
    eligible=bool(candidate and base_passed and event_pass and all(c['status']=='pass' for c in checks))
    return {'contract':opt.get('symbol'),'expiry':opt.get('expiration_date'),'dte':dte,'strike':strike,'bid':bid,'ask':ask,
            'quote_timestamp':min(quote_times)/1000 if all(t is not None for t in quote_times) else None,
            'preferred_liquidity':oi is not None and oi>=cfg.get('put_preferred_oi',1000),'delta':delta,'oi':oi,'volume':number(opt.get('volume')),'iv_pct':number(opt.get('iv_pct')),
            'greeks':{k:number((opt.get('greeks') or {}).get(k)) for k in ('gamma','theta','vega','rho')},
            'checks':checks,'trade_eligible':eligible,'engine_rejections':reasons,'economics':economics,
            'note':'Expiry scenarios assume one 100-share contract sold at the quoted bid, before fees. Bid is not an execution guarantee. Annualized yield is an arithmetic comparison, not a forecast. Delta is not a guaranteed assignment probability.'}


def review_symbol(data,symbol,cfg,today,model=None):
    report={'symbol':symbol,'started_at':datetime.now(timezone.utc).isoformat(),'status':'Reviewing','errors':{},'checks':[],'options':[]}
    def call(stage,fn):
        try:return fn()
        except Exception as error:
            report['errors'][stage]=type(error).__name__+' · evidence unavailable'
            if isinstance(error,SECDataError):report['errors'][stage]=str(error)
            if hasattr(error,'details'):report.setdefault('evidence_errors',{})[stage]=error.details
            return None
    clock=call('Exchange clock',lambda:data.clock())
    report['clock']=clock
    report['checks'].append(check('Regular market session',(clock or {}).get('state'),None if not clock else clock.get('state')=='open','Exchange reports regular trading session open'))
    quotes=call('Quote',lambda:data.quotes([symbol]))
    quote=quotes[0] if quotes else {}
    price=number(quote.get('last'));ts=number(quote.get('trade_date'))
    report['quote']=quote
    quote_pass=price is not None and price>0 and ts is not None and abs(time.time()-ts/1000)<=900
    try:observed_quote=datetime.fromtimestamp(ts/1000,timezone.utc).isoformat() if ts is not None and ts>0 else None
    except (ValueError,OSError,OverflowError):observed_quote=None
    report['checks'].append(check('Underlying quote freshness',observed_quote,quote_pass,'Positive price and trade within 15 minutes'))
    if price is None or price<=0:report['status']='Unavailable';return report
    days=call('Daily history',lambda:data.days(symbol,today))
    m=call('Indicators',lambda:indicators(days)) if days else None
    zone=None;sw=None
    history_pass=False
    if m:
        try:history_pass=0<(today-datetime.fromisoformat(days[-1]['date']).date()).days<=5
        except (KeyError,ValueError,TypeError):pass
        report['market_metrics']=m
        report['pullback']=call('Swing anchors',lambda:pullback_zone(price,days,m['atr']))
        report['daily_closes']=[{'date':b['date'],'close':number(b['close'])} for b in days[-120:]]
        report['high_52w']=max(float(b['high']) for b in days[-252:]) if len(days)>=252 else None
        report['low_52w']=min(float(b['low']) for b in days[-252:]) if len(days)>=252 else None
        changes=[float(b['close'])-float(a['close']) for a,b in zip(days[-15:-1],days[-14:])]
        gains=sum(max(v,0) for v in changes);losses=sum(max(-v,0) for v in changes)
        report['rsi14_simple']=100-100/(1+gains/losses) if losses else 100 if gains else 50
        demand_reasons=[];audit={}
        zone=call('Demand',lambda:demand_zone(price,days,cfg,demand_reasons,audit))
        report.update(demand_zone=zone,demand_rejections=demand_reasons,demand_diagnostics=audit)
        swing_reasons=[];sw=call('Swing',lambda:swing(price,days,cfg,swing_reasons))
        report.update(swing=sw,swing_rejections=swing_reasons)
    report['checks'] += [check('Completed daily history',days[-1].get('date') if days else None,history_pass,'≥65 bars; last completed session within five days'),
                        check('Minimum stock price',price,price>=cfg['min_price'],'≥ $'+str(cfg['min_price'])),
                        check('Average volume',m.get('avgvol') if m else None,None if not m else m['avgvol']>=cfg['min_avg_volume'],'≥ '+str(cfg['min_avg_volume'])),
                        check('Demand confirmation',('$'+str(round(zone['low'],2))+'–$'+str(round(zone['high'],2))) if zone else None,None if not m else bool(zone),'Confirmed pivot, recent bullish retest, intact zone and ATR distance')]
    quality=call('Annual fundamentals',lambda:data.quality(symbol,today))
    reasons=[];financial_pass=fundamental_gate({'quality':quality},cfg,today,reasons) if quality else None
    report.update(quality=quality,fundamental_rejections=reasons)
    report['checks'].append(check('Annual fundamental gate',(quality.get('period')+' · '+quality.get('source','Annual reported evidence')) if quality else None,None if not quality else bool(financial_pass),'Positive growth/FCF, current ratio and total liabilities/equity limits'))
    for label,key,predicate,requirement in [
        ('Revenue growth','revenue_growth_pct',lambda v:v>0,'Annual growth > 0%'),
        ('Free cash flow','fcf',lambda v:v>0,'Annual operating cash flow − capex > 0'),
        ('Current ratio','current_ratio',lambda v:v>=cfg['min_current_ratio'],'≥ '+str(cfg['min_current_ratio'])),
        ('Total liabilities / equity','debt_equity',lambda v:0<=v<=cfg['max_debt_equity'],'0–'+str(cfg['max_debt_equity']))]:
        value=number((quality or {}).get(key))
        report['checks'].append(check(label,value,None if value is None else predicate(value),requirement))
    earnings_raw=call('Earnings calendar',lambda:data.fh('calendar/earnings',symbol=symbol,**{'from':str(today),'to':str(today+timedelta(days=cfg['put_dte_max']+cfg['earnings_buffer_days']))}))
    earnings=None
    if isinstance(earnings_raw,dict) and isinstance(earnings_raw.get('earningsCalendar'),list):
        try:earnings=[datetime.fromisoformat(e['date']).date() for e in earnings_raw['earningsCalendar']]
        except (KeyError,TypeError,ValueError):earnings=None
    report['earnings']=[str(d) for d in earnings] if earnings is not None else None
    report['earnings_note']='No event returned is not a guarantee that the calendar is complete.'
    metrics_raw=call('Financial metrics',lambda:data.fh('stock/metric',symbol=symbol,metric='all'))
    metrics=metrics_raw.get('metric',{}) if isinstance(metrics_raw,dict) else {}
    report['financial_metrics']={k:number(metrics.get(k)) for k in ('peTTM','pb','roeTTM','netProfitMarginTTM','epsTTM','dividendYieldIndicatedAnnual','52WeekHigh','52WeekLow')}
    report['display_metadata']=call('Sector/P/E',lambda:data.display_metadata(symbol,metrics))
    news=call('News',lambda:data.fh('company-news',symbol=symbol,**{'from':str(today-timedelta(days=7)),'to':str(today)}))
    report['news']=[{k:n.get(k) for k in ('headline','url','source','datetime')} for n in news[:6] if isinstance(n,dict)] if isinstance(news,list) else []
    report['valuation']=estimate(price,model,today)
    if model is None:
        raw=getattr(data,'_annual_reports',{}).get(symbol,{})
        def automatic():
            from auto_fcfe import load_cashflow_inputs
            inputs=load_cashflow_inputs(symbol,raw.get('cik'),today)
            model={'symbol':symbol,**{k:inputs[k] for k in ('annual_fcfe_per_share','evidence_date','notes')},
                   'growth_pct':5,'discount_pct':10,'terminal_growth_pct':2,'years':5}
            result=estimate(price,model,today)
            result.update(input_source='Automatic SEC evidence',input_audit=inputs['audit'],
                          method=inputs['method']+' DCF estimate',
                          note=inputs['notes']+' 5% growth, 10% discount and 2% terminal growth are editable scenario assumptions, not forecasts.')
            return result
        automatic_result=call('Automatic valuation inputs',automatic)
        if automatic_result:report['valuation']=automatic_result
        else:
            report['valuation']['reason']=report['errors'].get('Automatic valuation inputs','Automatic evidence unavailable')
            report['valuation']['input_audit']=report.get('evidence_errors',{}).get('Automatic valuation inputs',{})
    if report['valuation'].get('status')=='estimated':
        assumptions=report['valuation']['assumptions']
        report['valuation']['sensitivity']=[]
        for label,growth_change,discount_change in [('Lower growth / higher discount',-2,2),('Base scenario',0,0),('Higher growth / lower discount',2,-2)]:
            scenario={**assumptions,'growth_pct':assumptions['growth_pct']+growth_change,
                      'discount_pct':assumptions['discount_pct']+discount_change}
            value=estimate(price,scenario,today)
            report['valuation']['sensitivity'].append({'scenario':label,'growth_pct':scenario['growth_pct'],
                'discount_pct':scenario['discount_pct'],'intrinsic_value':value.get('intrinsic_value'),
                'status':value['status'],'reason':value.get('reason')})
    base=all(c['status']=='pass' for c in report['checks'])
    trend=bool(m and price>m['ma20']>m['ma50'])
    report['checks'].append(check('Put trend',('Price $'+str(round(price,2))+' · MA20 $'+str(round(m['ma20'],2))+' · MA50 $'+str(round(m['ma50'],2))) if m else None,None if not m else trend,'Price > MA20 > MA50'))
    base=base and trend
    def chain():
        results=[]
        for index,opt in enumerate(data.options(symbol,today,cfg)):
            if index>=2500:report['chain_truncated']=True;break
            results.append(option_review(price,opt,cfg,today,zone,base,earnings))
        return results
    options=call('Option chain',chain) or []
    report['contracts_checked']=len(options)
    report['eligible_contract_count']=sum(o['trade_eligible'] for o in options)
    options.sort(key=lambda o:(not o['trade_eligible'],not (o['trade_eligible'] and o.get('preferred_liquidity',False)),-sum(c['status']=='pass' for c in o['checks']),
                               (o['ask']-o['bid']) if o['ask'] is not None and o['bid'] is not None else math.inf))
    report['options']=options[:60]
    swing_earnings=earnings is not None and not any(today<=d<=today+timedelta(days=14+cfg['earnings_buffer_days']) for d in earnings)
    # Demand confirmation and put trend are put-strategy checks, not swing prerequisites.
    report['swing_eligible']=swing_checks_pass(sw,report['checks'],swing_earnings)
    report['swing_stage']='Meets trade checks' if report['swing_eligible'] else 'Awaiting confirmation' if (report.get('pullback') or {}).get('in_zone') else 'Outside zone / unverified'
    report['swing_blockers']=[c['name']+': '+c['status'] for c in report['checks'] if c['name'] not in ('Demand confirmation','Put trend') and c['status']!='pass']+report.get('swing_rejections',[])+([] if swing_earnings else ['Earnings calendar missing or event inside swing window'])
    report['status']='Completed'
    report['completed_at']=datetime.now(timezone.utc).isoformat()
    report['suggestions']=['Resolve every fail or unknown before treating a setup as eligible.',
                           'Verify current broker bid/ask and cash available after existing commitments.',
                           'For a cash-secured put, confirm you want to own 100 shares at the strike.',
                           'Review sector concentration and downside scenarios before comparing premium.',
                           'Review DCF sensitivity; a high terminal-value share makes the estimate assumption-sensitive.']
    return report

def swing_checks_pass(setup,checks,earnings_pass):
    return bool(setup and earnings_pass and checks and all(c['status']=='pass' for c in checks if c['name'] not in ('Demand confirmation','Put trend')))
