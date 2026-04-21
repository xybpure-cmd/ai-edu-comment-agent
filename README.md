# ai-edu-comment-agent

零外部依赖（Python 标准库）AI+教育评论助理。

## CLI（保持稳定）
- `python -m app.main scan`
- `python -m app.main evaluate "<url_or_text>"`
- `python -m app.main build "<url_or_text>"`
- `python -m app.main trigger "<keyword>"`
- `python -m app.main weekly`

## 输入
- fixtures：`tests/fixtures/scan_inputs.json`
- 手工真实来源：`data/raw/manual_inputs.json`
- 模板：`data/raw/manual_inputs.sample.json`

## 输出命名（统一）
- briefs：`outputs/briefs/briefs_<ts>.md`
- writer_dashboard：`outputs/briefs/writer_dashboard_<ts>.md`
- weekly：`outputs/briefs/weekly_<ts>.md`
- candidates：`outputs/json/candidates_<ts>.json`
- topic_cards：`outputs/json/topic_cards_<ts>.json`
- comment_pack：`outputs/json/comment_pack_<id>.json`（HOLD: `hold_comment_pack_<id>.json`）
- usage_log：`data/usage_log.json`

时间戳统一为：`YYYYMMDDTHHMMSSZ`

## 文档
- `docs/SPEC.md`
- `docs/RUNBOOK.md`
- `docs/USAGE_GUIDE.md`

## 测试
`python -m unittest discover -s tests -q`
