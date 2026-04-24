# 评测报告: deterministic_eval_20260425_045901

- **评测 ID**: eval_f58a602f
- **执行时间**: 2026-04-25 04:59:01.877947
- **任务数量**: 8

## 评测指标

| 指标 | 值 |
|------|------|
| 任务成功率 | 87.50% |
| 工具执行成功率 | 64.29% |
| 恢复率 | 80.00% |
| GUI 操作准确率 | 100.00% |
| 平均延迟 | 9 ms |

## 任务详情

### FIXTURE

| 任务 | 成功 | 步骤数 | 延迟 |
|------|------|--------|------|
| fixture_tool_use_success | ✓ | 1 | 12ms |
| fixture_wrong_args_repair | ✓ | 2 | 13ms |
| fixture_gui_grounding_click | ✓ | 1 | 3ms |
| fixture_wrong_tool_repair | ✓ | 2 | 11ms |
| fixture_invalid_format_repair | ✓ | 2 | 8ms |
| fixture_policy_violation_repair | ✓ | 2 | 4ms |
| fixture_gui_click_miss_repair | ✓ | 2 | 9ms |
| fixture_over_correction | ✗ | 2 | 10ms |

## 失败分析

- **fixture_over_correction**: over_correction
