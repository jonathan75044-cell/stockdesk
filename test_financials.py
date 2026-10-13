import unittest
from datetime import date,timedelta
from provider import parse_annual_quality,FundamentalDataError


class FilingFreshnessTests(unittest.TestCase):
    def payload(self,end):
        return {'data':[{'endDate':str(end),'report':{}},
                        {'endDate':str(end-timedelta(days=365)),'report':{}}]}

    def test_screenshot_stale_period_precedes_missing_fields(self):
        with self.assertRaises(FundamentalDataError) as caught:
            parse_annual_quality(self.payload(date(2021,10,31)),date(2026,10,13))
        self.assertIn('fresh fundamental evidence',str(caught.exception))
        self.assertEqual(caught.exception.details['period'],'2021-10-31')
        self.assertGreater(caught.exception.details['age_days'],550)
        self.assertNotIn('missing_field',caught.exception.details)

    def test_future_period_rejected(self):
        with self.assertRaisesRegex(FundamentalDataError,'outside'):
            parse_annual_quality(self.payload(date(2026,10,14)),date(2026,10,13))

    def test_exact_freshness_boundary_still_parses_fields(self):
        today=date(2026,10,13)
        with self.assertRaises(FundamentalDataError) as caught:
            parse_annual_quality(self.payload(today-timedelta(days=550)),today)
        self.assertEqual(caught.exception.details['missing_field'],'revenue')

    def test_551_days_rejected_before_fields(self):
        today=date(2026,10,13)
        with self.assertRaisesRegex(FundamentalDataError,'outside'):
            parse_annual_quality(self.payload(today-timedelta(days=551)),today)


if __name__=='__main__':unittest.main()

