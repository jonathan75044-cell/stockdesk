import unittest
from decision import swing_checks_pass

class IndependentSwingTests(unittest.TestCase):
    def checks(self):return [dict(name=n,status='pass') for n in ('Underlying quote freshness','Completed daily history','Annual fundamental gate','Demand confirmation','Put trend')]
    def test_old_demand_and_put_trend_do_not_block_swing(self):
        c=self.checks();c[-1]['status']='fail';c[-2]['status']='fail'
        self.assertTrue(swing_checks_pass({'rr':2},c,True))
    def test_common_fail_or_unknown_still_blocks(self):
        for status in ('fail','unknown'):
            c=self.checks();c[0]['status']=status
            self.assertFalse(swing_checks_pass({'rr':2},c,True))
    def test_reversal_and_earnings_not_bypassed(self):
        self.assertFalse(swing_checks_pass(None,self.checks(),True))
        self.assertFalse(swing_checks_pass({'rr':2},self.checks(),False))
        self.assertFalse(swing_checks_pass({'rr':2},[],True))
