import unittest, threading, tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import app

class ScanFeedback(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=patch.object(app,'DB',Path(self.temp.name)/'test.db');self.db.start()
        self.lock=patch.object(app,'lock',threading.Lock());self.lock.start()
        app.save('rules_version',5);app.save('scan_state_version',1)
    def tearDown(self):
        self.lock.stop();self.db.stop();self.temp.cleanup()
    def test_closed_starts_research_and_preserves_results_until_worker_runs(self):
        before={'status':'Monitoring','rows':[{'symbol':'TEST'}],'completed_at':'2026-10-15T19:00:00+00:00'}
        app.save('state',before)
        with patch.object(app,'Data') as data,patch.object(app.threading,'Thread') as worker:
            data.return_value.clock.return_value={'state':'closed'}
            result,code=app.request_scan()
        self.assertEqual(code,202);self.assertTrue(result['queued']);worker.return_value.start.assert_called_once()
        self.assertIn('research',result['message']);self.assertEqual(app.get('state'),before)
        self.assertTrue(app.lock.locked());app.lock.release()
    def test_open_starts_reserved_worker(self):
        with patch.object(app,'Data') as data,patch.object(app.threading,'Thread') as worker:
            data.return_value.clock.return_value={'state':'open'}
            result,code=app.request_scan()
        self.assertEqual(code,202);self.assertTrue(result['queued']);worker.return_value.start.assert_called_once()
        self.assertTrue(app.lock.locked());app.lock.release()
    def test_busy_does_not_start_second_worker(self):
        app.lock.acquire()
        with patch.object(app,'Data') as data:
            result,code=app.request_scan()
        self.assertEqual(code,409);data.assert_not_called();self.assertTrue(app.lock.locked());app.lock.release()
    def test_failure_releases_reservation(self):
        with patch.object(app,'Data',side_effect=RuntimeError('secret')):
            result,code=app.request_scan()
        self.assertEqual(code,503);self.assertNotIn('secret',str(result));self.assertFalse(app.lock.locked())
    def test_repair_archives_old_diagnostics(self):
        app.save('scan_state_version',0)
        old={'status':'Market closed · agent waiting','completed_at':None,'scanned':166,'total':166,'diagnostics':[{'symbol':'AAPL'}],'errors':[{'reason':'old'}],'rows':[]}
        app.save('state',old);app.config()
        self.assertEqual(app.get('previous_scan'),old)
        self.assertEqual(app.get('state')['scanned'],0);self.assertEqual(app.get('state')['diagnostics'],[])
    def test_completed_scan_not_cleared_by_repair(self):
        app.save('scan_state_version',0)
        old={'status':'Monitoring','completed_at':'2026-10-15T19:00:00+00:00','rows':[{'symbol':'AAPL'}]}
        app.save('state',old);app.config();self.assertEqual(app.get('state'),old)

class AfterHoursScan(ScanFeedback):
    def run_scan(self,closed=True,completed=True,age=0):
        from datetime import datetime,timedelta
        from zoneinfo import ZoneInfo
        today=datetime.now(ZoneInfo('America/New_York')).date()
        day=str(today-timedelta(days=age))
        data=MagicMock();data.clock.return_value={'state':'closed' if closed else 'open','completed_today':completed}
        data.days.return_value=[{'date':day,'close':100,'volume':6000000}]
        data.research.return_value={'quality':{},'earnings':[],'metrics':{}}
        data.display_metadata.return_value={}
        data.quotes.return_value=[{'last':999,'trade_date':0}]
        cfg=app.config();cfg.update(universe='TEST',notifications_enabled=True)
        with patch.object(app,'Data',return_value=data),patch.object(app,'config',return_value=cfg),patch.object(app,'indicators',return_value={'atr':2,'avgvol':6000000,'ma20':95,'ma50':90}),patch.object(app,'pullback_zone',return_value=None),patch.object(app,'demand_zone',return_value=None),patch.object(app,'demand_watch_candidate',return_value=None),patch.object(app,'swing',return_value={'score':5,'rr':2}),patch.object(app,'fundamental_gate',return_value={'pass':True}),patch.dict(app.os.environ,{'SEC_USER_AGENT':'','ALERT_WEBHOOK_URL':'https://example.invalid'}),patch.object(app.requests,'post') as post:
            app.scan()
            post.assert_not_called()
        return app.get('state'),data,today
    def test_closed_scan_retains_dated_candidates_without_quotes_options_or_alerts(self):
        state,data,today=self.run_scan(age=1)
        self.assertTrue(state['completed_at']);self.assertTrue(state['research_only'])
        self.assertEqual(len(state['rows']),1);self.assertEqual(state['rows'][0]['price'],100)
        self.assertFalse(state['rows'][0]['market_ready']);self.assertIsNone(state['rows'][0]['put'])
        self.assertEqual(state['data_dates'],[state['rows'][0]['data_date']])
        data.quotes.assert_not_called();data.options.assert_not_called()
        data.days.assert_any_call('TEST',today+app.timedelta(days=1))
        data.days.assert_any_call('SPY',today+app.timedelta(days=1))
        data.days.assert_any_call('QQQ',today+app.timedelta(days=1))
    def test_preopen_excludes_current_day(self):
        state,data,today=self.run_scan(completed=False,age=1)
        data.days.assert_any_call('TEST',today)
        data.days.assert_any_call('SPY',today)
        data.days.assert_any_call('QQQ',today)
    def test_old_history_is_rejected(self):
        state,data,today=self.run_scan(age=6)
        self.assertEqual(state['rows'],[]);self.assertIn('stale',state['errors'][0]['reason'])
    def test_live_scan_still_rejects_stale_quote(self):
        state,data,today=self.run_scan(closed=False,age=1)
        self.assertFalse(state['research_only']);self.assertEqual(state['rows'],[])
        self.assertIn('Stale underlying quote',state['errors'][0]['reason'])

if __name__=='__main__':unittest.main()
