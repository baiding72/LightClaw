"""
GUI 模式内置任务模板
"""
from app.core.enums import TaskCategory, TaskDifficulty
from app.schemas.task import TaskDefinition


GUI_AGENT_TASKS = [
    TaskDefinition(
        task_id="gui_job_001",
        instruction="查看当前招聘网站的投递记录页面，识别岗位名称、投递状态和投递时间，并在完成后告诉我结果。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["click", "type_text", "select_option", "scroll", "take_screenshot"],
        target_state={"gui_task": True},
        validation_rules={},
        description="在当前招聘网站页面中读取并整理投递记录",
        tags=["gui", "job-application", "delivery-record"],
    ),
    TaskDefinition(
        task_id="gui_job_002",
        instruction="在当前招聘官网页面中继续填写表单，必要时滚动、点击下一步，并在提交前停下。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.HARD,
        allowed_tools=["click", "type_text", "select_option", "scroll", "take_screenshot"],
        target_state={"gui_task": True},
        validation_rules={},
        description="在当前官网页面中推进求职表单",
        tags=["gui", "job-application", "form"],
    ),
    TaskDefinition(
        task_id="gui_generic_001",
        instruction="在当前网页中找到与任务最相关的按钮或输入框，逐步执行并在完成时给出简短总结。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["click", "type_text", "select_option", "scroll", "take_screenshot"],
        target_state={"gui_task": True},
        validation_rules={},
        description="通用 GUI 交互模板",
        tags=["gui", "generic"],
    ),
]


ALL_TASKS = GUI_AGENT_TASKS


def get_task_by_id(task_id: str) -> TaskDefinition | None:
    """根据 ID 获取任务"""
    for task in ALL_TASKS:
        if task.task_id == task_id:
            return task
    return None


def get_tasks_by_category(category: TaskCategory) -> list[TaskDefinition]:
    """按类别获取任务"""
    return [t for t in ALL_TASKS if t.category == category]


def get_tasks_by_difficulty(difficulty: TaskDifficulty) -> list[TaskDefinition]:
    """按难度获取任务"""
    return [t for t in ALL_TASKS if t.difficulty == difficulty]


def get_all_task_ids() -> list[str]:
    """获取所有任务 ID"""
    return [t.task_id for t in ALL_TASKS]


def get_gui_tasks() -> list[TaskDefinition]:
    """获取 GUI 模式任务模板"""
    return GUI_AGENT_TASKS
