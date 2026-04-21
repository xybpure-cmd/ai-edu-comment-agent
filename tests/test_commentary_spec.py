import unittest
from pathlib import Path

from app.services import build_comment_pack, build_news_item, evaluate_candidate, export_outputs


class CommentarySpecTests(unittest.TestCase):
    def test_build_outputs_layered_draft_and_required_fields(self):
        n = build_news_item('https://www.moe.gov.cn/special/ai-policy')
        c = evaluate_candidate(n)
        p = build_comment_pack(n, c)

        self.assertGreaterEqual(len(p.verified_facts), 3)
        self.assertTrue(p.education_core_question)
        self.assertTrue(p.main_judgement)
        self.assertTrue(p.supporting_argument_1)
        self.assertTrue(p.supporting_argument_2)
        self.assertTrue(p.counterargument)
        self.assertEqual(p.draft_quality_level, 'READY')

        draft = p.full_draft
        self.assertGreaterEqual(len(draft), 900)
        self.assertLessEqual(len(draft), 1400)
        paras = [x for x in draft.split('\n\n') if x.strip()]
        self.assertEqual(len(paras), 6)
        self.assertGreaterEqual(len(paras[3]), 120)
        self.assertGreaterEqual(len(paras[4]), 120)
        self.assertNotIn('待补充摘要', draft)

        export_outputs(p)
        md = Path('outputs/markdown/comment_pack_48eccbf0dbc9.md').read_text(encoding='utf-8')
        self.assertIn('# 作者底稿层', md)
        self.assertIn('# 内部分析层', md)
        self.assertIn('六段式评论正文初稿（长评 900-1400 字）', md)

        author_layer = md.split('---')[0]
        self.assertNotIn('具备评论价值', author_layer)
        self.assertNotIn('建议先形成结构化短评再扩写', author_layer)
        self.assertNotIn('可从以下角度分析', author_layer)


if __name__ == '__main__':
    unittest.main()
