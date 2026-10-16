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
    def test_closed_preserves_results_and_does_not_start_thread(self):
        before={'status':'Monitoring','rows':[{'symbol':'TEST'}],'completed_at':'2026-10-15T19:00:00+00:00'}
        app.save('state',before)
        with patch.object(app,'Data') as data,patch.object(app.threading,'Thread') as worker:
            data.return_value.clock.return_value={'state':'closed'}
            result,code=app.request_scan()
        self.assertEqual(code,409);self.assertFalse(result['queued']);worker.assert_not_called()
        self.assertEqual(app.get('state'),before);self.assertFalse(app.lock.locked())
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

if __name__=='__main__':unittest.main()
