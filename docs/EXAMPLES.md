# AEGIS-1 示例代码与 Schema

## 1) 最小 Orchestrator 示例

文件：`examples/minimal_orchestrator.py`

功能：
- Controller 驱动状态机执行（`grok_scout -> gemini_scout -> qwen_scout -> grok_fusion`）
- Fail-Fast
- 产出标准 artifacts：
  - `tool_summary.json`
  - `output.json`
- 执行内置 verifier（模型锁、证据完整性、未配置模型名拦截）

运行：

```bash
cd /home/jiumu/.openclaw/workspace/aegis
python3 examples/minimal_orchestrator.py --query "现在BTC舆情如何"
```

模拟失败：

```bash
python3 examples/minimal_orchestrator.py --query "test" --fail-lane gemini_scout
```

## 2) Schema

- `schema/tool_summary.schema.json`
- `schema/output.schema.json`

说明：
- `tool_summary` 描述每个 lane 的真实执行证据（tool_call_id/run_id/requested_model/actual_model/status/error_code）。
- `output` 约束用户可见标准字段（status/error_code/model_trace/model_lock/lane_error/confidence/source_mix/conflict_points）。

## 3) Mermaid 图

文件：`docs/diagrams/fast_path.mmd`

可在支持 Mermaid 的 Markdown 渲染器中查看。
