import unittest,copy
from datetime import date
from unittest.mock import Mock
from watchlist_research import enrich_watchlists
class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.data=Mock();self.data.quality.return_value=dict(period='2025-12-31',revenue_growth_pct=5,fcf=100,current_ratio=2,debt_equity=.5)
        self.data.fh.return_value={'earningsCalendar':[]}
        self.cfg=dict(min_current_ratio=1,max_debt_equity=1,earnings_buffer_days=3)
        self.state={'rows':[],'golden_zones':[{'symbol':'TEST','entry_plan':{'eligible':False}}],'watchlist':[{'symbol':'TEST'}]};self.cache={}
    def run_research(self,budget=60):
        enrich_watchlists(self.state,self.data,self.cfg,date(2026,10,16),self.cache.get,lambda k,v:self.cache.update({k:v}),budget)
        return self.state['watchlist'][0]['watchlist_research']
    def test_blocked_candidate_researched_without_promotion(self):
        r=self.run_research();self.assertEqual(r['financial']['status'],'passed');self.assertEqual(r['earnings']['status'],'no_event_returned')
        self.assertEqual(self.state['rows'],[]);self.assertFalse(self.state['golden_zones'][0]['entry_plan']['eligible']);self.data.quality.assert_called_once()
    def test_financial_failure_does_not_hide_earnings(self):
        self.data.quality.side_effect=RuntimeError('secret token');self.data.fh.return_value={'earningsCalendar':[{'date':'2026-10-20'}]}
        r=self.run_research();self.assertEqual(r['financial']['status'],'unavailable');self.assertEqual(r['earnings']['status'],'blocked');self.assertNotIn('secret',str(r))
    def test_missing_calendar_not_clear(self):
        self.data.fh.return_value={};self.assertEqual(self.run_research()['earnings']['status'],'unavailable')
    def test_missing_metrics_unavailable_not_failed(self):
        self.data.quality.return_value={};self.assertEqual(self.run_research()['financial']['status'],'unavailable')
    def test_failed_financial_distinct(self):
        self.data.quality.return_value['fcf']=-1;self.assertEqual(self.run_research()['financial']['status'],'failed')
    def test_cache_and_criteria_invalidation(self):
        self.run_research();self.run_research();self.data.quality.assert_called_once()
        self.cfg['min_current_ratio']=3;self.assertEqual(self.run_research()['financial']['status'],'failed');self.assertEqual(self.data.quality.call_count,2)
    def test_budget_marks_unavailable_without_calls(self):
        r=self.run_research(0);self.assertEqual(r['financial']['status'],'unavailable');self.data.quality.assert_not_called();self.data.fh.assert_not_called()
