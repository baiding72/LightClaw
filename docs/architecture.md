# LightClaw 系统架构

## 概述

LightClaw 是一个面向个人效率管理的在线自进化轻量智能体系统。它参考了 OpenClaw-RL 和 Claw-R1 的设计思路，但采用了更轻量、更易于本地运行的实现方式。

## 系统层次

LightClaw 系统分为以下几个核心层：

### 1. Runtime 层

Agent Runtime 是系统的核心，实现了 MiniClaw 风格的轻量执行循环。

**核心组件**：
- **Agent**: 主循环控制器，协调 Planner、Executor、Observer 等组件
- **Planner**: 任务规划器，分析任务并决定下一步动作
- **Executor**: 工具执行器，调用具体工具并处理结果
- **Observer**: 执行观察器，总结状态变化并判断是否继续
- **RecoveryManager**: 恢复管理器，处理失败分析和修复策略
- **State**: 状态管理，跟踪任务执行的完整上下文

**执行循环**：
```
Plan → Act → Observe → Retry/Replan
```

### 2. Gateway/Logger 层

负责统一记录运行时信息，为后续数据分析和训练提供支持。

**记录内容**：
- 任务开始/结束事件
- 步骤开始/结束事件
- 工具调用和结果
- 错误和恢复信息
- GUI 动作和截图
- 性能指标（延迟、Token 使用）

### 3. DataPool 层

将原始日志整理成更高价值的数据对象。

**样本类型**：
- **success_trajectory**: 成功完成的轨迹
- **failure_trajectory**: 失败的轨迹
- **repair_trajectory**: 包含修复过程的轨迹
- **tool_use**: 工具使用样本
- **self_correction**: 自我纠正样本
- **gui_grounding**: GUI 定位样本

### 4. Evaluation 层

提供统一的评测框架，计算关键指标。

**评测指标**：
- task_success_rate: 任务成功率
- tool_execution_success_rate: 工具执行成功率
- recovery_rate: 恢复率
- gui_action_accuracy: GUI 操作准确率
- latency_ms: 延迟
- token_cost: Token 成本

## 为什么不是完整在线 RL

LightClaw 采用了轻量化的设计，而不是完整的在线强化学习框架，原因如下：

1. **本地可运行**: 完整的在线 RL 需要大量计算资源，LightClaw 设计为可以在个人电脑上运行

2. **快速迭代**: 轻量设计允许更快地测试和迭代，适合个人项目

3. **数据积累优先**: 当前阶段重点是积累高质量数据，为后续训练做准备

4. **接口预留**: 虽然不实现真正的在线 RL，但保留了数据导出接口，支持后续接入微调流程

## 为什么采用轻量增量训练接口

1. **低门槛**: 不需要复杂的 RL 基础设施

2. **灵活性**: 可以选择性地针对特定能力进行增强（如 tool-use、self-correction、GUI grounding）

3. **可扩展**: 后续可以逐步引入更复杂的训练方法

## 数据流

```
用户指令
    ↓
Agent Runtime
    ↓
Tool Execution
    ↓
Gateway Logger
    ↓
Trajectory Storage
    ↓
DataPool Builder
    ↓
Sample Export
    ↓
Fine-tuning (后续)
```

## 技术选型

- **后端**: Python 3.11 + FastAPI + SQLAlchemy
- **前端**: React + TypeScript + Tailwind CSS
- **浏览器自动化**: Playwright
- **LLM**: OpenAI-compatible API (可接入 GLM、DeepSeek 等)
- **数据存储**: SQLite + JSONL

## 扩展点

系统预留了以下扩展点：

1. **LLM Adapter**: 可以添加新的 LLM 提供商
2. **Tool Registry**: 可以注册新的工具
3. **Memory System**: 可以扩展更复杂的记忆机制
4. **Evaluation Framework**: 可以添加新的评测指标
5. **Training Pipeline**: 可以接入实际的微调流程
