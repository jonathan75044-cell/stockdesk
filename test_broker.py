import unittest
from datetime import datetime,timezone,timedelta
from ibkr_bridge import snapshot
from broker import validate_snapshot,portfolio_status
class Response:
 def __init__(self,value):self.value=value
 def raise_for_status(self):pass
 def json(self):return self.value
class Session:
 def __init__(self):self.paths=[]
 def get(self,url,**kwargs):
  self.paths.append(url)
  if url.endswith('/accounts'):return Response([{'accountId':'U1234567'}])
  if url.endswith('/summary'):return Response({'netliquidation':{'amount':10000,'currency':'USD'},'accountId':'U1234567'})
  if url.endswith('/ledger'):return Response({'USD':{'cashbalance':5000,'accountId':'U1234567'}})
  return Response([{'contractDesc':'TEST PUT','assetClass':'OPT','position':-1,'mktValue':-100,'accountId':'U1234567'}])
class Tests(unittest.TestCase):
 def test_snapshot(self):
  s=Session();p=snapshot(s,'https://localhost/v1/api',True)
  self.assertEqual(len(s.paths),4);self.assertTrue(all('/portfolio/' in x for x in s.paths))
  self.assertNotIn('U1234567',str(p));self.assertEqual(p['accounts'][0]['positions'][0]['position'],-1)
  self.assertEqual(validate_snapshot(p),p);self.assertFalse(portfolio_status(p)['stale'])
 def test_stale(self):
  p={'captured_at':(datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()}
  self.assertTrue(portfolio_status(p)['stale']);self.assertFalse(portfolio_status(None)['connected'])
 def test_bad_snapshot(self):
  for p in ({},{'source':'other'},{'source':'IBKR Client Portal Gateway','captured_at':'bad'}):
   with self.assertRaises((ValueError,KeyError)):validate_snapshot(p)
if __name__=='__main__':unittest.main()
