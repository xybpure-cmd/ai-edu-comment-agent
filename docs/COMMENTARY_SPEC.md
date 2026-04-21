# COMMENTARY_SPEC

## 目标
将输出从“评论建议”升级为“评论底稿”，确保作者拿到的是可直接改写的成文材料，而不是仅有方向性提示。

## CommentPack 数据结构（核心字段）
- `status`: `READY | HOLD`
- `hold_reason`: HOLD 原因
- `education_core_question`: 教育核心问题
- `main_judgement`: 主判断句
- `supporting_argument_1`: 支撑论点一
- `supporting_argument_2`: 支撑论点二
- `counterargument`: 可能反方意见
- `full_draft`: 连续正文（六段式）
- `draft_quality_level`: `READY | HOLD`
- `primary_title` / `alternative_titles`
- `suggested_opening_paragraph` / `ending_suggestion`

## build 输出模板（作者可直接使用）
build 输出采用“作者底稿层 + 内部分析层”组合：

1. 作者底稿层
   - 主标题与备选标题
   - 建议开头段
   - 六段式评论正文初稿（连续文本）
   - 核心论点列表
   - 可能反方意见
   - 结尾收束建议

2. 内部分析层
   - 新闻基本信息
   - 一句话摘要
   - 已核实事实 / 待核实信息
   - 教育核心问题 / 主判断句 / 两个支撑论点 / 一个反方意见
   - 状态（含 `status`、`draft_quality_level`、`hold_reason`）
   - 评论策划（核心问题、角度、受众、张力）

## READY/HOLD 判定规则
只有同时满足以下条件，`status` 与 `draft_quality_level` 才能判定为 `READY`：
1. 候选具备进入正式评论包资格（`candidate_ok = true`）
2. 已核实事实数量至少 3 条
3. 存在教育核心问题（`education_core_question`）
4. 存在主判断句（`main_judgement`）
5. 存在两个支撑论点（`supporting_argument_1`、`supporting_argument_2`）
6. 存在连续正文（六段式结构）

若任一条件不满足，判定 `HOLD`，并给出 `hold_reason`。

## 推荐策略
- `writer_dashboard`：优先推荐 `READY` 候选；同状态下按优先级排序。
- `weekly`：优先从 `READY` 候选中选择“本周最建议下笔的一篇评论”；同状态下按优先级排序。

## 落地约束
- 不以“是否有观点建议”作为完成标准，而以“是否形成可改写底稿”作为完成标准。
- 新字段与输出模板必须保持一致，避免结构定义与文件输出脱节。
