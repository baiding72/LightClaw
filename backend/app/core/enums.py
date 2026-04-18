"""
LightClaw 枚举定义
"""
from enum import Enum


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"
    PLANNING = "planning"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskDifficulty(str, Enum):
    """任务难度"""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class TaskCategory(str, Enum):
    """任务类别"""
    INFO_EXTRACTION = "info_extraction"      # 信息整理类
    TODO_CALENDAR = "todo_calendar"           # 待办/日程管理类
    WEB_FORM = "web_form"                     # 网页表单交互类
    MULTI_STEP = "multi_step"                 # 跨工具多步任务类


class StepStatus(str, Enum):
    """步骤状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class FailureType(str, Enum):
    """
    失败类型枚举

    失败类型分类：
    - wrong_tool: 选择了错误的工具
    - wrong_args: 工具参数错误
    - tool_runtime_error: 工具运行时错误
    - gui_click_miss: GUI 点击未命中目标
    - gui_wrong_element: GUI 操作了错误元素
    - gui_state_stale: GUI 状态过期（页面已变化）
    - state_loss_after_navigation: 页面跳转后状态丢失
    - planning_error: 规划错误
    - observation_error: 观察错误
    - repair_success: 修复成功
    - repair_failed: 修复失败
    """
    WRONG_TOOL = "wrong_tool"
    WRONG_ARGS = "wrong_args"
    TOOL_RUNTIME_ERROR = "tool_runtime_error"
    GUI_CLICK_MISS = "gui_click_miss"
    GUI_WRONG_ELEMENT = "gui_wrong_element"
    GUI_STATE_STALE = "gui_state_stale"
    STATE_LOSS_AFTER_NAVIGATION = "state_loss_after_navigation"
    PLANNING_ERROR = "planning_error"
    OBSERVATION_ERROR = "observation_error"
    REPAIR_SUCCESS = "repair_success"
    REPAIR_FAILED = "repair_failed"

    @classmethod
    def is_gui_failure(cls, failure_type: "FailureType") -> bool:
        """判断是否为 GUI 相关失败"""
        return failure_type in [
            cls.GUI_CLICK_MISS,
            cls.GUI_WRONG_ELEMENT,
            cls.GUI_STATE_STALE,
            cls.STATE_LOSS_AFTER_NAVIGATION,
        ]

    @classmethod
    def is_recoverable(cls, failure_type: "FailureType") -> bool:
        """判断是否可恢复"""
        return failure_type in [
            cls.WRONG_TOOL,
            cls.WRONG_ARGS,
            cls.TOOL_RUNTIME_ERROR,
            cls.GUI_CLICK_MISS,
            cls.GUI_STATE_STALE,
        ]


class TrajectoryType(str, Enum):
    """轨迹类型"""
    SUCCESS = "success_trajectory"
    FAILURE = "failure_trajectory"
    REPAIR = "repair_trajectory"


class SampleType(str, Enum):
    """样本类型"""
    TOOL_USE = "tool_use"
    SELF_CORRECTION = "self_correction"
    GUI_GROUNDING = "gui_grounding"


class MemoryType(str, Enum):
    """记忆类型"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"


class ActionType(str, Enum):
    """GUI 动作类型"""
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    SCROLL = "scroll"
    NAVIGATE = "navigate"
    SCREENSHOT = "screenshot"
