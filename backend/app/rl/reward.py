"""
强化学习奖励计算模块
"""

def calculate_step_reward(progress_score: float, grounding_score: float, alpha: float = 0.5, beta: float = 0.2) -> float:
    """
    计算基于 SPA-RL (Step-RL) 的即时步骤奖励
    
    Args:
        progress_score: 进度估算分 (通常 0.0 - 1.0)
        grounding_score: 动作有效性分 (如 1.0 为成功, 0.0 为无效, -0.5 为明显错误惩罚)
        alpha: 进度分的权重
        beta: Grounding 分的权重
        
    Returns:
        float: 融合后的步骤即时奖励
    """
    return alpha * progress_score + beta * grounding_score
