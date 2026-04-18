import pytest

from app.runtime.executor import Executor
from app.runtime.state import AgentState


class DummySessionContext:
    async def __aenter__(self):
        return None

    async def __aexit__(self, exc_type, exc, tb):
        return False


class DummyElement:
    async def inner_text(self) -> str:
        return "hello from browser runtime"


class DummyPage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self.goto_calls: list[str] = []

    async def goto(self, url: str, wait_until: str | None = None) -> None:
        self.url = url
        self.goto_calls.append(url)

    async def title(self) -> str:
        return f"title for {self.url}"

    async def query_selector(self, selector: str):
        if selector == "body":
            return DummyElement()
        return None


class DummyBrowserManager:
    def __init__(self, page: DummyPage) -> None:
        self.page = page

    async def start(self) -> None:
        return None


@pytest.mark.asyncio
async def test_open_url_uses_default_browser_runtime_when_page_not_passed(monkeypatch) -> None:
    page = DummyPage()
    manager = DummyBrowserManager(page)

    async def fake_get_browser_manager():
        return manager

    monkeypatch.setattr("app.runtime.executor.get_browser_manager", fake_get_browser_manager)
    monkeypatch.setattr("app.runtime.executor.async_session_maker", lambda: DummySessionContext())

    executor = Executor()
    state = AgentState(task_id="task_1", instruction="open page", trajectory_id="traj_1")

    result = await executor.execute("open_url", {"url": "https://example.com"}, state)

    assert result.success is True
    assert result.result["status"] == "loaded"
    assert page.goto_calls == ["https://example.com"]
    assert state.browser_runtime_initialized is True


@pytest.mark.asyncio
async def test_read_page_syncs_selected_tab_into_default_browser_runtime(monkeypatch) -> None:
    page = DummyPage()
    manager = DummyBrowserManager(page)

    async def fake_get_browser_manager():
        return manager

    monkeypatch.setattr("app.runtime.executor.get_browser_manager", fake_get_browser_manager)
    monkeypatch.setattr("app.runtime.executor.async_session_maker", lambda: DummySessionContext())

    executor = Executor()
    state = AgentState(
        task_id="task_2",
        instruction="read selected page",
        trajectory_id="traj_2",
        browser_context={
            "selected_tab": {
                "url": "https://example.org/current",
                "title": "Example Org",
            },
            "tabs": [],
        },
    )

    result = await executor.execute("read_page", {}, state)

    assert result.success is True
    assert result.result["content"] == "hello from browser runtime"
    assert page.goto_calls == ["https://example.org/current"]
    assert state.current_url == "https://example.org/current"
    assert state.current_page_title == "title for https://example.org/current"
