import unittest
from datetime import date,timedelta
from unittest.mock import Mock
from market_context import load_market_context,relative_strength

class MarketTests(unittest.TestCase):
    def setUp(self):
        self.today=date(2026,10,16)
        self.days=[{'date':str(self.today-timedelta(days=60-i)),'close':100+i} for i in range(60)]
        self.data=Mock();self.data.days.return_value=self.days
    def context(self):return load_market_context(self.data,self.today,self.today)
    def test_uptrend_and_bounded_storage(self):
        b=self.context()['SPY'];self.assertEqual(b['trend'],'Uptrend');self.assertEqual(len(b['recent_closes']),21)
    def test_downtrend(self):
        for i,b in enumerate(self.days):b['close']=200-i
        self.assertEqual(self.context()['QQQ']['trend'],'Downtrend')
    def test_equal_averages_mixed(self):
        for b in self.days:b['close']=100
        self.assertEqual(self.context()['SPY']['trend'],'Mixed')
    def test_failure_isolated(self):
        self.data.days.side_effect=[RuntimeError('secret'),self.days]
        c=self.context();self.assertFalse(c['SPY']['available']);self.assertTrue(c['QQQ']['available']);self.assertNotIn('secret',str(c))
    def test_duplicate_and_nonfinite_unavailable(self):
        self.days[-1]['date']=self.days[-2]['date'];self.assertFalse(self.context()['SPY']['available'])
        self.days[-1]['close']=float('nan');self.assertFalse(self.context()['QQQ']['available'])
    def test_return_math_and_matching_dates(self):
        c=self.context();stock=[dict(b) for b in self.days];stock[-1]['close']*=1.1
        r=relative_strength(stock,c)['SPY'];self.assertAlmostEqual(r['difference_pp'],100*(174.9-159)/139)
        stock[-1]['date']='2026-10-16';self.assertFalse(relative_strength(stock,c)['SPY']['available'])
    def test_missing_completed_session_label(self):
        c=load_market_context(self.data,self.today+timedelta(days=1),self.today,True)
        self.assertEqual(c['SPY']['freshness'],'Latest completed session missing')
