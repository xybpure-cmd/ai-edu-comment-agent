# SPEC（收口版）

## 核心目标
- 标准库实现
- 本地输入（fixtures + manual inputs）
- 稳定输出（briefs/candidates/topic_cards/comment_pack/weekly/usage_log）
- 作者可直接改写

## 固定 CLI
- scan / evaluate / build / trigger / weekly

## 命名规范
- 时间戳：`YYYYMMDDTHHMMSSZ`
- briefs：`outputs/briefs/briefs_<ts>.md`
- writer_dashboard：`outputs/briefs/writer_dashboard_<ts>.md`
- weekly：`outputs/briefs/weekly_<ts>.md`
- candidates：`outputs/json/candidates_<ts>.json`
- topic_cards：`outputs/json/topic_cards_<ts>.json`
- comment_pack：`outputs/json/comment_pack_<id>.json`（HOLD 为 `hold_comment_pack_<id>.json`）
- usage_log：`data/usage_log.json`
