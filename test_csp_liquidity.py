import unittest,json,time
from pathlib import Path
from datetime import date,timedelta
from engine import put_candidate
class LiquidityTests(unittest.TestCase):
 def setUp(self):
  self.cfg=json.loads(Path('config.json').read_text());self.today=date.today()
  self.opt=dict(option_type='put',contract_size=100,symbol='TEST',strike=90,bid=1,ask=1.1,greeks={'delta':-.2},open_interest=500,volume=100,bid_date=time.time()*1000,ask_date=time.time()*1000,expiration_date=str(self.today+timedelta(days=20)))
 def test_interest_boundaries(self):
  for oi,valid,preferred in ((499,False,False),(500,True,False),(999,True,False),(1000,True,True)):
   r=put_candidate(100,{**self.opt,'open_interest':oi},self.cfg,self.today)
   self.assertEqual(bool(r),valid)
   if r:self.assertEqual(r['preferred_liquidity'],preferred)
 def test_volume_boundaries_and_invalid(self):
  for volume in (None,0,99,99.9,float('nan'),float('inf'),True):
   self.assertIsNone(put_candidate(100,{**self.opt,'volume':volume},self.cfg,self.today))
  self.assertIsNotNone(put_candidate(100,self.opt,self.cfg,self.today))
  o=dict(self.opt);del o['volume'];self.assertIsNone(put_candidate(100,o,self.cfg,self.today))
 def test_no_bypass_with_high_interest_or_lower_saved_limits(self):
  self.assertIsNone(put_candidate(100,{**self.opt,'open_interest':5000,'volume':99},{**self.cfg,'put_min_volume':1},self.today))
  self.assertIsNone(put_candidate(100,{**self.opt,'open_interest':499},{**self.cfg,'put_min_oi':1},self.today))
 def test_invalid_interest(self):
  for oi in (True,500.5,None,float('inf'),float('nan')):
   self.assertIsNone(put_candidate(100,{**self.opt,'open_interest':oi},self.cfg,self.today))
 def test_review_explains_volume_and_preference(self):
  from decision import option_review
  for volume,expected in ((99,'fail'),(100,'pass'),(None,'unknown')):
   r=option_review(100,{**self.opt,'volume':volume,'open_interest':1000},self.cfg,self.today,{'high':95,'low':90},True,[])
   check=next(c for c in r['checks'] if c['name']=='Daily option volume')
   self.assertEqual(check['status'],expected);self.assertTrue(r['preferred_liquidity'])
   if volume!=100:self.assertFalse(r['trade_eligible'])
 def test_saved_liquidity_settings_migrate_once(self):
  import tempfile
  from unittest.mock import patch
  import app
  with tempfile.TemporaryDirectory() as tmp,patch.object(app,'DB',Path(tmp)/'test.db'):
   app.config();app.save('csp_liquidity_version',0)
   app.save('config',{**self.cfg,'put_min_oi':100,'cash_per_position':7777})
   app.save('state',{'rows':[{'symbol':'OLD'}],'completed_at':'2026-10-26'})
   c=app.config();self.assertEqual((c['put_min_oi'],c['put_preferred_oi'],c['put_min_volume']),(500,1000,100));self.assertEqual(c['cash_per_position'],7777)
   self.assertIsNone(app.get('state')['completed_at']);self.assertEqual(app.get('state')['rows'],[])
   app.save('config',{**c,'put_min_volume':200});self.assertEqual(app.config()['put_min_volume'],200)
if __name__=='__main__':unittest.main()

