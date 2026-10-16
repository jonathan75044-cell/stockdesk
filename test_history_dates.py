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
            dt.combine.side_effect=datetime.combine;dt.min=datetime.min
            rows=Schwab().days('AAPL',cutoff)
            params=get.call_args.kwargs
            self.assertEqual(params['endDate'],int(datetime.combine(cutoff-timedelta(days=1),datetime.min.time(),NY).replace(hour=16).timestamp()*1000))
            self.assertEqual(params['startDate'],int((now-timedelta(days=730)).timestamp()*1000))
            self.assertNotIn('period',params)
            return rows
    def test_after_close_keeps_today(self):
        self.assertEqual(self.history(date(2026,10,16))[-1]['date'],'2026-10-15')
    def test_live_and_preopen_exclude_today(self):
        self.assertEqual(self.history(date(2026,10,15))[-1]['date'],'2026-10-14')

    def duplicate_history(self,candles):
        with patch.object(Schwab,'get',return_value={'candles':candles}):
            return Schwab().days('AAPL',date(2026,10,16))
    def candle(self,day=15,**changes):
        return dict(datetime=int(datetime(2026,10,day,tzinfo=NY).timestamp()*1000),
                    open=100,high=105,low=99,close=103,volume=6000000,**changes)
    def test_identical_duplicates_count_once_and_sort(self):
        c=self.candle()
        rows=self.duplicate_history([c,dict(c),self.candle(14)])
        self.assertEqual([r['date'] for r in rows],['2026-10-14','2026-10-15'])
        self.assertEqual(rows[-1]['volume'],6000000)
    def test_matching_ohlcv_with_different_timestamp_same_day(self):
        c=self.candle();other=dict(c,datetime=c['datetime']+3600000)
        self.assertEqual(len(self.duplicate_history([c,other])),1)
    def test_conflicting_fields_rejected_with_date(self):
        for field in ('open','high','low','close','volume'):
            with self.subTest(field=field):
                c=self.candle();other=dict(c);other[field]+=1
                with self.assertRaisesRegex(ValueError,'AAPL on 2026-10-15.*'+field):
                    self.duplicate_history([c,other])
    def test_incomplete_duplicates_not_silently_accepted(self):
        c=self.candle();del c['volume']
        with self.assertRaisesRegex(ValueError,'volume'):
            self.duplicate_history([c,dict(c)])
    def test_unfinished_day_excluded_before_duplicate_validation(self):
        c=self.candle(16)
        self.assertEqual(self.duplicate_history([c,dict(c,close=999)]),[])

    def test_live_response_regression_excludes_appended_snapshot(self):
        historical={'open':346.95,'high':347.85,'low':341.6,'close':342.0,
                    'volume':39910007,'datetime':1792040400000}
        snapshot=dict(historical,volume=39767218,datetime=1792036800000)
        close=datetime(2026,10,15,16,tzinfo=NY)
        def response(path,**params):
            return {'candles':[historical] if params['endDate']<=int(close.timestamp()*1000)
                    else [historical,snapshot]}
        with patch.object(Schwab,'get',side_effect=response),patch('schwab.datetime') as dt:
            dt.now.return_value=close.replace(hour=22);dt.combine.side_effect=datetime.combine
            dt.min=datetime.min;dt.fromtimestamp.side_effect=datetime.fromtimestamp
            rows=Schwab().days('AAPL',date(2026,10,16))
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['volume'],39910007)
        self.assertEqual(rows[0]['date'],'2026-10-15')
    def test_exchange_early_close_bounds_history(self):
        s=Schwab();now=datetime(2026,10,15,14,tzinfo=NY)
        market={'equity':{'EQ':{'isOpen':False,'sessionHours':{'regularMarket':[
            {'start':'2026-10-15T09:30:00-04:00','end':'2026-10-15T13:00:00-04:00'}]}}}}
        with patch('schwab.datetime') as dt,patch.object(s,'get',side_effect=[market,{'candles':[]}]) as get:
            dt.now.return_value=now;dt.fromisoformat.side_effect=datetime.fromisoformat
            dt.combine.side_effect=datetime.combine;dt.min=datetime.min
            clock=s.clock();s.days('AAPL',date(2026,10,16))
        self.assertTrue(clock['completed_today'])
        self.assertEqual(clock['completed_session_end'],'2026-10-15T13:00:00-04:00')
        self.assertEqual(get.call_args.kwargs['endDate'],int(now.replace(hour=13).timestamp()*1000))
    def test_history_bound_uses_eastern_dst(self):
        for day,utc_hour in ((date(2026,1,15),21),(date(2026,7,15),20)):
            with self.subTest(day=day),patch.object(Schwab,'get',return_value={'candles':[]}) as get,patch('schwab.datetime') as dt:
                dt.now.return_value=datetime(2026,10,15,22,tzinfo=NY)
                dt.combine.side_effect=datetime.combine;dt.min=datetime.min
                Schwab().days('AAPL',day+timedelta(days=1))
                from datetime import timezone
                end=datetime.fromtimestamp(get.call_args.kwargs['endDate']/1000,timezone.utc)
                self.assertEqual(end.hour,utc_hour)
                self.assertEqual(end.date(),day)
