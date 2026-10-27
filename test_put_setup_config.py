import unittest, tempfile, json, time
from pathlib import Path
from datetime import date, timedelta
from unittest.mock import patch
from engine import put_candidate
import app


class PutSetupConfigTests(unittest.TestCase):
    def test_expiry_boundaries(self):
        cfg=json.loads((app.ROOT/'config.json').read_text())
        self.assertEqual((cfg['put_dte_min'],cfg['put_dte_max']),(7,45))
        today=date.today()
        opt=dict(option_type='put',contract_size=100,symbol='TEST',strike=90,bid=1,ask=1.1,
                 greeks={'delta':-.2},open_interest=800,volume=100,bid_date=time.time()*1000,ask_date=time.time()*1000)
        for dte,expected in [(6,False),(7,True),(21,True),(45,True),(46,False)]:
            opt['expiration_date']=str(today+timedelta(days=dte))
            self.assertEqual(bool(put_candidate(100,opt,cfg,today)),expected)

    def test_saved_expiration_migrates_once_and_preserves_other_preferences(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(app,'DB',Path(tmp)/'test.db'):
            for key in ('resistance_rules_version','scan_state_version'):app.save(key,1)
            app.save('rules_version',5)
            app.save('config',dict(put_dte_min=21,put_dte_max=35,cash_per_position=4567))
            before={'rows':[{'symbol':'TEST'}],'completed_at':'2026-10-16T15:00:00+00:00'}
            app.save('state',before)
            cfg=app.config()
            self.assertEqual((cfg['put_dte_min'],cfg['put_dte_max']),(7,45))
            self.assertEqual(cfg['cash_per_position'],4567)
            self.assertEqual(app.get('previous_scan'),before)
            self.assertEqual(app.get('state')['rows'],[])
            app.save('config',{**cfg,'put_dte_min':10})
            self.assertEqual(app.config()['put_dte_min'],10)
