# AEGIS-1（Agent Execution Governance & Integrity Standard）

中文名：**Agent 真执行治理标准 v1**  
版本：v1.0  
生效：2026-02-28  
适用范围：后续所有 Agent（不区分模型供应商/型号）

---

## 0. 设计目标

1. **可验证执行**：禁止“口头执行”；所有关键结论必须可追溯到工具调用证据。  
2. **模型可替换**：同一编排可在 Grok / Gemini / Qwen / Claude / GPT 等模型间替换。  
3. **稳定可恢复**：长任务可 checkpoint / 可恢复 / 可重试。  
4. **可审计运维**：有 trace、指标、失败码、告警与回放。

---

## 1. 架构分层（必须）

### L1. Controller（控制层）
- 负责：路由、状态机推进、重试、超时、并发配额。
- 禁止：让 LLM 直接决定“是否执行了工具”。

### L2. Executor（执行层）
- 负责：真正调用 tools（sessions_spawn / web_search / web_fetch / exec 等）。
- 要求：每次调用产出 `tool_call_id`、`run_id`、`start/end_ts`、`status`。

### L3. Verifier（校验层）
- 发送前硬校验：
  - 是否存在必需 tool_call
  - `requested_model == actual_model`
  - 输出声明与 trace 一致
  - 未配置模型名不得出现
- 不通过即失败返回（禁止降级伪成功）。

### L4. Reporter（输出层）
- 只能基于 Verifier 通过后的结构化证据生成用户可见结论。

---

## 2. 编排规范（必须）

1. **状态机/图编排**：任务以 `state -> action -> state` 运行，不走自由文本链式推理。  
2. **Fail-Fast**：关键 lane 失败直接 error，禁止静默 fallback（除非用户显式授权）。  
3. **幂等重试**：仅对可重试错误重试（429/超时）；重试次数与退避策略固定可见。  
4. **超时上限**：每步与总流程都必须有 timeout。  
5. **并发控制**：设 lane 并发上限，避免拥塞导致假超时。

---

## 3. 模型抽象规范（必须）

1. **模型声明三元组**：`lane_name / requested_model / actual_model`。  
2. **模型别名白名单**：只允许配置文件中的模型 ID 与别名。  
3. **未配置模型拦截**：输出出现未配置模型名，直接 `ERROR_UNCONFIGURED_MODEL_CLAIM`。  
4. **模型无关 Prompt**：Prompt 描述职责，不绑定具体供应商术语。

---

## 4. 输出可信规范（必须）

用户可见输出至少包含：
- `status`（success/error）
- `error_code`（失败时必填）
- `model_trace`（每 lane run_id）
- `model_lock`（requested vs actual）
- `lane_error`（逐 lane）
- `confidence`（证据一致性驱动，不可拍脑袋）

禁止项：
- “我让某模型执行了”但无 tool_call/run_id
- “据我搜索”但无外链或来源

---

## 5. 观测与审计规范（必须）

1. 每次任务落盘：query、path、latency、tool_count、error_code、models_used。  
2. 保留最近 N 天可回放日志（至少包含输入、状态迁移、工具调用摘要）。  
3. 建立最小 SLO：
   - 执行真实性通过率（trace-consistency）
   - 首次成功率
   - 平均延迟
   - 假执行拦截次数

---

## 6. 人工介入（HITL）规范（建议默认开启）

对以下场景强制人工确认：
- 破坏性操作
- 外发消息到公共群/外部渠道
- 高风险金融/安全建议

---

## 7. 发布门禁（必须）

上线前必须通过：
1. 合约测试（字段完整性、错误码、trace 一致性）  
2. 回归测试（正常/超时/429/上游失败）  
3. 影子流量验证（只观测不放量）  
4. 版本化变更（VERSION + CHANGELOG）

---

## 8. 统一错误码（基础集）

- `ERROR_MISSING_TOOL_CALL`
- `ERROR_MODEL_MISMATCH`
- `ERROR_UNCONFIGURED_MODEL_CLAIM`
- `ERROR_SCOUT_TIMEOUT`
- `ERROR_UPSTREAM_FETCH_FAILED`
- `ERROR_GUARDRAIL_REJECTED`

---

## 9. 后续执行原则

- 任何新 Agent 先落该蓝图，再写具体业务 Prompt。  
- 新模型接入先过“模型抽象规范 + 校验层”，再进生产。  
- 规则冲突时：**执行真实性 > 结果好看**。
