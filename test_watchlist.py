import unittest
from copy import deepcopy
from test_demand import DemandTests
from engine import demand_zone,demand_watch_candidate
from compare_demand import compare


class WatchlistTests(unittest.TestCase):
    def setUp(self):
        fixture=DemandTests();fixture.setUp()
        self.days=fixture.days;self.cfg=fixture.cfg
        self.days[-8]['low']=98

    def audit(self):
        result={}
        self.assertIsNone(demand_zone(101,self.days,self.cfg,diagnostics=result))
        return result

    def test_watchlist_only_pending_confirmation(self):
        watch=demand_watch_candidate(self.audit())
        self.assertIsNotNone(watch)
        self.assertFalse(watch['trade_eligible'])
        self.assertIn('Options liquidity and risk',watch['unchecked'])

    def test_invalidated_zone_excluded(self):
        self.days[-1]['low']=97
        self.assertIsNone(demand_watch_candidate(self.audit()))

    def test_outside_distance_excluded(self):
        audit=self.audit();audit['candidates'][0]['distance_atr']=4
        self.assertIsNone(demand_watch_candidate(audit))

    def test_confirmed_zone_excluded(self):
        self.days[-1].update(open=99,low=98.5,close=101)
        audit={}
        self.assertIsNotNone(demand_zone(101,self.days,self.cfg,diagnostics=audit))
        self.assertIsNone(demand_watch_candidate(audit))

    def test_offline_window_cannot_change_live_default(self):
        self.days[-12]['low']=97.5
        self.days[-8]['low']=100
        self.days[-6].update(open=99,low=98,close=101)
        self.assertIsNone(demand_zone(101,self.days,self.cfg))
        self.assertIsNotNone(demand_zone(101,self.days,self.cfg,retest_window=10))
        self.assertIsNone(demand_zone(101,self.days,self.cfg))

    def test_comparison_does_not_mutate_inputs(self):
        histories={'TEST':self.days};before=deepcopy(histories)
        result=compare(histories,self.cfg)
        self.assertEqual(histories,before)
        self.assertEqual(result['observations'],6)

    def test_history_must_be_ordered(self):
        with self.assertRaisesRegex(ValueError,'ascending'):
            compare({'TEST':self.days[::-1]},self.cfg)


if __name__=='__main__':unittest.main()
