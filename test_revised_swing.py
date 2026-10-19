import copy
import unittest
from datetime import date, timedelta
from unittest.mock import patch
from revised_swing import assess, technical, DEFAULTS


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        dated=dict(source='Test evidence',checked_at='2026-10-19T15:00:00+00:00')
        self.case=dict(as_of='2026-10-19T15:01:00+00:00',expected_completed_session='2026-10-16',days=[],price=100,
            benchmarks={'SPY':dict(source='Test',data_date='2026-10-16',trend='Uptrend',relative_strength_pp=2)},
            valuation=dict(dated,supported=True,intrinsic_value=120),
            financial_review=dict(dated,sector='Technology',policy='Documented industry review',evidence='Reviewed annual cash flow and solvency',passed=True),
            earnings=dict(dated,verified=True,next_date='2026-11-10'),
            quote=dict(session='open',at='2026-10-19T15:00:00+00:00',session_end='2026-10-19T20:00:00+00:00'),
            sizing=dict(cash=10000,maximum_loss=100,allocation_cash=5000))
        self.plan=dict(checks=[dict(stage='watch',name='Discovery',status='pass'),dict(stage='ready',name='Entry',status='pass')],entry=100,risk_per_share=2)
    def run_case(self):
        with patch('revised_swing.technical',return_value=copy.deepcopy(self.plan)):
            return assess(self.case)
    def test_pass_is_trial_only_and_inputs_unchanged(self):
        before=copy.deepcopy(self.case);r=self.run_case()
        self.assertEqual(r['stage'],'All required checks passed');self.assertFalse(r['trade_eligible']);self.assertTrue(r['experimental'])
        self.assertEqual(r['hypothetical_shares'],50);self.assertEqual(before,self.case)
    def test_stage_transitions(self):
        self.plan['checks'][1]['status']='fail';self.assertEqual(self.run_case()['stage'],'Watch')
        self.plan['checks'][0]['status']='unknown';self.assertEqual(self.run_case()['stage'],'Not ready for watchlist')
    def test_empty_calendar_never_confirms(self):
        self.case['earnings']={};self.assertEqual(self.run_case()['stage'],'Ready to review')
    def test_earnings_inclusive_boundary(self):
        self.case['earnings']['next_date']='2026-11-04';self.assertEqual(self.run_case()['stage'],'Ready to review')
        self.case['earnings']['next_date']='2026-11-05';self.assertEqual(self.run_case()['stage'],'All required checks passed')
    def test_holding_period_changes_window(self):
        self.case['config']={'holding_days':30};self.assertEqual(self.run_case()['stage'],'Ready to review')
    def test_unverified_and_past_earnings_block(self):
        self.case['earnings']['verified']=False;self.assertEqual(self.run_case()['stage'],'Ready to review')
        self.case['earnings']['verified']=True;self.case['earnings']['next_date']='2026-10-01';self.assertEqual(self.run_case()['stage'],'Ready to review')
    def test_stale_future_and_missing_sources_block(self):
        for field in ('valuation','earnings','financial_review'):
            original=copy.deepcopy(self.case[field])
            for checked in ('2025-01-01T00:00:00+00:00','2026-10-20T00:00:00+00:00'):
                self.case[field]['checked_at']=checked;self.assertEqual(self.run_case()['stage'],'Ready to review')
            self.case[field]=dict(original,source='');self.assertEqual(self.run_case()['stage'],'Ready to review')
            self.case[field]=original
    def test_valuation_must_be_positive_supported_discount(self):
        for value in (None,0,100,99,float('nan')):
            self.case['valuation']['intrinsic_value']=value;self.assertEqual(self.run_case()['stage'],'Ready to review')
        self.case['valuation'].update(intrinsic_value=120,supported=False);self.assertEqual(self.run_case()['stage'],'Ready to review')
    def test_financial_policy_not_waived(self):
        for field in ('sector','policy','evidence'):
            original=self.case['financial_review'].pop(field);self.assertEqual(self.run_case()['stage'],'Ready to review');self.case['financial_review'][field]=original
        self.case['financial_review']['passed']=False;self.assertEqual(self.run_case()['stage'],'Ready to review')
    def test_only_selected_benchmark_required(self):
        self.case['benchmarks']['QQQ']={'trend':'Downtrend'};self.assertEqual(self.run_case()['stage'],'All required checks passed')
        self.case['config']={'benchmark':'QQQ'};self.assertNotEqual(self.run_case()['stage'],'All required checks passed')
    def test_mismatched_benchmark_and_negative_strength(self):
        self.case['benchmarks']['SPY']['data_date']='2026-10-15';self.assertEqual(self.run_case()['stage'],'Watch')
        self.case['benchmarks']['SPY'].update(data_date='2026-10-16',relative_strength_pp=-1);self.assertEqual(self.run_case()['stage'],'Watch')
    def test_closed_stale_future_quote(self):
        for at in ('2026-10-19T14:00:00+00:00','2026-10-19T16:00:00+00:00'):
            self.case['quote']['at']=at;self.assertEqual(self.run_case()['stage'],'Ready to review')
        self.case['quote'].update(at='2026-10-19T15:00:00+00:00',session='closed');self.assertEqual(self.run_case()['stage'],'Ready to review')
    def test_sizing_boundaries(self):
        self.case['sizing']['maximum_loss']=1;self.assertEqual(self.run_case()['hypothetical_shares'],0)
        self.case['sizing'].update(maximum_loss=1000,allocation_cash=200);self.assertEqual(self.run_case()['hypothetical_shares'],2)
        self.case['sizing']['cash']=100;self.assertEqual(self.run_case()['hypothetical_shares'],1)
    def test_invalid_config_and_intraday_history_rejected(self):
        self.case['config']={'round_trip_cost_per_share':-1}
        with self.assertRaises(ValueError):self.run_case()
        self.case['config']={};self.case['expected_completed_session']='2026-10-19'
        with self.assertRaises(ValueError):self.run_case()


class TechnicalTests(unittest.TestCase):
    def setUp(self):
        self.bars=[dict(date=str(date(2026,6,1)+timedelta(days=i)),open=100+i*.1,close=100+i*.1,low=98+i*.1,high=102+i*.1,volume=6000000) for i in range(70)]
        self.session=self.bars[-1]['date']
    def check(self,result,name):
        return next(c['status'] for c in result['checks'] if c['name']==name)
    def test_real_indicator_pipeline_no_invented_pivots(self):
        r=technical(self.bars,108,self.session,DEFAULTS)
        self.assertEqual(self.check(r,'Higher confirmed swing low'),'unknown');self.assertIsNone(r['touch'])
    def test_invalid_duplicate_and_missing_session(self):
        with self.assertRaises(ValueError):technical(self.bars,108,'2026-01-01',DEFAULTS)
        self.bars[-1]['date']=self.bars[-2]['date']
        with self.assertRaises(ValueError):technical(self.bars,108,self.session,DEFAULTS)
    def test_zone_touch_uses_only_available_prefix_and_volume_on_reversal(self):
        self.bars[-3].update(open=106,close=105,low=104,high=107,volume=3000000)
        self.bars[-2].update(open=106,close=108,low=105,high=109,volume=9000000)
        self.bars[-1].update(open=108,close=108,low=107,high=108.5,volume=2000000)
        prefixes=[]
        def zone(price,prefix,atr):
            prefixes.append(len(prefix))
            return dict(in_zone=len(prefix)==68,zone_low=103,zone_high=107,priority=True) if len(prefix)==68 else None
        with patch('revised_swing.pullback_zone',side_effect=zone):
            r=technical(self.bars,109.1,self.session,DEFAULTS)
        self.assertEqual(prefixes,[70,69,68]);self.assertEqual(r['touch']['touch_date'],self.bars[-3]['date'])
        self.assertEqual(r['reversal_date'],self.bars[-2]['date'])
        self.assertEqual(self.check(r,'Reversal-day volume'),'pass');self.assertEqual(self.check(r,'Break above reversal high'),'pass')
        self.assertGreater(r['entry'],r['touch']['zone_high'])
    def test_lower_volume_floor_cannot_bypass_five_million(self):
        for b in self.bars:b['volume']=4000000
        r=technical(self.bars,108,self.session,{**DEFAULTS,'min_avg_volume':1000000})
        self.assertEqual(self.check(r,'Liquidity'),'fail')
    def test_nearest_obstacle_and_costs_reduce_reward(self):
        evidence=dict(target1={'price':120},target2=None,nearest_overhead_high={'price':109})
        with patch('revised_swing.resistance_levels',return_value=evidence):
            r=technical(self.bars,108,self.session,DEFAULTS)
        self.assertEqual(r['effective_target'],109);self.assertLess(r['reward_risk'],1)
        self.assertEqual(self.check(r,'Reward/risk after assumed costs'),'fail')


if __name__=='__main__':unittest.main()
