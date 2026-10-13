import unittest
from datetime import date
from valuation import estimate,validate_model

TODAY=date(2026,10,13)


def model(**changes):
    return {'symbol':'TEST','annual_fcfe_per_share':10,'growth_pct':0,
            'discount_pct':10,'terminal_growth_pct':0,'years':5,
            'evidence_date':'2025-12-31','notes':'Test normalized annual FCFE',**changes}


class ValuationTests(unittest.TestCase):
    def test_constant_cashflow_matches_perpetuity(self):
        value=estimate(80,model(),TODAY)
        self.assertAlmostEqual(value['intrinsic_value'],100)
        self.assertEqual(value['classification'],'undervalued')
        self.assertEqual(value['valuation_pct'],20)
    def test_overvalued(self):
        value=estimate(120,model(),TODAY)
        self.assertEqual(value['classification'],'overvalued')
        self.assertEqual(value['valuation_pct'],20)
    def test_fairly_valued(self):
        self.assertEqual(estimate(100,model(),TODAY)['classification'],'fairly valued')
    def test_missing_inputs_are_unavailable(self):
        self.assertEqual(estimate(100,None,TODAY)['status'],'unavailable')
    def test_terminal_growth_cannot_reach_discount(self):
        self.assertEqual(estimate(100,model(discount_pct=2,terminal_growth_pct=2),TODAY)['status'],'unavailable')
    def test_future_and_stale_evidence_are_unavailable(self):
        for day in ('2026-10-14','2021-12-31'):
            self.assertEqual(estimate(100,model(evidence_date=day),TODAY)['status'],'unavailable')
    def test_nonfinite_values_and_boolean_are_rejected(self):
        for value in (float('nan'),float('inf'),True):
            with self.assertRaises(ValueError):validate_model(model(annual_fcfe_per_share=value),TODAY)
    def test_fractional_years_rejected(self):
        with self.assertRaises(ValueError):validate_model(model(years=5.5),TODAY)
    def test_unavailable_cashflow_not_fabricated(self):
        for value in (0,-1):
            self.assertEqual(estimate(100,model(annual_fcfe_per_share=value),TODAY)['status'],'unavailable')
    def test_growing_cashflow_hand_calculation(self):
        value=estimate(100,model(growth_pct=5,terminal_growth_pct=2,years=2),TODAY)
        expected=10.5/1.1+11.025/1.1**2+(11.025*1.02/.08)/1.1**2
        self.assertAlmostEqual(value['intrinsic_value'],expected)
    def test_evidence_note_required(self):
        with self.assertRaises(ValueError):validate_model(model(notes=' '),TODAY)
    def test_model_does_not_mutate(self):
        m=model();before=dict(m);estimate(100,m,TODAY);self.assertEqual(m,before)


if __name__=='__main__':unittest.main()
