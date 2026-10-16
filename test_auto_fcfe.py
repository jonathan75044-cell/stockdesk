import unittest,copy
from datetime import date
from auto_fcfe import cashflow_inputs
from sec_fundamentals import SECDataError
from valuation import estimate

def fixture():
    acc='0000831259-26-000012'
    sub={'cik':831259,'sic':1000,'tickers':['FCX'],'filings':{'recent':{'form':['10-Q','10-K'],'reportDate':['2026-06-30','2025-12-31'],'filingDate':['2026-08-06','2026-02-13'],'accessionNumber':['0000831259-26-000036',acc],'primaryDocument':['q.htm','k.htm']}}}
    values={'NetCashProvidedByUsedInOperatingActivities':5610000000,'PaymentsToAcquireProductiveAssets':4494000000,'ProceedsFromIssuanceOfDebt':3195000000,'RepaymentsOfDebt':2777000000}
    gaap={k:{'units':{'USD':[{'accn':acc,'form':'10-K','filed':'2026-02-13','start':'2025-01-01','end':'2025-12-31','val':v}]}} for k,v in values.items()}
    shares={'accn':'0000831259-26-000036','form':'10-Q','filed':'2026-08-06','end':'2026-07-31','val':1436017523}
    return sub,{'cik':831259,'facts':{'us-gaap':gaap,'dei':{'EntityCommonStockSharesOutstanding':{'units':{'shares':[shares]}}}}}

class CapexMatching(unittest.TestCase):
    def run_inputs(self,sub,facts):return cashflow_inputs('FCX',831259,sub,facts,date(2026,10,15))
    def test_fcx_reported_aggregate_produces_estimate(self):
        sub,facts=fixture();v=self.run_inputs(sub,facts)
        self.assertEqual(v['fcfe'],1534000000)
        model={'symbol':'FCX',**{k:v[k] for k in ('annual_fcfe_per_share','evidence_date','notes')},'growth_pct':5,'discount_pct':10,'terminal_growth_pct':2,'years':5}
        result=estimate(69.62,model,date(2026,10,15))
        self.assertEqual(result['status'],'estimated');self.assertEqual(result['classification'],'overvalued')
        self.assertEqual(v['audit']['capital_expenditure']['selected_tag'],'PaymentsToAcquireProductiveAssets')
    def test_does_not_double_count_components(self):
        sub,facts=fixture();g=facts['facts']['us-gaap'];g['PaymentsToAcquirePropertyPlantAndEquipment']=copy.deepcopy(g['PaymentsToAcquireProductiveAssets'])
        g['PaymentsToAcquirePropertyPlantAndEquipment']['units']['USD'][0]['val']=4000000000
        self.assertEqual(self.run_inputs(sub,facts)['fcfe'],1534000000)
    def test_pp_e_fallback(self):
        sub,facts=fixture();g=facts['facts']['us-gaap'];g['PaymentsToAcquirePropertyPlantAndEquipment']=g.pop('PaymentsToAcquireProductiveAssets')
        self.assertEqual(self.run_inputs(sub,facts)['fcfe'],1534000000)
    def test_wrong_period_accession_currency_and_negative_rejected(self):
        for key,value in [('start','2025-04-01'),('end','2024-12-31'),('accn','other'),('val',-1)]:
            sub,facts=fixture();facts['facts']['us-gaap']['PaymentsToAcquireProductiveAssets']['units']['USD'][0][key]=value
            with self.assertRaises(SECDataError):self.run_inputs(sub,facts)
        sub,facts=fixture();c=facts['facts']['us-gaap']['PaymentsToAcquireProductiveAssets'];c['units']['EUR']=c['units'].pop('USD')
        with self.assertRaises(SECDataError):self.run_inputs(sub,facts)
    def test_missing_records_have_audit_and_no_fabricated_value(self):
        sub,facts=fixture();facts['facts']['us-gaap'].pop('PaymentsToAcquireProductiveAssets')
        with self.assertRaises(SECDataError) as caught:self.run_inputs(sub,facts)
        self.assertIsNone(caught.exception.details['capital_expenditure']['selected_tag'])
