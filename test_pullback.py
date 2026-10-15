import unittest
from unittest.mock import patch
from datetime import date,timedelta
from pullback import pullback_zone

class PullbackTests(unittest.TestCase):
    def bars(self):
        bars=[dict(date=str(date(2026,1,1)+timedelta(days=i)),low=110.,high=115.) for i in range(30)]
        bars[5].update(low=100.,high=110.)
        bars[20].update(low=190.,high=200.)
        return bars
    def test_bounds_and_priority(self):
        for p in [161.8,150,138.2]:self.assertTrue(pullback_zone(p,self.bars(),5)['in_zone'])
        self.assertTrue(pullback_zone(150,self.bars(),5)['priority'])
        self.assertFalse(pullback_zone(155,self.bars(),5)['priority'])
        for p in [161.81,138.19,90,201]:self.assertFalse(pullback_zone(p,self.bars(),5)['in_zone'])
    def test_no_unconfirmed_endpoint_pivot(self):
        b=self.bars();b[20].update(low=110.,high=115.);b[-1]['high']=200.
        self.assertIsNone(pullback_zone(150,b,5))
    def test_dates_and_provenance(self):
        z=pullback_zone(150,self.bars(),5)
        self.assertLess(z['low_date'],z['high_date']);self.assertFalse(z['entry_confirmed']);self.assertIn('Schwab',z['source'])
        b=self.bars();b[-1]['date']=b[-2]['date']
        with self.assertRaises(ValueError):pullback_zone(150,b,5)
    def test_missing_history_is_not_a_match(self):
        b=self.bars();del b[0]['date']
        self.assertIsNone(pullback_zone(150,b,5));self.assertIsNone(pullback_zone(150,self.bars(),100))
    def test_entry_requires_reversal_and_real_reward_risk(self):
        from engine import swing
        days=[dict(open=170,close=170,high=180,low=165,volume=2000000) for _ in range(70)]
        days[10]['high']=190
        days[-3].update(low=147,high=149,close=149,open=148)
        days[-2].update(low=147,high=149,close=148,open=148)
        days[-1].update(low=148,high=152,close=151,open=149)
        cfg=dict(min_price=10,min_avg_volume=1000000,swing_min_rvol=1.3,swing_min_rr=2)
        m=dict(ma20=160,ma50=140,atr=10,avgvol=2000000,rvol=1.5)
        zone=dict(in_zone=True,zone_low=138.2)
        with patch('engine.indicators',return_value=m),patch('engine.pullback_zone',return_value=zone):
            trade=swing(150,days,cfg)
            self.assertIsNotNone(trade);self.assertGreaterEqual(trade['rr'],2)
            days[-1]['close']=148
            self.assertIsNone(swing(150,days,cfg))
