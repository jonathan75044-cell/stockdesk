import copy
import unittest
from datetime import datetime, timezone
from setup_checklist import assess_setup, trend_checks


class SetupChecklistTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, 15, tzinfo=timezone.utc)
        self.item = dict(quote_at=self.now.isoformat(),
            entry_plan=dict(average_volume=6000000,reward_risk=2.5,data_date='2026-10-15', checks=[dict(name='Risk', passed=True)],
                preferred_checks=[dict(name='Trend', passed=True)],
                relative_strength={s:dict(available=True,end_date='2026-10-15',difference_pp=2) for s in ('SPY','QQQ')}),
            valuation=dict(status='estimated',classification='undervalued',valuation_pct=20),
            watchlist_research={k:dict(status=v,checked_at=self.now.isoformat(),reason='Evidence') for k,v in [('financial','passed'),('earnings','no_event_returned')]})
        self.state = dict(research_only=False,completed_at=self.now.isoformat(),stale=False,
            market_clock=dict(state='open',regular_session_end='2026-10-16T20:00:00+00:00'),
            market_context={s:dict(available=True,data_date='2026-10-15',trend='Uptrend') for s in ('SPY','QQQ')})
    def assess(self):
        return assess_setup(self.item,self.state,self.now)
    def test_complete_evidence_passes_without_mutating_eligibility(self):
        before=copy.deepcopy(self.item)
        self.assertEqual(self.assess()['status'],'Entry checks passed')
        self.assertEqual(self.item,before)
    def test_after_hours_never_confirms(self):
        self.state['research_only']=True
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
    def test_unknown_valuation_not_a_pass(self):
        self.item['valuation']={'status':'unavailable'}
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
    def test_overvalued_absolute_percentage_not_mislabeled(self):
        self.item['valuation']['classification']='overvalued'
        check=next(c for c in self.assess()['checks'] if c['name']=='Supported undervaluation')
        self.assertEqual(check['status'],'fail');self.assertEqual(check['detail'],'Not undervalued')
    def test_stale_quote_scan_and_closed_session_each_block(self):
        for field,value in [('quote_at','2026-10-16T14:00:00+00:00')]:
            self.item[field]=value
            self.assertEqual(self.assess()['status'],'Watchlist candidate')
        self.item['quote_at']=self.now.isoformat();self.state['stale']=True
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
        self.state['stale']=False;self.state['market_clock']['regular_session_end']='2026-10-16T14:00:00+00:00'
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
    def test_earnings_block_and_old_research_do_not_confirm(self):
        self.item['watchlist_research']['earnings']['status']='blocked'
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
        self.item['watchlist_research']['earnings']['status']='no_event_returned'
        self.item['watchlist_research']['financial']['checked_at']='2026-10-16T13:00:00+00:00'
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
    def test_missing_old_plan_and_mismatched_benchmarks_block(self):
        del self.item['entry_plan']['preferred_checks']
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
        self.item['entry_plan']['preferred_checks']=[]
        self.state['market_context']['SPY']['data_date']='2026-10-14'
        self.assertEqual(self.assess()['status'],'Watchlist candidate')
    def test_monotonic_trend_does_not_invent_pivot_structure(self):
        bars=[dict(close=100+i,high=101+i,low=99+i) for i in range(60)]
        checks=trend_checks(161,bars)
        self.assertTrue(checks[0]['passed']);self.assertTrue(checks[1]['passed'])
        self.assertIsNone(checks[2]['passed'])
    def test_falling_averages_fail(self):
        bars=[dict(close=200-i,high=201-i,low=199-i) for i in range(60)]
        self.assertFalse(trend_checks(140,bars)[1]['passed'])
