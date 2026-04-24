# Failure Taxonomy

LightClaw 的失败类型用于 runtime logging、self-correction、reward 和 DPO 数据构造。

## Tool-use

- `wrong_tool`：选择了不存在或不适合当前任务的工具。
- `invalid_format`：工具参数不是合法 JSON object，例如非法 JSON 字符串、数组、null。
- `wrong_args`：参数对象合法，但缺字段、类型错误、enum 错误或业务校验失败。
- `tool_runtime_error`：工具执行时抛异常、超时或外部依赖不可用。
- `tool_timeout`：工具执行超过 runtime timeout。
- `tool_exception`：未分类工具异常。
- `policy_violation`：违反运行时策略，例如没有目标标签页时仍尝试 GUI 操作。
- `redundant_tool_call`：重复执行无收益工具调用，可作为 reward penalty。
- `hallucinated_observation`：在没有 observation/evidence 的情况下生成结论。
- `over_correction`：原 action 已正确，但 revision 错误地改变了 tool、arguments 或 action type。

## GUI Grounding

- `gui_click_miss`：点击点或 selector 未命中目标。
- `gui_wrong_element`：命中元素但语义错误。
- `gui_state_stale`：页面刷新、弹窗或 DOM 变化导致旧目标失效。
- `state_loss_after_navigation`：导航后上下文丢失。

## Planning / Observation

- `planning_error`：任务分解或工具顺序错误。
- `observation_error`：误读工具返回、页面内容或 verifier feedback。

## Recovery

- `repair_success`：失败后基于 error/observation 修正并成功。
- `repair_failed`：尝试修正但仍失败。

## DPO Pair 构造规则

- rejected：失败 action，例如 `wrong_args`、`invalid_format`、`gui_click_miss`。
- chosen：紧随其后的成功修正 action。
- 如果原 action 已被 verifier 判断正确，不生成 over-correction pair。

## Over-correction

过度修正是 self-correction 中的关键负样本：系统需要学会在 action 已正确时保持不变，而不是机械地产生 revision。LightClaw 在 deterministic fixtures 中保留了一个 over-correction case，用于测试 `over_correction_rate` 和训练数据质量检查。
