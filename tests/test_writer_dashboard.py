import unittest
from pathlib import Path
from app.services import run_scan
class WriterDashboardTests(unittest.TestCase):
    def test_writer_dashboard_generated(self):
        r=run_scan(); p=Path(r['dashboard']); self.assertTrue(p.exists())
        txt=p.read_text(encoding='utf-8')
        self.assertIn('本轮最值得写的3条',txt)
        self.assertIn('建议切入点',txt)
if __name__=='__main__':unittest.main()
