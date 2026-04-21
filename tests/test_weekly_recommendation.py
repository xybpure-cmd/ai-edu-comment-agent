import unittest
from pathlib import Path
from app.services import run_scan,run_weekly_review
class WeeklyRecommendationTests(unittest.TestCase):
    def test_weekly_contains_recommendation(self):
        run_scan(); p=run_weekly_review(); txt=Path(p).read_text(encoding='utf-8')
        self.assertIn('本周最建议下笔的一篇评论',txt)
        self.assertIn('建议标题',txt)
if __name__=='__main__':unittest.main()
