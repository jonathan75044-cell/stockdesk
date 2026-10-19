import copy
import unittest
from datetime import datetime,timezone
from unittest.mock import patch
from trial_comparison import comparison_rows,capture_trial,sma200_context
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

class SMA200Tests(ComparisonTests):
 def bars(self,n):
  return [dict(date=str(i),close=100) for i in range(n)]
 def test_history_boundaries(self):
  self.assertIsNone(sma200_context(self.bars(199),101)['above'])
  for count in (200,204):
   c=sma200_context(self.bars(count),101);self.assertTrue(c['above']);self.assertEqual(c['direction'],'Unknown')
  self.assertEqual(sma200_context(self.bars(205),101)['direction'],'Flat')
 def test_price_strictly_above(self):
  for price,above in ((99,False),(100,False),(101,True)):
   c=sma200_context(self.bars(200),price);self.assertEqual(c['above'],above);self.assertAlmostEqual(c['distance_pct'],price-100)
 def test_direction_uses_five_sessions(self):
  rows=self.bars(205);rows[-1]['close']=200
  self.assertEqual(sma200_context(rows,101)['direction'],'Rising')
  rows[-1]['close']=50
  self.assertEqual(sma200_context(rows,101)['direction'],'Falling')
 def test_invalid_close_unknown(self):
  rows=self.bars(205);rows[-1]['close']=float('nan')
  self.assertIsNone(sma200_context(rows,101)['value'])
 def test_filter_only_changes_trial_variant(self):
  for above in (True,False,None):
   self.state['diagnostics'][0]['trial_capture']['sma200']=dict(above=above,direction='Falling')
   before=copy.deepcopy(self.state);r=comparison_rows(self.state,self.now)[0]
   self.assertEqual(before,self.state)
   self.assertEqual(r['trial']['stage'],'Ready to review')
   self.assertEqual(r['trial_with_sma200']['stage'],'Ready to review' if above is True else 'Not ready for watchlist')
   self.assertFalse(r['trial_with_sma200']['trade_eligible'])
 def test_old_capture_unknown_filter(self):
  r=comparison_rows(self.state,self.now)[0]
  c=next(c for c in r['trial_with_sma200']['checks'] if c['name']=='Price above 200-day average')
  self.assertEqual(c['status'],'unknown');self.assertIn('new scan',c['detail'])

if __name__=='__main__':unittest.main()
