import unittest
from unittest.mock import patch
from engine import swing

class SwingBlockerTests(unittest.TestCase):
    def run_case(self,ma20,ma50,rvol):
        reasons=[]
        m=dict(ma20=ma20,ma50=ma50,rvol=rvol,avgvol=6000000,atr=2)
        cfg=dict(min_price=10,min_avg_volume=5000000,swing_min_rvol=1.3)
        with patch('engine.indicators',return_value=m),patch('engine.pullback_zone',return_value={'in_zone':True}):
            result=swing(100,[{'volume':rvol*6000000}],cfg,reasons)
        self.assertIsNone(result)
        return reasons
    def test_only_volume_fails(self):
        r=self.run_case(110,100,1.1);self.assertEqual(len(r),1);self.assertIn('1.1000x; minimum 1.3000x',r[0])
    def test_only_trend_fails(self):
        r=self.run_case(99,100,1.5);self.assertEqual(len(r),1);self.assertIn('$99.0000',r[0]);self.assertIn('$100.0000',r[0])
    def test_both_fail_are_reported(self):
        r=self.run_case(99,100,1.1);self.assertEqual(len(r),2)
    def test_equal_averages_fail_strict_trend(self):
        r=self.run_case(100,100,1.3);self.assertEqual(len(r),1);self.assertIn('Uptrend failed',r[0])
