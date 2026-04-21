import json,unittest
from pathlib import Path
from app.services import run_scan,run_weekly_review,build_news_item,evaluate_candidate,build_comment_pack,export_outputs
class UsageLogTests(unittest.TestCase):
    def test_usage_log_records_build_and_weekly(self):
        run_scan(); n=build_news_item('https://www.moe.gov.cn/policy'); c=evaluate_candidate(n); export_outputs(build_comment_pack(n,c)); run_weekly_review()
        p=Path('data/usage_log.json'); self.assertTrue(p.exists())
        events=json.loads(p.read_text(encoding='utf-8'))['events']
        self.assertTrue(any(e['event']=='build' for e in events))
        self.assertTrue(any(e['event']=='weekly' for e in events))
if __name__=='__main__':unittest.main()
