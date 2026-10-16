import unittest
from entry_plan import swing_entry_plan

class EntryPlanTests(unittest.TestCase):
    def setUp(self):
        self.days=[dict(date='2026-10-01',open=100,high=120,low=99,close=110,volume=6000000) for _ in range(70)]
        self.days[10]['high']=130
        for b in self.days[-5:]:b.update(open=102,high=106,low=100,close=103)
        self.days[-2].update(high=104,close=103)
        self.days[-1].update(date='2026-10-15',open=104,high=108,close=107)
        self.m=dict(atr=5,ma20=110,ma50=100,avgvol=6000000,rvol=1.5)
        self.zone=dict(zone_low=95,zone_high=115)
        self.cfg=dict(min_price=10,min_avg_volume=5000000,swing_min_rvol=1.3,swing_min_rr=2)
    def plan(self,price=107):return swing_entry_plan(price,self.days,self.m,self.zone,self.cfg)
    def test_confirmed_bar_still_yields_only_conditional_plan(self):
        p=self.plan();self.assertFalse(p['eligible']);self.assertEqual(p['entry'],107)
        self.assertEqual(p['stop'],99.5);self.assertEqual(p['target1'],120);self.assertEqual(p['target2'],130)
        self.assertEqual(p['financial_status'],'Not evaluated');self.assertEqual(p['earnings_status'],'Not evaluated')
    def test_unconfirmed_bar_requires_new_daily_reversal_and_rescan(self):
        self.days[-1].update(close=103,open=104)
        p=self.plan(103);self.assertEqual(p['entry'],108.01);self.assertIn('NEW completed daily bar',p['trigger'])
        self.assertFalse(next(c['passed'] for c in p['checks'] if c['name']=='Completed bullish reversal'))
    def test_real_targets_not_manufactured_to_meet_rr(self):
        p=self.plan();self.assertLess(p['reward_risk'],2)
        self.assertEqual(p['max_entry_for_rr'],106.33)
        self.assertFalse(next(c['passed'] for c in p['checks'] if c['name']=='First-target reward/risk meets minimum'))
    def test_no_historical_targets_stays_unavailable(self):
        for b in self.days[:-2]:b['high']=105
        p=self.plan();self.assertIsNone(p['target1']);self.assertIsNone(p['target2']);self.assertIsNone(p['reward_risk'])
    def test_entry_above_zone_is_blocked(self):
        p=self.plan(116)
        self.assertFalse(next(c['passed'] for c in p['checks'] if c['name']=='Planning entry inside pullback zone'))
    def test_price_gap_and_risk_limit_not_silently_accepted(self):
        p=self.plan(140)
        self.assertFalse(next(c['passed'] for c in p['checks'] if c['name']=='Positive stop and risk no greater than 2 ATR'))
    def test_negative_stop_is_unavailable_for_sizing(self):
        self.m['atr']=2000
        p=self.plan();self.assertIsNone(p['stop']);self.assertIsNone(p['risk_per_share'])
    def test_plan_does_not_mutate_zone_or_bars(self):
        import copy
        before=copy.deepcopy((self.days,self.zone));self.plan()
        self.assertEqual(before,(self.days,self.zone))

    def test_blocked_scan_saves_plan_without_promoting_stock(self):
        import app,tempfile,threading,json
        from pathlib import Path
        from unittest.mock import patch,MagicMock
        from datetime import datetime,timedelta
        from zoneinfo import ZoneInfo
        today=datetime.now(ZoneInfo('America/New_York')).date()
        for i,b in enumerate(self.days):b['date']=str(today-timedelta(days=len(self.days)-i))
        cfg=json.loads((app.ROOT/'config.json').read_text());cfg.update(self.cfg,universe='ANET')
        data=MagicMock();data.token=True;data.finn='configured';data.clock.return_value={'state':'closed','completed_today':False};data.days.return_value=self.days
        zone={**self.zone,'in_zone':True,'priority':True,'retracement':.55,'low_date':self.days[0]['date'],'high_date':self.days[40]['date'],'last_bar_date':self.days[-1]['date']}
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'DB',Path(tmp)/'test.db'),patch.object(app,'lock',threading.Lock()),patch.object(app,'config',return_value=cfg),patch.object(app,'Data',return_value=data),patch.object(app,'indicators',return_value=self.m),patch.object(app,'pullback_zone',return_value=zone),patch.object(app,'swing',return_value=None),patch.object(app,'demand_zone',return_value=None),patch.object(app,'demand_watch_candidate',return_value=None):
            app.scan();state=app.get('state')
        self.assertEqual(state['rows'],[]);self.assertEqual(len(state['golden_zones']),1)
        plan=state['golden_zones'][0]['entry_plan'];self.assertFalse(plan['eligible'])
        self.assertEqual(plan['financial_status'],'Not evaluated');self.assertEqual(plan['earnings_status'],'Not evaluated')
        data.research.assert_not_called();data.options.assert_not_called()
