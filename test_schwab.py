import unittest, tempfile, os, time
from datetime import date
from unittest.mock import patch, Mock
from schwab import Schwab
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.env=patch.dict(os.environ,{'DATA_DIR':self.tmp.name,'SCHWAB_APP_KEY':'test','SCHWAB_APP_SECRET':'test','SCHWAB_CALLBACK_URL':'https://example.com/auth/schwab/callback'})
  self.env.start();self.s=Schwab()
 def tearDown(self):self.env.stop();self.tmp.cleanup()
 def test_no_orders(self):
  with self.assertRaises(ValueError):self.s.get('accounts/orders')
 def test_oauth_refresh_preserves_age_and_secret_permissions(self):
  with patch('schwab.requests.post',return_value=Mock(ok=True,json=lambda:{'access_token':'a','refresh_token':'r','expires_in':1800})):
   self.s.finish('code');before=self.s.read()['authorized_at'];self.assertTrue(self.s.connected())
   self.s.exchange(grant_type='refresh_token',refresh_token='r')
   self.assertEqual(self.s.read()['authorized_at'],before)
   self.assertEqual(self.s.path.stat().st_mode&0o777,0o600)
 def test_delayed_underlying_rejected(self):
  with patch.object(self.s,'get',return_value={'JD':{'realtime':False}}):
   with self.assertRaises(ValueError):self.s.quotes(['JD'])
 def test_quote_normalization(self):
  with patch.object(self.s,'get',return_value={'JD':{'realtime':True,'quote':{'lastPrice':28,'tradeTime':1000,'totalVolume':22}}}):
   self.assertEqual(self.s.quotes(['JD'])[0]['trade_date'],1000)
 def test_option_normalization(self):
  c={'nonStandard':False,'symbol':'PUT','multiplier':100,'strikePrice':90,'bid':1,'ask':1.1,'delta':-.25,'openInterest':600,'quoteTimeInLong':12345}
  with patch.object(self.s,'get',return_value={'isDelayed':False,'putExpDateMap':{'2026-07-17:30':{'90':[c]}}}):
   o=list(self.s.options('JD',date(2026,6,1),{'put_dte_min':21,'put_dte_max':45}))[0]
   self.assertEqual(o['expiration_date'],'2026-07-17');self.assertEqual(o['bid_date'],12345)
 def test_unknown_delay_rejected(self):
  with patch.object(self.s,'get',return_value={}):
   with self.assertRaises(ValueError):list(self.s.options('JD',date.today(),{'put_dte_min':21,'put_dte_max':45}))
 def test_closed_clock(self):
  with patch.object(self.s,'get',return_value={'equity':{'EQ':{'isOpen':False}}}):self.assertEqual(self.s.clock()['state'],'closed')
if __name__=='__main__':unittest.main()
