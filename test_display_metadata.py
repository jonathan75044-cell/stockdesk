import unittest
from unittest.mock import patch
from provider import Data,positive_pe


class MetadataTests(unittest.TestCase):
    def setUp(self):self.data=Data.__new__(Data)
    def test_sector_not_industry(self):
        with patch.object(self.data,'fh',return_value={'finnhubIndustry':'Software'}):
            result=self.data.display_metadata('TEST',{'peTTM':25})
        self.assertIsNone(result['sector']);self.assertEqual(result['pe_ttm'],25)
    def test_profile_failure_keeps_pe(self):
        with patch.object(self.data,'fh',side_effect=ValueError('Provider unavailable')):
            result=self.data.display_metadata('TEST',{'peTTM':25})
        self.assertIsNone(result['sector']);self.assertEqual(result['pe_ttm'],25)
    def test_reported_sector_and_pe(self):
        with patch.object(self.data,'fh',return_value={'gsector':'Information Technology'}):
            result=self.data.display_metadata('TEST',{'peTTM':25.5})
        self.assertEqual(result['sector'],'Information Technology');self.assertEqual(result['pe_ttm'],25.5)
    def test_nonmeaningful_pe_is_unavailable(self):
        for value in (0,-1,float('nan'),float('inf'),None,True,'invalid'):
            self.assertIsNone(positive_pe(value))
    def test_missing_metrics_requests_pe_ttm(self):
        with patch.object(self.data,'fh',side_effect=[{'gsector':'Industrials'},{'metric':{'peTTM':20}}]) as fh:
            result=self.data.display_metadata('TEST')
        self.assertEqual(result['pe_ttm'],20)
        self.assertEqual(fh.call_args_list[1].args[0],'stock/metric')


if __name__=='__main__':unittest.main()
