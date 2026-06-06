# myClaw 测试迁移记录

## 2026-05-21

这轮目标是把 CyberClaw `tests/` 里能迁移到 myClaw 当前阶段的测试先搬过来，尤其是 `test_two_phase_skills.py` 这类能帮助理解 harness 机制的测试。

### 执行命令

```bash
PYTHONPATH=/Users/baiding/CyberClaw pytest -q myClaw/tests
```

### 执行结果

```text
80 passed in 63.18s (0:01:03)
```

### 本轮新增/迁移的测试

- `myClaw/tests/test_config_and_skill_loader.py`
  - 检查 myClaw 的配置路径是否稳定存在。
  - 检查 skill loader 的入口函数是否能正常导入。
  - 检查空 skill 目录不会导致加载失败。

- `myClaw/tests/test_context_advanced.py`
  - 检查短期上下文裁剪在小上下文下不会误删。
  - 检查长上下文会保留最近 turn，丢弃过旧内容。
  - 检查 tool 消息也会随上下文窗口一起裁剪。
  - 检查 turn 计数逻辑是否只按用户输入来算。

- `myClaw/tests/test_builtins_migrated.py`
  - 检查内置工具的基础行为，包括时间、计算器、系统信息。
  - 检查用户画像 profile 的保存和更新。
  - 检查任务工具的创建、读取、更新、删除。
  - 检查非法任务时间会被拒绝。

- `myClaw/tests/test_two_phase_skills.py`
  - 迁移 CyberClaw 两阶段 skill 测试的核心思路。
  - 单阶段工具暴露时，模型容易直接踩到陷阱工具。
  - 两阶段工具暴露时，模型先读 help，再执行 run，更容易避开陷阱。
  - 当前测试是确定性 harness 测试，不依赖真实 LLM 随机输出。

- `myClaw/tests/test_lazy_loader_migrated.py`
  - 迁移 CyberClaw lazy loader 测试的核心思路。
  - 检查启动时只扫描 skill 名字和简介。
  - 检查真正调用 `mode='help'` 时才读取完整 `SKILL.md`。
  - 检查新增 skill 后可以强制重扫。
  - 这个测试对应的功能已经先迁移到 `myClaw/core/skill_loader.py`，不是只迁移测试。

- `myClaw/tests/test_sandbox_tools_migrated.py`
  - 迁移 CyberClaw sandbox tools 测试的核心思路。
  - 检查文件工具只能在 office sandbox 内读写。
  - 检查 `write_office_file` 只负责首次创建，`update_office_file` 只负责更新已有文件。
  - 检查 shell 工具会锁在 office sandbox 里执行，并拒绝明显越界命令。

### 当前覆盖到的机制

- agent loop 基础调用链。
- tool 注册、执行、错误处理。
- tool gate 权限决策。
- memory routing 和上下文裁剪。
- skill loader。
- lazy skill loader。
- 两阶段 skill。
- heartbeat。
- trace/logger。
- 文件工具。
- 约束文档里的基础策略。

### 备注

这轮迁移没有直接照搬 CyberClaw 的真实 LLM 行为评测，而是先把其中可确定、可回归的 harness 行为固化下来。这样做的好处是测试稳定，适合 myClaw 当前“边学边搭”的阶段；后续再逐步补真实模型评测、长任务评测和 badcase 回放。
