import json,unittest
from pathlib import Path
from app.services import run_scan
class ManualInputsTests(unittest.TestCase):
    def test_scan_reads_manual_inputs(self):
        r=run_scan(); data=json.loads(Path(r['candidates']).read_text(encoding='utf-8'))
        titles=[x['news_item']['title'] for x in data]
        self.assertTrue(any('教育部发布AI课程政策' in t for t in titles))
if __name__=='__main__':unittest.main()
