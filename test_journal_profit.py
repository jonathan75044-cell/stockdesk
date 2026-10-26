import unittest,copy
from journal_profit import estimates
class ProfitTests(unittest.TestCase):
 def row(self,i,qty,cash,effect,account='A',symbol='XYZ',asset='EQUITY'):
  return dict(activity_id=str(i),date=f'2026-10-{i:02d}T15:00:00Z',account=account,status='VALID',net_amount=cash,legs=[dict(symbol=symbol,asset=asset,quantity=qty,effect=effect)],description='Trade')
 def test_long_profit_after_costs_and_no_mutation(self):
  rows=[self.row(1,10,-1001,'OPENING'),self.row(2,-10,1099,'CLOSING')];before=copy.deepcopy(rows)
  r=estimates(rows);self.assertIsNone(r[0]['profit']);self.assertEqual(r[1]['profit'],98);self.assertEqual(rows,before)
 def test_short_put_uses_net_cash_without_assumed_multiplier(self):
  r=estimates([self.row(1,-2,599,'OPENING',asset='OPTION'),self.row(2,2,-201,'CLOSING',asset='OPTION')]);self.assertEqual(r[1]['profit'],398)
 def test_partial_fifo_and_loss(self):
  rows=[self.row(1,10,-1001,'OPENING'),self.row(2,10,-1201,'OPENING'),self.row(3,-15,1648,'CLOSING'),self.row(4,-5,499,'CLOSING')]
  r=estimates(rows);self.assertEqual(r[2]['profit'],46.5);self.assertEqual(r[3]['profit'],-101.5);self.assertEqual(sum(x['profit'] or 0 for x in r),-55)
 def test_missing_entry_does_not_guess(self):
  r=estimates([self.row(1,-10,1000,'CLOSING'),self.row(2,10,-900,'OPENING'),self.row(3,-10,1100,'CLOSING')]);self.assertTrue(all(x['profit'] is None for x in r))
 def test_accounts_and_symbols_are_separate(self):
  r=estimates([self.row(1,10,-1000,'OPENING'),self.row(2,-10,1100,'CLOSING',account='B'),self.row(3,-10,1100,'CLOSING',symbol='OTHER')]);self.assertTrue(all(x['profit'] is None for x in r))
 def test_invalid_or_ambiguous_data_blocks_matching(self):
  for change in ({'status':'PENDING'},{'net_amount':float('nan')},{'date':''},{'description':'Option assignment'}):
   opening=self.row(1,10,-1000,'OPENING');opening.update(change)
   self.assertIsNone(estimates([opening,self.row(2,-10,1100,'CLOSING')])[1]['profit'])
 def test_multi_leg_and_unspecified_effect(self):
  for multi in (True,False):
   opening=self.row(1,10,-1000,'OPENING')
   if multi:opening['legs'].append(dict(opening['legs'][0]))
   else:opening['legs'][0]['effect']=''
   self.assertIsNone(estimates([opening,self.row(2,-10,1100,'CLOSING')])[1]['profit'])
 def test_cash_direction_and_insufficient_quantity(self):
  for qty,cash in ((5,-500),(10,1000)):
   self.assertIsNone(estimates([self.row(1,qty,cash,'OPENING'),self.row(2,-10,1100,'CLOSING')])[1]['profit'])
 def test_sorting_revisions_and_break_even(self):
  opening=self.row(1,10,-1000,'OPENING');closing=self.row(2,-10,1000,'CLOSING')
  self.assertEqual(estimates([closing,opening])[0]['profit'],0)
  closing['net_amount']=1050;self.assertEqual(estimates([closing,opening])[0]['profit'],50)
if __name__=='__main__':unittest.main()
