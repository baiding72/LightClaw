"""
进度估算器模块 (Progress Estimator)

该模块负责基于 AgentState 和当前动作评估每步的进度贡献值。
在生产环境中，该模块可替换为基于 Qwen3-8B+MLP 的实际推理服务。
这里提供一个基于规划步骤完成情况的启发式实现。
"""
from typing import Any, Optional
from app.runtime.state import AgentState

class ProgressEstimator:
    """
    进度估算器，负责将最终延迟奖励拆分为每步进度分 (progress_score)
    """
    
    def __init__(self, mode: str = "heuristic"):
        """
        初始化
        Args:
            mode: 估算模式 (heuristic 启发式, llm 大模型, external 外部接口)
        """
        self.mode = mode

    async def estimate(self, state: AgentState) -> float:
        """
        估算当前步骤的进度分数
        
        Args:
            state: 当前 Agent 状态
            
        Returns:
            float: 进度分
        """
        if self.mode == "heuristic":
            return self._heuristic_estimate(state)
        
        # 默认返回一个基础推进奖励
        return 0.1

    def _heuristic_estimate(self, state: AgentState) -> float:
        """基于当前完成状态的简单启发式进度估算"""
        if not state.plan_steps:
            return 0.1
            
        total_steps = max(len(state.plan_steps), 1)
            
        # 如果没有工具调用历史
        if not state.tool_calls:
            return 0.0
            
        last_call = state.tool_calls[-1]
        
        # 如果产生了错误，不推进进度
        if last_call.get("error"):
            return 0.0
            
        # 基础每步分配的进度分
        base_progress = 1.0 / total_steps
        
        tool = last_call.get("tool")
        if tool in ["click", "type_text", "select_option"]:
            # 涉及 UI 成功交互，赋予较高权重
            return min(base_progress * 1.2, 1.0)
            
        return base_progress
