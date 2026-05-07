from app.tools.registry import ToolRegistry
from app.tools.skills import build_default_tool_skills


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    for skill in build_default_tool_skills():
        registry.register_skill(skill)
    return registry


def test_tool_skills_register_metadata_without_loading_tools() -> None:
    registry = _registry()

    skills = registry.list_skills()

    assert len(skills) >= 5
    assert registry.get_loaded_tool_count() == 0
    assert "write_note" in registry.list_tools()
    assert registry.has_tool("click") is True
    assert all(skill["loaded"] is False for skill in skills)


def test_get_tool_progressively_loads_owning_skill() -> None:
    registry = _registry()

    tool = registry.get("write_note")

    assert tool is not None
    assert tool.name == "write_note"
    assert registry.get_loaded_tool_count() == 3
    structured = registry.get_skill("structured_memory_write")
    assert structured is not None
    assert structured.loaded is True
    browser = registry.get_skill("browser_gui_control")
    assert browser is not None
    assert browser.loaded is False


def test_get_schemas_with_names_loads_only_requested_skill() -> None:
    registry = _registry()

    schemas = registry.get_schemas(["click", "type_text"])

    assert [schema["name"] for schema in schemas] == ["click", "type_text"]
    assert registry.get_loaded_tool_count() == 5
    assert registry.get_skill("browser_gui_control").loaded is True
    assert registry.get_skill("apple_native_apps").loaded is False


def test_get_all_preserves_legacy_full_registry_behavior() -> None:
    registry = _registry()

    tools = registry.get_all()

    tool_names = {tool.name for tool in tools}
    assert "read_file" in tool_names
    assert "write_note" in tool_names
    assert "click" in tool_names
    assert "select_option" in tool_names
    assert registry.get_loaded_tool_count() == len(tool_names)
    assert all(skill["loaded"] is True for skill in registry.list_skills())
