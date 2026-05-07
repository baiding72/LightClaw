from app.gateway.event_schema import TaskEvent
from app.runtime.skill_selector import SkillSelector
from app.tools.registry import ToolRegistry
from app.tools.skills import build_default_tool_skills


def _selector() -> SkillSelector:
    registry = ToolRegistry()
    for skill in build_default_tool_skills():
        registry.register_skill(skill)
    return SkillSelector(registry)


def test_recruiting_instruction_selects_retrieval_and_browser_with_context() -> None:
    selection = _selector().select(
        "查看当前招聘页面的投递记录",
        browser_context={"selected_tab": {"url": "https://jobs.example.com", "title": "Jobs"}},
        scenario_type="recruiting",
    )

    assert "information_retrieval" in selection.selected_skills
    assert "browser_gui_control" in selection.selected_skills
    assert "read_file" in selection.allowed_tools
    assert "click" in selection.allowed_tools


def test_write_task_selects_structured_memory_skill() -> None:
    selection = _selector().select("写一条笔记，总结今天投递情况")

    assert "structured_memory_write" in selection.selected_skills
    assert "information_retrieval" in selection.selected_skills
    assert "write_note" in selection.allowed_tools


def test_explicit_allowed_tools_are_preserved_and_skills_recorded() -> None:
    selection = _selector().select("自定义任务", allowed_tools=["click", "type_text"])

    assert selection.allowed_tools == ["click", "type_text"]
    assert selection.selected_skills == ["browser_gui_control"]


def test_task_event_serializes_selected_skills() -> None:
    event = TaskEvent(
        task_id="task",
        user_instruction="查看招聘页面",
        allowed_tools=["read_file"],
        selected_skills=[{"skill_id": "information_retrieval", "reason": "读取页面"}],
    )

    payload = event.to_dict()

    assert payload["selected_skills"][0]["skill_id"] == "information_retrieval"
