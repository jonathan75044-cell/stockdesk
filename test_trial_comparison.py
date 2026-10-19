import copy
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from trial_comparison import comparison_rows,capture_trial
from revised_swing import DEFAULTS

class ComparisonTests(unittest.TestCase):
 def setUp(self):
  self.now=datetime(2026,10,19,16,tzinfo=timezone.utc)
  plan=dict(checks=[dict(stage='watch',name='Discovery',status='pass'),dict(stage='ready',name='Technical',status='pass')],entry=100,stop=95,target=115,effective_target=115,risk_per_share=5,reward_risk=3)
  self.state=dict(completed_at=self.now.isoformat(),stale=False,research_only=False,market_clock=dict(state='open',regular_session_end='2026-10-19T20:00:00+00:00'),rows=[],watchlist=[],golden_zones=[],diagnostics=[dict(symbol='TEST',outcome='Blocked',swing_technical_pass=False,trial_capture=dict(plan=plan,price=100,quote_at=self.now.isoformat(),data_date='2026-10-16',config=DEFAULTS,benchmarks={'SPY':dict(source='test',data_date='2026-10-16',trend='Uptrend',relative_strength_pp=1)}))])
 def test_trial_does_not_mutate_current_results(self):
  before=copy.deepcopy(self.state);r=comparison_rows(self.state,self.now)[0]
  self.assertEqual(before,self.state);self.assertFalse(r['current_ranked']);self.assertFalse(r['current_technical']);self.assertFalse(r['trial']['trade_eligible']);self.assertEqual(r['trial']['stage'],'Ready to review')
 def test_old_scan_requests_new_evidence(self):
  del self.state['diagnostics'][0]['trial_capture'];self.assertIn('new scan',comparison_rows(self.state,self.now)[0]['reason'])
 def test_no_calendar_or_sector_evidence_is_invented(self):
  r=comparison_rows(self.state,self.now)[0]['trial'];unknown=[c['name'] for c in r['checks'] if c['status']=='unknown']
  self.assertIn('Verified earnings outside holding window',unknown);self.assertIn('Sector-appropriate financial review',unknown);self.assertIn('Personal risk and allocation budget',unknown)
 def test_supported_valuation_transferred_only_when_available(self):
  self.state['golden_zones']=[dict(symbol='TEST',valuation=dict(status='estimated',intrinsic_value=120))]
  r=comparison_rows(self.state,self.now)[0]['trial'];self.assertEqual(next(c['status'] for c in r['checks'] if c['name']=='Supported undervaluation'),'pass')
 def test_stale_and_after_hours_quote_never_pass(self):
  for key in ('stale','research_only'):
   self.state[key]=True;r=comparison_rows(self.state,self.now)[0]['trial'];self.assertEqual(next(c['status'] for c in r['checks'] if c['name']=='Fresh regular-session quote'),'fail');self.state[key]=False
 def test_current_ranked_swing_distinct_from_put(self):
  self.state['rows']=[dict(symbol='TEST',put=True,swing=None)];self.assertFalse(comparison_rows(self.state,self.now)[0]['current_ranked'])
  self.state['rows'][0]['swing']={'entry':100};self.assertTrue(comparison_rows(self.state,self.now)[0]['current_ranked'])
 def test_capture_failure_remains_separate(self):
  del self.state['diagnostics'][0]['trial_capture'];self.state['diagnostics'][0]['trial_error']='Invalid history';r=comparison_rows(self.state,self.now)[0];self.assertEqual(r['reason'],'Invalid history');self.assertEqual(r['current'],'Blocked')
 def test_cached_assessment_is_idempotent(self):
  self.assertEqual(comparison_rows(self.state,self.now),comparison_rows(self.state,self.now))
if __name__=='__main__':unittest.main()
