# RUNBOOK（收口版）

1. 维护 `data/raw/manual_inputs.json`
2. 运行 `python -m app.main scan`
3. 先看：
   - `outputs/briefs/writer_dashboard_*.md`
   - `outputs/briefs/briefs_*.md`
4. 周度：`python -m app.main weekly`
5. 选题后：`python -m app.main build "<url_or_text>"`
6. 检查 `data/usage_log.json` 是否记录 build/weekly 轨迹
