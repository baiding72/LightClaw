"""
内置任务定义

包含 20+ 个覆盖不同类别的任务
"""
from app.core.enums import TaskCategory, TaskDifficulty
from app.schemas.task import TaskDefinition


# =============================================================================
# A. 信息整理类任务
# =============================================================================

INFO_EXTRACTION_TASKS = [
    TaskDefinition(
        task_id="info_001",
        instruction="从网页中提取会议信息，包括时间、地点和参会要求，然后写入笔记。",
        category=TaskCategory.INFO_EXTRACTION,
        difficulty=TaskDifficulty.EASY,
        allowed_tools=["open_url", "read_page", "create_apple_note"],
        target_state={
            "note_created": True,
            "note_contains_time": True,
            "note_contains_location": True,
        },
        validation_rules={
            "check_note_exists": True,
            "check_keywords": ["时间", "地点"],
        },
        description="从网页提取会议信息并创建笔记",
        tags=["extraction", "note"],
    ),
    TaskDefinition(
        task_id="info_002",
        instruction="打开指定的招聘页面，提取职位名称、公司名称和薪资范围，生成总结。",
        category=TaskCategory.INFO_EXTRACTION,
        difficulty=TaskDifficulty.EASY,
        allowed_tools=["open_url", "read_page", "create_apple_note"],
        target_state={
            "note_created": True,
            "note_contains_job_title": True,
            "note_contains_company": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="提取招聘信息并总结",
        tags=["extraction", "job"],
    ),
    TaskDefinition(
        task_id="info_003",
        instruction="读取本地文件中的待办列表，提取所有任务和截止日期。",
        category=TaskCategory.INFO_EXTRACTION,
        difficulty=TaskDifficulty.EASY,
        allowed_tools=["read_file", "create_apple_note"],
        target_state={
            "note_created": True,
            "note_contains_tasks": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="从本地文件提取待办列表",
        tags=["extraction", "file"],
    ),
    TaskDefinition(
        task_id="info_004",
        instruction="搜索关于人工智能最新发展的信息，整理成笔记。",
        category=TaskCategory.INFO_EXTRACTION,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["search_web", "open_url", "read_page", "create_apple_note"],
        target_state={
            "note_created": True,
            "note_has_content": True,
        },
        validation_rules={
            "check_note_exists": True,
            "min_note_length": 100,
        },
        description="搜索并整理 AI 发展信息",
        tags=["search", "extraction", "note"],
    ),
    TaskDefinition(
        task_id="info_005",
        instruction="从多个网页中收集产品价格信息，创建对比笔记。",
        category=TaskCategory.INFO_EXTRACTION,
        difficulty=TaskDifficulty.HARD,
        allowed_tools=["search_web", "open_url", "read_page", "create_apple_note"],
        target_state={
            "note_created": True,
            "multiple_sources": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="收集产品价格并对比",
        tags=["search", "extraction", "comparison"],
    ),
]


# =============================================================================
# B. 待办/日程管理类任务
# =============================================================================

TODO_CALENDAR_TASKS = [
    TaskDefinition(
        task_id="todo_001",
        instruction="创建一个待办事项：完成项目报告，截止日期为下周五，优先级为高。",
        category=TaskCategory.TODO_CALENDAR,
        difficulty=TaskDifficulty.EASY,
        allowed_tools=["create_apple_reminder"],
        target_state={
            "todo_created": True,
            "title_contains": "项目报告",
            "priority": "high",
        },
        validation_rules={
            "check_todo_exists": True,
            "check_priority": "high",
        },
        description="创建简单待办事项",
        tags=["todo", "simple"],
    ),
    TaskDefinition(
        task_id="todo_002",
        instruction="创建一个日历事件：团队会议，明天下午2点到3点，地点在会议室A。",
        category=TaskCategory.TODO_CALENDAR,
        difficulty=TaskDifficulty.EASY,
        allowed_tools=["add_calendar_event"],
        target_state={
            "event_created": True,
            "title_contains": "团队会议",
            "location": "会议室A",
        },
        validation_rules={
            "check_event_exists": True,
        },
        description="创建日历事件",
        tags=["calendar", "simple"],
    ),
    TaskDefinition(
        task_id="todo_003",
        instruction="创建三个待办事项：1. 准备会议材料（明天截止，高优先级）2. 发送周报（周五截止，中优先级）3. 回复邮件（今天截止，低优先级）。",
        category=TaskCategory.TODO_CALENDAR,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["create_apple_reminder"],
        target_state={
            "todos_created": 3,
        },
        validation_rules={
            "check_todo_count": 3,
        },
        description="创建多个待办事项",
        tags=["todo", "batch"],
    ),
    TaskDefinition(
        task_id="todo_004",
        instruction="创建一个重复事件：每周一的部门例会，时间9:00-10:00，地点在线会议室。",
        category=TaskCategory.TODO_CALENDAR,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["add_calendar_event"],
        target_state={
            "event_created": True,
            "title_contains": "部门例会",
        },
        validation_rules={
            "check_event_exists": True,
        },
        description="创建重复日历事件",
        tags=["calendar", "recurring"],
    ),
    TaskDefinition(
        task_id="todo_005",
        instruction="根据网页上的会议信息，创建对应的日历事件和待办提醒。",
        category=TaskCategory.TODO_CALENDAR,
        difficulty=TaskDifficulty.HARD,
        allowed_tools=["open_url", "read_page", "add_calendar_event", "create_apple_reminder"],
        target_state={
            "event_created": True,
            "todo_created": True,
        },
        validation_rules={
            "check_event_exists": True,
            "check_todo_exists": True,
        },
        description="从网页创建日程和待办",
        tags=["extraction", "calendar", "todo"],
    ),
]


# =============================================================================
# C. 网页表单交互类任务
# =============================================================================

WEB_FORM_TASKS = [
    TaskDefinition(
        task_id="form_001",
        instruction="在本地表单页面中填写姓名、邮箱和电话号码，然后提交。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.EASY,
        allowed_tools=["open_url", "type_text", "click"],
        target_state={
            "form_submitted": True,
        },
        validation_rules={
            "check_form_submission": True,
        },
        description="填写简单表单",
        tags=["form", "simple"],
    ),
    TaskDefinition(
        task_id="form_002",
        instruction="在注册页面填写用户名、密码、确认密码、邮箱，选择性别，然后点击注册按钮。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["open_url", "type_text", "click", "select_option"],
        target_state={
            "form_submitted": True,
        },
        validation_rules={
            "check_form_submission": True,
        },
        description="填写注册表单",
        tags=["form", "registration"],
    ),
    TaskDefinition(
        task_id="form_003",
        instruction="在产品搜索页面，输入搜索关键词，选择价格区间，点击搜索，然后截取结果页面。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["open_url", "type_text", "click", "select_option", "take_screenshot"],
        target_state={
            "search_performed": True,
            "screenshot_taken": True,
        },
        validation_rules={
            "check_screenshot_exists": True,
        },
        description="搜索产品并截图",
        tags=["form", "search", "screenshot"],
    ),
    TaskDefinition(
        task_id="form_004",
        instruction="在设置页面修改个人信息，包括姓名、电话、地址，然后保存。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["open_url", "type_text", "click", "read_page"],
        target_state={
            "form_saved": True,
        },
        validation_rules={
            "check_save_success": True,
        },
        description="修改个人信息",
        tags=["form", "settings"],
    ),
    TaskDefinition(
        task_id="form_005",
        instruction="在多步骤表单中完成三个步骤：填写基本信息、选择选项、确认提交。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.HARD,
        allowed_tools=["open_url", "type_text", "click", "select_option", "take_screenshot"],
        target_state={
            "multi_step_completed": True,
        },
        validation_rules={
            "check_final_submission": True,
        },
        description="完成多步骤表单",
        tags=["form", "multi-step"],
    ),
]


# =============================================================================
# D. 跨工具多步任务类
# =============================================================================

MULTI_STEP_TASKS = [
    TaskDefinition(
        task_id="multi_001",
        instruction="搜索一个活动页面，提取时间地点，创建日历事件，再写一条提醒笔记。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["search_web", "open_url", "read_page", "add_calendar_event", "create_apple_note"],
        target_state={
            "event_created": True,
            "note_created": True,
        },
        validation_rules={
            "check_event_exists": True,
            "check_note_exists": True,
        },
        description="搜索活动并创建日程和笔记",
        tags=["search", "calendar", "note", "multi-tool"],
    ),
    TaskDefinition(
        task_id="multi_002",
        instruction="读取本地 markdown 文件中的待办列表，将每个待办导入系统。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["read_file", "create_apple_reminder"],
        target_state={
            "todos_created": True,
        },
        validation_rules={
            "check_todo_count_min": 1,
        },
        description="从文件导入待办",
        tags=["file", "todo", "import"],
    ),
    TaskDefinition(
        task_id="multi_003",
        instruction="打开网页表单，填写搜索条件，获取结果，将结果写入笔记。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["open_url", "type_text", "click", "read_page", "create_apple_note"],
        target_state={
            "note_created": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="表单操作并记录结果",
        tags=["form", "note", "multi-tool"],
    ),
    TaskDefinition(
        task_id="multi_004",
        instruction='计算 15 * 8 + 32，然后将结果写入笔记，标题为"计算结果"。',
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.EASY,
        allowed_tools=["calculator", "create_apple_note"],
        target_state={
            "note_created": True,
            "note_contains_result": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="计算并记录结果",
        tags=["calculator", "note"],
    ),
    TaskDefinition(
        task_id="multi_005",
        instruction="打开本地 dashboard，查看数据，截图，然后创建一条总结笔记。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["open_url", "read_page", "take_screenshot", "create_apple_note"],
        target_state={
            "screenshot_taken": True,
            "note_created": True,
        },
        validation_rules={
            "check_screenshot_exists": True,
            "check_note_exists": True,
        },
        description="查看 dashboard 并总结",
        tags=["dashboard", "screenshot", "note"],
    ),
    TaskDefinition(
        task_id="multi_006",
        instruction="创建一条提醒事项：明天下午提交周报，优先级为高，然后在提醒事项中打开它给我看。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["create_apple_reminder", "show_apple_reminder"],
        target_state={
            "reminder_created": True,
            "reminder_shown": True,
        },
        validation_rules={
            "check_todo_exists": True,
        },
        description="创建提醒事项并展示结果",
        tags=["reminder", "demo", "native-app"],
    ),
    TaskDefinition(
        task_id="multi_007",
        instruction="创建一条备忘录，标题为“LightClaw Demo”，内容为“这是一次本机备忘录联调演示”，然后打开这条备忘录给我看。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["create_apple_note", "open_apple_note"],
        target_state={
            "note_created": True,
            "note_opened": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="创建备忘录并展示结果",
        tags=["note", "demo", "native-app"],
    ),
]


JOB_APPLICATION_TASKS = [
    TaskDefinition(
        task_id="job_001",
        instruction="搜索目标公司的实习岗位官网入口，整理岗位名称、地点、申请入口，并写入笔记。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["search_web", "open_url", "read_page", "create_apple_note"],
        target_state={
            "note_created": True,
            "job_sources_found": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="搜索并整理官网实习岗位入口",
        tags=["job-application", "search", "internship"],
    ),
    TaskDefinition(
        task_id="job_002",
        instruction="打开目标公司的官网申请页面，阅读表单要求，整理必填字段和缺失信息。",
        category=TaskCategory.WEB_FORM,
        difficulty=TaskDifficulty.MEDIUM,
        allowed_tools=["open_url", "read_page", "create_apple_note"],
        target_state={
            "note_created": True,
            "required_fields_identified": True,
        },
        validation_rules={
            "check_note_exists": True,
        },
        description="解析官网申请表单字段",
        tags=["job-application", "form", "analysis"],
    ),
    TaskDefinition(
        task_id="job_003",
        instruction="在招聘官网中填写候选人基础信息，截图保存当前进度，然后创建一条后续跟进提醒。",
        category=TaskCategory.MULTI_STEP,
        difficulty=TaskDifficulty.HARD,
        allowed_tools=["open_url", "type_text", "select_option", "click", "take_screenshot", "create_apple_reminder"],
        target_state={
            "screenshot_taken": True,
            "todo_created": True,
        },
        validation_rules={
            "check_screenshot_exists": True,
            "check_todo_exists": True,
        },
        description="执行官网投递并记录跟进",
        tags=["job-application", "form", "submit-flow"],
    ),
]


# 所有任务集合
ALL_TASKS = (
    INFO_EXTRACTION_TASKS
    + TODO_CALENDAR_TASKS
    + WEB_FORM_TASKS
    + MULTI_STEP_TASKS
    + JOB_APPLICATION_TASKS
)


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
