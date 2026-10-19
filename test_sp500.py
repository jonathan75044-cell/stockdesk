import unittest
from unittest.mock import patch
from sp500 import constituents, scan_universe
from trial_comparison import top_comparisons
class SP500Tests(unittest.TestCase):
 def test_reference_is_complete_and_normalized(self):
  symbols=constituents();self.assertGreaterEqual(len(symbols),500);self.assertLess(len(symbols),520)
  self.assertIn('BRK.B',symbols);self.assertIn('NVDA',symbols);self.assertEqual(len(symbols),len(set(symbols)))
 def test_extra_symbols_are_trial_only_and_first(self):
  with patch('sp500.constituents',return_value=['AAPL','NVDA']):
   symbols,live,members=scan_universe('AAPL XYZ AAPL')
  self.assertEqual(symbols,['NVDA','AAPL','XYZ']);self.assertEqual(live,{'AAPL','XYZ'})
 def test_top25_stage_order_and_exclusions(self):
  def row(symbol,stage,filtered='Not ready for watchlist'):
   return dict(symbol=symbol,trial=dict(stage=stage,checks=[]),trial_with_sma200=dict(stage=filtered))
  rows=[row('X'+str(i),'Not ready for watchlist') for i in range(30)]
  rows+=[row('WATCH','Watch'),row('READY','Ready to review'),row('BOTH','Watch','Watch'),row('OUT','All required checks passed')]
  state={'sp500_universe':[r['symbol'] for r in rows if r['symbol']!='OUT']}
  with patch('trial_comparison.comparison_rows',return_value=rows):result=top_comparisons(state)
  self.assertEqual(len(result),25);self.assertEqual([r['symbol'] for r in result[:3]],['READY','BOTH','WATCH']);self.assertNotIn('OUT',[r['symbol'] for r in result]);self.assertEqual(result[-1]['rank'],25)
 def test_old_scan_has_no_unverified_members(self):
  with patch('trial_comparison.comparison_rows',return_value=[{'symbol':'NVDA'}]):self.assertEqual(top_comparisons({}),[])
if __name__=='__main__':unittest.main()
