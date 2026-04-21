import unittest
from pathlib import Path

from app.services import build_comment_pack, build_news_item, evaluate_candidate, export_outputs


class CommentarySpecTests(unittest.TestCase):
    def test_build_outputs_layered_draft_and_required_fields(self):
        n = build_news_item({
            'url': 'https://www.moe.gov.cn/special/ai-policy',
            'title': '教育部发布AI课程政策',
            'summary': '强调课程规范与教师能力建设。',
        })
        c = evaluate_candidate(n)
        p = build_comment_pack(n, c)
        self.assertGreaterEqual(len(p.verified_facts), 3)
        self.assertTrue(p.education_core_question)
        self.assertTrue(p.main_judgement)
        self.assertTrue(p.supporting_argument_1)
        self.assertTrue(p.supporting_argument_2)
        self.assertTrue(p.counterargument)
        self.assertEqual(p.draft_quality_level, 'READY')

        export_outputs(p)
        md = Path('outputs/markdown/comment_pack_48eccbf0dbc9.md').read_text(encoding='utf-8')
        self.assertIn('# 作者底稿层', md)
        self.assertIn('# 内部分析层', md)
        self.assertIn('六段式评论正文初稿', md)

        author_layer = md.split('---')[0]
        self.assertNotIn('具备评论价值', author_layer)
        self.assertNotIn('建议先形成结构化短评再扩写', author_layer)
        self.assertNotIn('可从以下角度分析', author_layer)


if __name__ == '__main__':
    unittest.main()
