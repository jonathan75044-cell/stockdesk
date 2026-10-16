import unittest
from datetime import date
from unittest.mock import patch
from provider import Data,parse_annual_quality,FundamentalDataError
from sec_fundamentals import SECDataError,CIKS
from symbols import canonical_symbol,canonical_universe
from schwab import market_symbol


def target_payload():
    def rows(values):return [{'concept':'us-gaap_'+k,'value':v} for k,v in values.items()]
    return {'data':[
        {'endDate':'2026-01-31','filedDate':'2026-03-11','accessNumber':'0000027419-26-000016',
         'report':{'ic':rows({'Revenues':104780000000}),
                   'cf':rows({'NetCashProvidedByUsedInOperatingActivities':6562000000,'PaymentsToAcquirePropertyPlantAndEquipment':3727000000}),
                   'bs':rows({'StockholdersEquity':16165000000,'AssetsCurrent':20005000000,
                              'LiabilitiesCurrent':21230000000,'LiabilitiesNoncurrent':22095000000})}},
        {'endDate':'2025-02-01','report':{'ic':rows({'Revenues':106566000000})}}]}

class MappingAuditTests(unittest.TestCase):
    def test_target_components_reconcile_without_guessing_nci(self):
        q=parse_annual_quality(target_payload(),date(2026,10,16))
        self.assertAlmostEqual(q['debt_equity'],43325000000/16165000000)
        self.assertAlmostEqual(q['current_ratio'],20005000000/21230000000)
        self.assertEqual(q['accounting_audit']['fields']['total_liabilities']['components'],
                         {'LiabilitiesCurrent':21230000000,'LiabilitiesNoncurrent':22095000000})
    def test_missing_component_still_fails(self):
        p=target_payload();p['data'][0]['report']['bs'].pop()
        with self.assertRaisesRegex(FundamentalDataError,'Cannot derive liabilities'):
            parse_annual_quality(p,date(2026,10,16))
    def test_negative_component_fails(self):
        p=target_payload();p['data'][0]['report']['bs'][-1]['value']=-1
        with self.assertRaisesRegex(FundamentalDataError,'Negative liability component'):
            parse_annual_quality(p,date(2026,10,16))
    def test_custom_component_is_not_mapped(self):
        p=target_payload();p['data'][0]['report']['bs'][-1]['concept']='tgt_LiabilitiesNoncurrent'
        with self.assertRaisesRegex(FundamentalDataError,'Cannot derive liabilities'):
            parse_annual_quality(p,date(2026,10,16))
    def test_reported_total_takes_precedence(self):
        p=target_payload();p['data'][0]['report']['bs'].append({'concept':'Liabilities','value':43325000000})
        q=parse_annual_quality(p,date(2026,10,16))
        self.assertEqual(q['accounting_audit']['fields']['total_liabilities']['concept'],'Liabilities')
    def test_duplicate_conflicting_component_fails(self):
        p=target_payload();p['data'][0]['report']['bs'].append({'concept':'LiabilitiesNoncurrent','value':1})
        with self.assertRaisesRegex(FundamentalDataError,'Conflicting values'):
            parse_annual_quality(p,date(2026,10,16))
    def test_verified_issuer_fallback_retains_provenance(self):
        for symbol in ('LRCX','PANW'):
            with self.subTest(symbol=symbol),patch.object(Data,'fh',return_value={'data':[]}),patch('sec_fundamentals.load_annual_payload',return_value=(target_payload(),{'filing_url':'https://www.sec.gov/example'})) as load:
                q=Data().quality(symbol,date(2026,10,16))
                load.assert_called_once_with(symbol,date(2026,10,16))
                self.assertEqual(q['source'],'SEC EDGAR annual 10-K companyfacts')
                self.assertIn('finnhub_audit',q)
    def test_unverified_issuer_not_enabled(self):
        with patch.object(Data,'fh',return_value={'data':[]}),patch('sec_fundamentals.load_annual_payload') as load:
            with self.assertRaises(FundamentalDataError):Data().quality('TSM',date(2026,10,16))
            load.assert_not_called()
    def test_failed_sec_fallback_keeps_both_audits(self):
        with patch.object(Data,'fh',return_value={'data':[]}),patch('sec_fundamentals.load_annual_payload',side_effect=SECDataError('missing exact fact',{'missing_fields':['current_assets']})):
            with self.assertRaises(FundamentalDataError) as caught:Data().quality('PANW',date(2026,10,16))
            self.assertIn('finnhub',caught.exception.details)
            self.assertEqual(caught.exception.details['sec']['missing_fields'],['current_assets'])
    def test_berkshire_aliases_deduplicate_and_reach_schwab(self):
        self.assertEqual(canonical_universe('BRK.B BRK-B BRK/B AAPL SQ XYZ'),['BRK.B','AAPL','XYZ'])
        for symbol in ('BRK.B','BRK-B','BRK/B'):
            self.assertEqual(market_symbol(symbol),'BRK/B')
    def test_only_confirmed_ticker_typo_is_corrected(self):
        self.assertEqual(canonical_symbol('NUFG'),'MUFG')
        self.assertEqual(canonical_symbol('NUFX'),'NUFX')
        self.assertEqual(canonical_symbol('MUFG'),'MUFG')
    def test_verified_ciks(self):
        self.assertEqual(CIKS['LRCX'],'0000707549')
        self.assertEqual(CIKS['PANW'],'0001327567')

    def test_alert_aliases_share_identity_and_keep_allowlist(self):
        from tradingview_alerts import validate_alert,AlertError
        from datetime import datetime,timezone
        secret='test-only-token-'*3
        payload={'token':secret,'symbol':'BRK-B','exchange':'NYSE','trigger':'research','time':'2026-10-16T00:00:00Z'}
        now=datetime(2026,10,16,tzinfo=timezone.utc).timestamp()
        first=validate_alert(payload,secret,{'BRK.B'},now)
        self.assertEqual(first['symbol'],'BRK.B')
        payload['symbol']='BRK.B'
        self.assertEqual(first['id'],validate_alert(payload,secret,{'BRK-B'},now)['id'])
        with self.assertRaises(AlertError):validate_alert(payload,secret,{'AAPL'},now)
    def test_saved_universe_normalizes_for_display_and_scan(self):
        import tempfile
        from pathlib import Path
        import app
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'DB',Path(tmp)/'test.db'):
            app.save('rules_version',5);app.save('scan_state_version',1)
            app.save('config',{'universe':'BRK.B BRK-B NUFG MUFG AAPL'})
            self.assertEqual(app.config()['universe'],'BRK.B MUFG AAPL')
