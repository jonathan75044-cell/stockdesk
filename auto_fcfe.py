"""Automatic FCFE inputs from exact SEC annual facts; no missing-flow guesses."""
import math
import re
from datetime import date
from sec_fundamentals import fetch_json,SECDataError


def cashflow_inputs(symbol,cik,submissions,facts,today):
    audit={'source':'SEC EDGAR annual FCFE inputs','symbol':symbol,'facts':{}}
    def fail(message):raise SECDataError(message,audit)
    try:
        if int(submissions['cik'])!=int(cik) or int(facts['cik'])!=int(cik):fail('Entity identifier mismatch')
        sic=int(submissions['sic'])
        audit.update(sic=sic,sic_description=submissions.get('sicDescription'))
        if 6000<=sic<=6999:fail('Financial-sector issuer requires a sector-specific valuation model')
        if symbol.replace('.','-') not in submissions['tickers'] and symbol not in submissions['tickers']:
            fail('Ticker/entity mismatch')
        recent=submissions['filings']['recent']
        keys=('form','reportDate','filingDate','accessionNumber','primaryDocument')
        if len({len(recent[k]) for k in keys})!=1:fail('Submission arrays differ in length')
        records=[dict(zip(keys,v)) for v in zip(*(recent[k] for k in keys))]
        known=[r for r in records if date.fromisoformat(r['filingDate'])<=today]
        annual=[r for r in known if r['form']=='10-K']
        if not annual:fail('No recent 10-K')
        filing=max(annual,key=lambda r:(r['reportDate'],r['filingDate']))
        end=filing['reportDate'];age=(today-date.fromisoformat(end)).days
        if not 0<=age<=550:fail('Annual evidence outside 0–550 days')
        if any(r['form']=='10-K/A' and r['reportDate']==end and r['filingDate']>=filing['filingDate'] for r in known):
            fail('Annual amendment requires context review')
        accession=filing['accessionNumber']
        audit.update(period=end,accession=accession,filed_at=filing['filingDate'],sic=sic)
        gaap=facts['facts']['us-gaap']
    except (KeyError,TypeError,ValueError) as error:
        if isinstance(error,SECDataError):raise
        fail('Invalid SEC annual metadata')

    def select(namespace,tag,unit='USD',duration=True,start=None):
        concept=facts.get('facts',{}).get(namespace,{}).get(tag,{})
        matched=[]
        for row in concept.get('units',{}).get(unit,[]):
            if row.get('accn')!=accession or row.get('form')!='10-K':continue
            try:
                rowend=date.fromisoformat(row['end'])
                if date.fromisoformat(row['filed'])>today:continue
                if duration:
                    if row['end']!=end or not 330<=(rowend-date.fromisoformat(row['start'])).days<=400:continue
                    if start and row['start']!=start:continue
                else:
                    if row.get('start') or not date.fromisoformat(end)<=rowend<=date.fromisoformat(filing['filingDate']):continue
                value=float(row['val'])
                if isinstance(row['val'],bool) or not math.isfinite(value):fail('Invalid SEC '+tag)
            except (KeyError,TypeError,ValueError) as error:
                if isinstance(error,SECDataError):raise
                fail('Invalid SEC fact context: '+tag)
            matched.append((row,value))
        if not matched:return None
        if not duration:
            latest=max(row['end'] for row,_ in matched)
            matched=[pair for pair in matched if pair[0]['end']==latest]
        if len({(r.get('start'),r['end'],v) for r,v in matched})!=1:fail('Conflicting SEC '+tag)
        row,value=matched[0]
        audit['facts'][tag]={'value':value,'unit':unit,'start':row.get('start'),'end':row['end'],'accession':accession}
        return value

    ocf=select('us-gaap','NetCashProvidedByUsedInOperatingActivities')
    if ocf is None:fail('Missing annual operating cash flow')
    start=audit['facts']['NetCashProvidedByUsedInOperatingActivities']['start']
    # The productive-assets aggregate includes PP&E, software and intangibles.
    # Prefer the reported aggregate; never sum it with its narrower components.
    capex=select('us-gaap','PaymentsToAcquireProductiveAssets',start=start)
    capex_tag='PaymentsToAcquireProductiveAssets'
    if capex is None:
        capex_tag='PaymentsToAcquirePropertyPlantAndEquipment'
        capex=select('us-gaap',capex_tag,start=start)
    audit['capital_expenditure']={'selected_tag':capex_tag if capex is not None else None,
        'required_start':start,'required_end':end,'required_accession':accession}
    if capex is None:
        audit['capital_expenditure']['available_concepts']=[
            {'tag':tag,'description':concept.get('description'),
             'contexts':[{k:r.get(k) for k in ('start','end','accn','form','filed','val')}
                         for r in concept.get('units',{}).get('USD',[]) if r.get('accn')==accession]}
            for tag,concept in gaap.items() if any(word in tag.lower() for word in
                ('productiveassets','propertyplantandequipment','capitalexpend'))]
        fail('Missing matching annual capital expenditure; inspect capital_expenditure audit')
    if capex<0:fail('Capital expenditure sign requires review')
    # Only aggregate debt flows are accepted. Long-term-only flows can omit
    # commercial paper or other short-term financing and are not substituted.
    method='Reported FCFE'
    net=select('us-gaap','ProceedsFromRepaymentsOfDebt',start=start)
    if net is None:
        issuance=select('us-gaap','ProceedsFromIssuanceOfDebt',start=start)
        repayment=select('us-gaap','RepaymentsOfDebt',start=start)
        if issuance is not None and repayment is not None:
            if issuance<0 or repayment<0:fail('Debt cash-flow sign requires review')
            net=issuance-repayment
        else:
            # Component-based estimates are a proxy, not a claim of complete
            # generic FCFE. The entire financing statement must reconcile.
            def flow(tags):
                for tag in tags:
                    value=select('us-gaap',tag,start=start)
                    if value is not None:return value
                return None
            long_in=flow(('ProceedsFromDebtMaturingInMoreThanThreeMonths','ProceedsFromIssuanceOfLongTermDebt'))
            long_out=flow(('RepaymentsOfDebtMaturingInMoreThanThreeMonths','RepaymentsOfLongTermDebt'))
            if long_in is None or long_out is None:fail('Complete supported long-term/maturity debt cash flows unavailable')
            if long_in<0 or long_out<0:fail('Debt component sign requires review')
            broad_maturity='ProceedsFromDebtMaturingInMoreThanThreeMonths' in audit['facts']
            short=flow(('ProceedsFromRepaymentsOfShortTermDebtMaturingInThreeMonthsOrLess',)) if broad_maturity else flow(('ProceedsFromRepaymentsOfShortTermDebt','ProceedsFromRepaymentsOfCommercialPaper'))
            if short is None:fail('Supported short-term financing aggregate unavailable')
            net_debt=long_in-long_out+short
            common_in=flow(('ProceedsFromIssuanceOfCommonStock','ProceedsFromStockOptionsExercised'))
            repurchases=flow(('PaymentsForRepurchaseOfCommonStock',))
            dividends=flow(('PaymentsOfDividendsCommonStock','PaymentsOfDividends'))
            withholding=flow(('PaymentsRelatedToTaxWithholdingForShareBasedCompensation',))
            preferred=flow(('PaymentsOfDividendsPreferredStock',))
            if preferred is not None and preferred!=0:fail('Preferred cash distributions require a separate common-equity model')
            for label,value in [('common proceeds',common_in),('repurchases',repurchases),('dividends',dividends),('withholding',withholding)]:
                if value is not None and value<0:fail('Equity financing sign requires review: '+label)
            equity=(common_in or 0)-(repurchases or 0)-(dividends or 0)-(withholding or 0)
            other=flow(('ProceedsFromPaymentsForOtherFinancingActivities',))
            total=flow(('NetCashProvidedByUsedInFinancingActivities',))
            if total is None:fail('Net financing cash-flow total unavailable')
            residual=total-(net_debt+equity+(other or 0))
            audit['financing_reconciliation']={'reported_total':total,'supported_debt_net':net_debt,
                'supported_equity_net':equity,'other_financing_net':other,'residual':residual,
                'note':'Unreported components are accepted only if disclosed financing lines reconcile to the total within $1. Unknown positive other financing is not treated as debt proceeds.'}
            if abs(residual)>1:fail('Financing cash-flow components do not reconcile; manual review required')
            if other is not None and other>0:fail('Positive unidentified financing inflow requires classification')
            net=net_debt+min(other or 0,0)
            method='Conservative equity cash-flow proxy'
    # Use the latest known filing's share count, not an old annual count that
    # could predate repurchases, issuance or stock splits. Provenance is separate.
    share_records=[]
    known_accessions={r['accessionNumber'] for r in known if r['form'] in ('10-K','10-Q')}
    for row in facts.get('facts',{}).get('dei',{}).get('EntityCommonStockSharesOutstanding',{}).get('units',{}).get('shares',[]):
        if row.get('accn') not in known_accessions or row.get('form') not in ('10-K','10-Q') or row.get('start'):continue
        try:
            asof=date.fromisoformat(row['end']);filed=date.fromisoformat(row['filed']);value=float(row['val'])
            if filed>today or not 0<=(today-asof).days<=150:continue
            if isinstance(row['val'],bool) or not math.isfinite(value) or value<=0:fail('Invalid share count')
        except (KeyError,TypeError,ValueError) as error:
            if isinstance(error,SECDataError):raise
            fail('Invalid share-count context')
        share_records.append((row,value))
    if not share_records:fail('Positive SEC share count within 150 days unavailable')
    latest=max(row['end'] for row,_ in share_records)
    share_records=[pair for pair in share_records if pair[0]['end']==latest]
    if len({value for _,value in share_records})!=1:fail('Conflicting SEC share counts')
    share_row,shares=max(share_records,key=lambda pair:pair[0]['filed'])
    audit['facts']['EntityCommonStockSharesOutstanding']={'value':shares,'unit':'shares','end':latest,'accession':share_row['accn']}
    fcfe=ocf-capex+net
    if fcfe<=0:fail('Reported annual FCFE is not positive; simple DCF is unavailable')
    return {'annual_fcfe_per_share':fcfe/shares,'evidence_date':end,
            'notes':method+': SEC annual operating cash flow − capex + supported debt cash flows. Reconciled proxy cases deduct unidentified financing outflows. Latest filing share count within 150 days; not cycle-normalized; verify corporate actions and other equity claims.',
            'audit':audit,'fcfe':fcfe,'shares':shares,'method':method}


def load_cashflow_inputs(symbol,cik,today):
    if cik is None or cik=='':
        mapping=fetch_json('company_tickers.json')
        matches=[row.get('cik_str') for row in mapping.values() if isinstance(row,dict)
                 and row.get('ticker') in (symbol,symbol.replace('.','-'))] if isinstance(mapping,dict) else []
        if len(set(matches))!=1:raise SECDataError('Unique SEC ticker-to-CIK mapping unavailable')
        cik=matches[0]
    text=str(cik)
    if not re.fullmatch(r'\d{1,10}',text) or int(text)<=0:raise SECDataError('Verified CIK unavailable')
    padded=text.zfill(10)
    return cashflow_inputs(symbol,padded,fetch_json('submissions/CIK'+padded+'.json'),
                           fetch_json('api/xbrl/companyfacts/CIK'+padded+'.json'),today)


def estimate_automatic(symbol,cik,price,today):
    from valuation import estimate
    inputs=load_cashflow_inputs(symbol,cik,today)
    model={'symbol':symbol,**{k:inputs[k] for k in ('annual_fcfe_per_share','evidence_date','notes')},
           'growth_pct':5,'discount_pct':10,'terminal_growth_pct':2,'years':5}
    result=estimate(price,model,today)
    result.update(input_source='Automatic SEC evidence',input_audit=inputs['audit'],method=inputs['method']+' DCF estimate',
                  note=inputs['notes']+' 5% growth, 10% discount and 2% terminal growth are editable scenario assumptions, not forecasts.')
    return result
