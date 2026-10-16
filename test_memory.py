import json,unittest,tempfile,threading
from pathlib import Path
from unittest.mock import patch,MagicMock
import sec_fundamentals as sec
import app
from provider import Data

class MemoryTests(unittest.TestCase):
    def setUp(self):
        sec._cache.clear()
        self.env=patch.dict(sec.os.environ,{'SEC_USER_AGENT':'Test test@example.com'});self.env.start()
        self.sleep=patch.object(sec.time,'sleep');self.sleep.start()
    def tearDown(self):sec._cache.clear();self.env.stop();self.sleep.stop()
    def fetch(self,path,payload):
        response=MagicMock();response.__enter__.return_value.read.return_value=json.dumps(payload).encode()
        with patch.object(sec,'urlopen',return_value=response):return sec.fetch_json(path)
    def test_many_companyfacts_are_not_retained(self):
        for i in range(30):
            self.assertEqual(self.fetch(f'api/xbrl/companyfacts/CIK{i:010}.json',{'facts':[i]*1000})['facts'][0],i)
        self.assertEqual(sec._cache,{})
    def test_small_cache_is_bounded(self):
        for i in range(12):self.fetch(f'submissions/CIK{i:010}.json',{'cik':i})
        self.assertEqual(len(sec._cache),sec.CACHE_MAX_ENTRIES)
    def test_oversized_small_endpoint_is_not_cached(self):
        self.fetch('company_tickers.json',{'data':'x'*sec.CACHE_MAX_RESPONSE_BYTES})
        self.assertEqual(sec._cache,{})
    def test_expired_entries_are_evicted(self):
        sec._cache['company_tickers.json']=(sec.time.monotonic()-4000,{'old':True})
        self.fetch('submissions/CIK0000000001.json',{})
        self.assertNotIn('company_tickers.json',sec._cache)
    def test_small_cache_hit_avoids_network(self):
        path='submissions/CIK0000000001.json';self.fetch(path,{'ok':True})
        with patch.object(sec,'urlopen') as request:
            self.assertEqual(sec.fetch_json(path),{'ok':True});request.assert_not_called()
    def test_only_cik_retained_from_annual_reports(self):
        d=Data()
        with patch.object(d,'fh',return_value={'cik':123,'data':['large']*100}),patch('provider.parse_annual_quality',return_value={'ok':True}):
            self.assertEqual(d.quality('AAPL'),{'ok':True})
        self.assertEqual(d._annual_reports,{'AAPL':{'cik':123}})
    def test_restart_marks_incomplete_but_preserves_completed(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'DB',Path(tmp)/'state.db'):
            for status in ('Scanning','Loading table metadata','Loading automatic valuations · 3/50 · AAPL'):
                app.save('state',{'status':status,'rows':[]});app.recover_interrupted_scan()
                self.assertIn('interrupted',app.get('state')['status']);self.assertIsNone(app.get('state')['completed_at'])
            done={'status':'Monitoring','completed_at':'2026-10-15T20:00:00+00:00'}
            app.save('state',done);app.recover_interrupted_scan();self.assertEqual(app.get('state'),done)
