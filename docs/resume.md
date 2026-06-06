# agent研发

## 基本信息

### 黄志坤

LLM/Agent

- 邮箱: 486534919@qq.com
- 电话: 18064558369

## 教育经历

### 厦门大学 | 电子信息

_硕士研究生 | 2024/09 - 2027/06_

### 华中科技大学 | 自动化

_本科 | 2019/09 - 2023/06_

- 主修课程：数据结构与算法、计算机视觉、模式识别与机器学习、生成式人工智能，专业排名前 30%

- 担任机器人团队视觉组组长

## 项目经历

### LightClaw：透明可控的 Agent Harness / Agent Runtime

_开发者 | 2026/01 - 2026/03_

- **Agent Runtime 与 ReAct Harness 搭建：** 面向工具调用、记忆读写、文件生成、定时任务和前端可观测等真实 Agent 场景，设计原生 ReAct loop，支持多轮 tool call、observation 回灌、max turn 兜底、流式响应和 session/trace 持久化；将模型输入、工具决策、权限结果、工具返回和最终回复全部写入 JSONL 轨迹

- **记忆系统与上下文压缩：** 构建短期 session、长期 user profile、项目 note 和自动 summary 的分层记忆体系，围绕 memory scope、create/update 语义、跨会话注入和 token 预算做约束；通过 checkpointer、turn-level trimming、summary 注入解决长对话遗忘、上下文爆炸和临时信息污染长期画像的问题

- **工具权限、沙盒与 Source Routing：** 实现 ToolGatePolicy，在工具真正执行前按资源类型、作用域、风险等级和运行模式给出 allow / ask / deny 决策；对文件、Shell、Office 生成、web/search、memory 写入等工具做参数校验、路径沙盒、危险命令拦截和人工确认，避免仅依赖 system prompt 约束模型

- **Skill 懒加载、两阶段调用与评测闭环：** 实现 skill registry 懒加载和渐进式披露，启动时只扫描技能元信息，需要时再读取完整 SKILL.md，并通过 help → run 两阶段调用降低工具误用风险；将上下文误判、记忆未落盘、错误联网、工具误用等 badcase 固化为 agent 级 eval，支持新会话自动执行并在 Mac 客户端展示评测 trace

## 比赛经历

### MM-CustomerAgent：多模态客服智能体

_第二十一届中国研究生电子设计竞赛 | 2026/03 - 2026/06_

面向电商客服图文混合问答场景，设计并迭代融合文本检索、视觉检索与多图上下文生成的多模态客服系统，统一处理商品参数查询、活动规则理解、尺码表解读与用户截图问答等问题。

- **检索前优化**：围绕客服问题中“文本规则 / 图片理解 / 图文混合”三类模式，设计实体抽取 + 问题分类 + 模态路由流程，先识别商品、活动、页面报错等关键约束，再动态选择文本检索、视觉检索或双路召回路径，降低纯文本链路对海报、截图、表格类问题的误召回

- **检索中优化**：采用 **BGE 主体文本 embedding + 视觉 embedding** 的双索引方案，分别覆盖 FAQ/规则/参数/OCR 文本与商品图/海报/尺码表/用户截图等视觉知识；针对图文证据分散、单一路径召回不稳定的问题，设计多路召回 + 跨模态融合策略，并对 top-N 候选做轻量 rerank 去噪

- **返回后优化**：在生成侧构建多图上下文组织模块，对召回图片生成 caption、OCR 摘要与 metadata 标签，并与文本证据联合排序；根据问题类型选择 text-only 或 vision-grounded 回答链路，提升图文联合问答、多图对比解释与截图报错定位场景下的回答稳定性

- **评测与迭代**：围绕图文问答 benchmark 建立 Recall@K、图像证据命中率、答案正确率、引用一致性与多图任务完成率等指标，对文本索引、视觉索引、双路融合与 rerank 策略进行消融，为后续场景扩展和模型替换提供评测基础

## 工作经验

### 中国电器科学研究院 | 软件研发工程师

_2023/07 - 2024/06_

- 焓差实验室上位机调试软件开发，负责界面迭代、交互优化、业务逻辑修复及现场调试支持

## 专业技能

- 掌握 Transformer 与 LLM 基本原理

- 掌握 RAG 与 Agent 基本概念，熟悉 Query Rewrite、Chunking、Dense/BM25 Hybrid Retrieval、Reranker、Tool Use、Memory、Planning、Self-Correction 等核心模块

- 熟悉 LoRA/QLoRA 等轻量微调方法，了解 SFT、DPO、GRPO 等 post-training 流程

- 熟悉 Codex、Claude Code、Antigravity 等 AI Coding 工具在项目搭建、调试排错与工程重构中的应用