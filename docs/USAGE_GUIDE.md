# USAGE GUIDE

## 作者日常怎么用
- 每天补充 `data/raw/manual_inputs.json`
- 跑 `scan`，先看 writer dashboard 再看 briefs
- 从 top3 里选题后运行 `build`

## 每三天一次工作流
1. 批量补充 manual inputs
2. `python -m app.main scan`
3. 检查 `candidates` 与 `topic_cards`
4. 选择 1-2 条进入 build

## weekly 怎么看
- 运行 `python -m app.main weekly`
- 重点看“本周最建议下笔的一篇评论”
- 复核推荐理由、建议标题、建议结构

## build 生成后怎么改写
- 先改主标题和开头段
- 保留核心论点，补充你自己的证据
- 参考反方意见，增强论证韧性
- 用“结尾收束建议”形成最终落点

## 哪些输出优先看
1. `writer_dashboard_*.md`
2. `weekly_*.md`
3. `briefs_*.md`
4. `comment_pack_*.md`
