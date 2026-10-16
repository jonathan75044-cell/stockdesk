import unittest
from datetime import date,timedelta
from resistance import resistance_levels
class ResistanceTests(unittest.TestCase):
    def bars(self):
        b=[{'date':str(date(2026,1,1)+timedelta(days=i)),'high':100} for i in range(30)]
        b[5]['high']=110;b[15]['high']=120
        return b
    def test_dated_pivots_and_obstacle(self):
        b=self.bars();b[-1]['high']=105
        r=resistance_levels(b,102,4)
        self.assertEqual(r['target1']['price'],110);self.assertEqual(r['target2']['price'],120)
        self.assertEqual(r['target1']['confirmed_date'],b[7]['date']);self.assertEqual(r['nearest_overhead_high']['price'],105)
    def test_unconfirmed_endpoint_never_target(self):
        b=self.bars();b[-1]['high']=140
        self.assertIsNone(resistance_levels(b,125,4)['target1'])
    def test_equal_high_plateau_not_strict_pivot(self):
        b=self.bars();b[6]['high']=110
        self.assertEqual(resistance_levels(b,102,4)['target1']['price'],120)
    def test_nearest_target_not_skipped_for_reward(self):
        self.assertEqual(resistance_levels(self.bars(),109.99,4)['target1']['price'],110)
    def test_duplicate_dates_rejected(self):
        b=self.bars();b[2]['date']=b[1]['date']
        with self.assertRaises(ValueError):resistance_levels(b,102,4)

    def test_config_migration_preserves_custom_and_runs_once(self):
        import app
        from unittest.mock import patch
        for initial,expected in [(1000000,5000000),(7000000,7000000)]:
            store={'config':{'min_avg_volume':initial},'rules_version':5,'scan_state_version':1,'state':{'rows':[{'symbol':'OLD'}]}}
            with patch.object(app,'get',side_effect=lambda k,default=None:store.get(k,default)),patch.object(app,'save',side_effect=lambda k,v:store.update({k:v})):
                self.assertEqual(app.config()['min_avg_volume'],expected)
                self.assertEqual(store['state']['rows'],[])
                store['state']={'rows':[{'symbol':'NEW'}]}
                app.config();self.assertEqual(store['state']['rows'][0]['symbol'],'NEW')
