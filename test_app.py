import unittest,time
from datetime import date,timedelta
from engine import put_candidate,swing
import json
from pathlib import Path
class Rules(unittest.TestCase):
 def setUp(self):
  self.cfg=json.loads(Path(__file__).with_name('config.json').read_text());self.today=date.today()
  self.opt={'option_type':'put','contract_size':100,'symbol':'TEST_PUT','strike':90,'bid':1,'ask':1.1,'greeks':{'delta':-.2},'open_interest':800,'expiration_date':str(self.today+timedelta(days=30)),'bid_date':time.time()*1000,'ask_date':time.time()*1000}
 def test_put_economics(self):
  r=put_candidate(100,self.opt,self.cfg,self.today);self.assertEqual(r['collateral'],9000);self.assertEqual(r['max_loss'],8900);self.assertEqual(r['breakeven'],89)
 def test_stale_option_rejected(self):
  self.opt['bid_date']=0;self.assertIsNone(put_candidate(100,self.opt,self.cfg,self.today))
 def test_insufficient_cash(self):
  self.cfg['cash_per_position']=5000;self.assertIsNone(put_candidate(100,self.opt,self.cfg,self.today))
 def test_wide_spread(self):
  self.opt['ask']=2;self.assertIsNone(put_candidate(100,self.opt,self.cfg,self.today))
 def test_no_manufactured_targets(self):
  days=[{'close':50+i*.5,'high':51+i*.5,'low':49+i*.5,'volume':2000000} for i in range(70)]
  days[-1]['close']=86;days[-1]['high']=87;days[-1]['volume']=4000000
  self.assertIsNone(swing(86,days,self.cfg))
class NewRules(Rules):
 def test_otm_boundary(self):
  self.opt['strike']=96;self.assertIsNone(put_candidate(100,self.opt,self.cfg,self.today))
 def test_low_delta(self):
  self.opt['greeks']['delta']=-.19;self.assertIsNone(put_candidate(100,self.opt,self.cfg,self.today))
 def test_absolute_spread(self):
  self.opt.update(bid=3,ask=3.2);self.assertIsNone(put_candidate(100,self.opt,self.cfg,self.today))
 def test_quality(self):
  from engine import fundamental_gate
  f=dict(period=str(self.today),revenue_growth_pct=5,fcf=100,current_ratio=2,debt_equity=.4)
  self.assertIsNotNone(fundamental_gate({'quality':f},self.cfg,self.today))
  for k in ('fcf','revenue_growth_pct'):
   bad={**f,k:0};self.assertIsNone(fundamental_gate({'quality':bad},self.cfg,self.today))
  self.assertIsNone(fundamental_gate({},self.cfg,self.today))
 def test_morning(self):
  from app import cfg_morning_due
  from datetime import datetime
  now=datetime(2026,6,2,9,45)
  self.assertTrue(cfg_morning_due(now,self.cfg,None))
  self.assertFalse(cfg_morning_due(now,self.cfg,'2026-06-02'))
  self.assertFalse(cfg_morning_due(now.replace(hour=12),self.cfg,None))
 def test_demand(self):
  from engine import demand_zone
  days=[dict(open=101,close=101,high=102,low=100,volume=2000000,date=str(self.today)) for _ in range(70)]
  self.assertIsNone(demand_zone(101,days,self.cfg))
  days[-8]['low']=98
  days[-2].update(open=98.5,low=98.5,close=101)
  self.assertIsNotNone(demand_zone(101,days,self.cfg))
  days[-1]['low']=97
  self.assertIsNone(demand_zone(101,days,self.cfg))
if __name__=='__main__':unittest.main()

