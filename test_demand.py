import json
import unittest
from datetime import date, timedelta
from pathlib import Path
from engine import demand_zone, indicators, put_candidate
import time


class DemandTests(unittest.TestCase):
    def setUp(self):
        self.cfg=json.loads(Path(__file__).with_name('config.json').read_text())
        self.days=[dict(open=101,close=101,high=102,low=100,volume=2000000,
                        date=str(date(2026,1,1)+timedelta(days=i))) for i in range(70)]

    def confirm(self,pivot=-4,retest=-1):
        self.days[pivot]['low']=98
        self.days[retest].update(open=99,low=98.5,close=101)

    def test_newest_eligible_pivot(self):
        self.confirm()
        audit={}
        zone=demand_zone(101,self.days,self.cfg,diagnostics=audit)
        self.assertIsNotNone(zone)
        self.assertEqual(zone['pivot_date'],self.days[-4]['date'])
        self.assertEqual(audit['candidates'][0]['outcome'],'Confirmed')

    def test_no_forward_looking_pivot(self):
        self.confirm(pivot=-3)
        self.assertIsNone(demand_zone(101,self.days,self.cfg))

    def test_old_retest_remains_rejected(self):
        self.confirm(pivot=-12,retest=-6)
        reasons=[]
        self.assertIsNone(demand_zone(101,self.days,self.cfg,reasons))
        self.assertIn('last five',reasons[0])

    def test_later_lower_low_invalidates(self):
        self.confirm(pivot=-8,retest=-2)
        self.days[-1]['low']=97
        audit={}
        self.assertIsNone(demand_zone(101,self.days,self.cfg,diagnostics=audit))
        self.assertEqual(audit['candidates'][0]['outcome'],'Invalidated by lower low')

    def test_bearish_retest_rejected(self):
        self.confirm()
        self.days[-1]['open']=101.5
        self.assertIsNone(demand_zone(101,self.days,self.cfg))

    def test_distance_and_exact_boundaries(self):
        self.confirm()
        zone=demand_zone(101,self.days,self.cfg)
        atr=indicators(self.days)['atr']
        self.assertEqual(zone['high'],98+.5*atr)
        self.assertIsNone(demand_zone(zone['high'],self.days,self.cfg))
        self.assertIsNone(demand_zone(zone['high']+3*atr+.001,self.days,self.cfg))

    def test_missing_open_is_data_error(self):
        del self.days[-1]['open']
        with self.assertRaisesRegex(ValueError,'open prices'):
            demand_zone(101,self.days,self.cfg)

    def test_nonfinite_and_zero_volume_are_data_errors(self):
        self.days[-1]['close']=float('nan')
        with self.assertRaisesRegex(ValueError,'OHLCV'):indicators(self.days)
        self.days[-1]['close']=101
        for b in self.days:b['volume']=0
        with self.assertRaisesRegex(ValueError,'volume'):indicators(self.days)

    def test_rounding_cannot_admit_strike_above_zone(self):
        today=date.today()
        opt=dict(option_type='put',contract_size=100,symbol='TEST',strike=90,
                 bid=1,ask=1.1,greeks={'delta':-.25},open_interest=800,
                 expiration_date=str(today+timedelta(days=30)),
                 bid_date=time.time()*1000,ask_date=time.time()*1000)
        reasons=[]
        self.assertIsNone(put_candidate(100,opt,self.cfg,today,{'high':89.999},reasons))
        self.assertEqual(reasons,['Strike above demand zone'])


if __name__=='__main__':unittest.main()
