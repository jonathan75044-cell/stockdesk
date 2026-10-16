import unittest
from datetime import datetime,date,timedelta
from unittest.mock import patch,Mock
from schwab import Schwab,NY

class DailyHistoryTests(unittest.TestCase):
    def clock_at(self,hour,close=16,regular=True):
        now=datetime(2026,10,15,hour,tzinfo=NY)
        sessions=[{'start':'2026-10-15T09:30:00-04:00','end':f'2026-10-15T{close:02}:00:00-04:00'}] if regular else []
        with patch('schwab.datetime') as dt,patch.object(Schwab,'get',return_value={'equity':{'EQ':{'isOpen':True,'sessionHours':{'regularMarket':sessions}}}}):
            dt.now.return_value=now;dt.fromisoformat.side_effect=datetime.fromisoformat
            return Schwab().clock()
    def test_session_boundaries_and_early_close(self):
        self.assertFalse(self.clock_at(8)['completed_today'])
        self.assertFalse(self.clock_at(12)['completed_today'])
        self.assertTrue(self.clock_at(17)['completed_today'])
        self.assertTrue(self.clock_at(14,close=13)['completed_today'])
        self.assertFalse(self.clock_at(17,regular=False)['completed_today'])
    def history(self,cutoff):
        now=datetime(2026,10,15,22,tzinfo=NY)
        candles=[{'datetime':int(datetime(2026,10,d,tzinfo=NY).timestamp()*1000),'close':100,'volume':6000000} for d in (14,15)]
        with patch('schwab.datetime') as dt,patch.object(Schwab,'get',return_value={'candles':candles}) as get:
            dt.now.return_value=now;dt.fromtimestamp.side_effect=datetime.fromtimestamp
            rows=Schwab().days('AAPL',cutoff)
            params=get.call_args.kwargs
            self.assertEqual(params['endDate'],int(now.timestamp()*1000))
            self.assertEqual(params['startDate'],int((now-timedelta(days=730)).timestamp()*1000))
            self.assertNotIn('period',params)
            return rows
    def test_after_close_keeps_today(self):
        self.assertEqual(self.history(date(2026,10,16))[-1]['date'],'2026-10-15')
    def test_live_and_preopen_exclude_today(self):
        self.assertEqual(self.history(date(2026,10,15))[-1]['date'],'2026-10-14')
