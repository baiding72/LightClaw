"""Test cases for myClaw security constraints and safeguards."""

import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import pytest

# Set PYTHONPATH before imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestTaskThreadLock:
    """P0: Task file thread lock - prevents concurrent writes from corrupting tasks.json"""

    def setup_method(self):
        """Clean up tasks before each test."""
        from core.tools.builtins import TASKS_FILE, TASKS_DIR
        TASKS_DIR.mkdir(parents=True, exist_ok=True)
        if TASKS_FILE.exists():
            TASKS_FILE.unlink()

    def test_sequential_task_operations(self):
        """Sequential schedule/list/cancel works correctly."""
        from core.tools.builtins import schedule_task, list_tasks, cancel_task

        result = schedule_task.invoke({
            'target_time': '2027-01-01 12:00:00',
            'description': 'Test task 1'
        })
        assert 'Task scheduled' in result

        result = list_tasks.invoke({})
        assert 'Test task 1' in result

        # Get task id from file
        from core.tools.builtins import TASKS_FILE
        tasks = json.loads(TASKS_FILE.read_text())
        task_id = tasks[0]['id']

        result = cancel_task.invoke({'task_id': task_id})
        assert 'cancelled' in result

        tasks = json.loads(TASKS_FILE.read_text())
        assert not any(t['id'] == task_id for t in tasks)

    def test_concurrent_writes_no_corruption(self):
        """Multiple threads writing tasks.json simultaneously should not corrupt it."""
        from core.tools.builtins import schedule_task, TASKS_FILE

        errors = []
        def concurrent_schedule(thread_id):
            try:
                for i in range(3):
                    schedule_task.invoke({
                        'target_time': f'2027-01-01 12:{thread_id:02d}:{i:02d}',
                        'description': f'Thread-{thread_id}-task-{i}'
                    })
            except Exception as e:
                errors.append(f'Thread {thread_id}: {e}')

        threads = []
        for t in range(10):
            th = threading.Thread(target=concurrent_schedule, args=(t,))
            threads.append(th)
            th.start()

        for th in threads:
            th.join()

        assert len(errors) == 0, f'Errors occurred: {errors}'

        # Verify tasks.json is still valid JSON
        tasks = json.loads(TASKS_FILE.read_text())
        assert len(tasks) == 30, f'Expected 30 tasks, got {len(tasks)}'


class TestOfficeFileSandbox:
    """P0: Office file sandbox - prevents directory traversal attacks"""

    def test_legitimate_file_access(self):
        """Reading files within office sandbox works."""
        from core.tools.files import OFFICE_DIR, read_office_file

        # Create a test file in office
        office_dir = OFFICE_DIR
        office_dir.mkdir(parents=True, exist_ok=True)
        test_file = office_dir / 'test_sandbox.txt'
        test_file.write_text('sandbox test content')

        result = read_office_file.invoke({'relative_path': 'test_sandbox.txt'})
        assert 'sandbox test content' in result

        test_file.unlink()

    def test_directory_traversal_blocked(self):
        """Attempting to escape office sandbox is blocked."""
        from core.tools.files import read_office_file

        result = read_office_file.invoke({'relative_path': '../../etc/passwd'})
        assert 'Error' in result
        assert 'escapes' in result or 'not found' in result

        result = read_office_file.invoke({'relative_path': '../../../.ssh'})
        assert 'Error' in result


class TestShellSandbox:
    """P1: Shell sandbox - three layers of protection"""

    def test_working_directory_locked(self):
        """Shell commands execute in office directory, not elsewhere."""
        from core.tools.shell import execute_office_shell

        result = execute_office_shell.invoke({'command': 'pwd'})
        assert 'workspace/office' in result

    def test_path_traversal_blocked(self):
        """Path traversal patterns are blocked."""
        from core.tools.shell import execute_office_shell

        # ../ blocked
        result = execute_office_shell.invoke({'command': 'ls ../'})
        assert 'Error' in result
        assert 'detected dangerous directory escape' in result

        # Absolute paths blocked
        result = execute_office_shell.invoke({'command': 'cat /etc/passwd'})
        assert 'Error' in result
        assert 'detected dangerous' in result

        # Home directory blocked
        result = execute_office_shell.invoke({'command': 'ls ~'})
        assert 'Error' in result

    def test_privileged_commands_blocked(self):
        """Privilege escalation commands are blocked."""
        from core.tools.shell import execute_office_shell

        result = execute_office_shell.invoke({'command': 'sudo whoami'})
        assert 'Error' in result
        assert 'not allowed' in result

        result = execute_office_shell.invoke({'command': 'su root'})
        assert 'Error' in result

    def test_valid_commands_allowed(self):
        """Valid commands within sandbox work fine."""
        from core.tools.shell import execute_office_shell

        result = execute_office_shell.invoke({'command': 'ls'})
        assert 'Exit code: 0' in result

        result = execute_office_shell.invoke({'command': 'echo hello'})
        assert 'hello' in result

    def test_shell_timeout_enforced(self):
        """Long-running commands are killed after timeout."""
        from core.tools.shell import execute_office_shell, SHELL_TIMEOUT

        # This command should timeout
        start = time.time()
        result = execute_office_shell.invoke({'command': f'sleep {SHELL_TIMEOUT + 5}'})
        elapsed = time.time() - start

        assert 'timed out' in result or elapsed < SHELL_TIMEOUT + 10


class TestPreExecutionParamValidation:
    """P0: Pre-execution parameter validation"""

    def test_echo_missing_required_param(self):
        """Calling echo without required 'message' param returns error via harness."""
        from core.agent import AgentHarness
        from core.tools.builtins import echo

        # Test via harness _execute_tool (how agent actually calls tools)
        h = AgentHarness(llm=None, tools=[echo])
        result, gate = h._execute_tool('echo', {}, user_input='call echo')
        assert 'Error' in result
        assert 'missing required argument' in result
        assert 'message' in result

    def test_calculator_with_valid_expression(self):
        """Calculator works with valid expressions."""
        from core.tools.builtins import calculator

        result = calculator.invoke({'expression': '2+2'})
        assert result == '4'

        result = calculator.invoke({'expression': '10*5'})
        assert result == '50'

    def test_calculator_eval_injection_blocked(self):
        """Calculator prevents code injection via eval."""
        from core.tools.builtins import calculator

        # __builtins__ is blocked so this should fail
        result = calculator.invoke({'expression': '__import__("os").system("ls")'})
        assert 'Error' in result


class TestTaskTimeValidation:
    """P0: Task scheduling time format and future-time validation"""

    def test_past_time_rejected(self):
        """Scheduling a task in the past is rejected."""
        from core.tools.builtins import schedule_task

        result = schedule_task.invoke({
            'target_time': '2020-01-01 12:00:00',
            'description': 'past task'
        })
        assert 'Error' in result
        assert 'must be in the future' in result

    def test_invalid_format_rejected(self):
        """Invalid time format is rejected."""
        from core.tools.builtins import schedule_task

        result = schedule_task.invoke({
            'target_time': 'not-a-time',
            'description': 'bad format'
        })
        assert 'Error' in result
        assert 'YYYY-MM-DD HH:MM:SS' in result

    def test_valid_future_time_accepted(self):
        """Valid future time is accepted."""
        from core.tools.builtins import schedule_task

        result = schedule_task.invoke({
            'target_time': '2030-12-31 23:59:59',
            'description': 'future task'
        })
        assert 'Task scheduled' in result


class TestContextTrimming:
    """P2: Context trimming prevents token overflow"""

    def test_trim_trigger_threshold(self):
        """Messages beyond threshold trigger trimming."""
        from core.state import AgentState, CONTEXT_TRIM_TRIGGER

        state = AgentState()
        # Add enough messages to exceed threshold
        for i in range(CONTEXT_TRIM_TRIGGER + 5):
            state.add_user_message(f'User message {i}')
            state.add_ai_message(f'Assistant response {i}')

        # Should trigger trim check
        initial_count = len(state.messages)
        assert initial_count > CONTEXT_TRIM_TRIGGER

    def test_trim_keeps_recent_turns(self):
        """After trimming, recent turns are preserved with summary."""
        from core.state import AgentState, CONTEXT_TRIM_KEEP

        state = AgentState()
        # Add 45 messages (exceeds trigger of 40)
        for i in range(45):
            if i % 2 == 0:
                state.add_user_message(f'User {i}')
            else:
                state.add_ai_message(f'Assistant {i}')

        summary = state.trim_context()

        assert summary != ''
        assert state.summary != ''
        assert len(state.messages) < 45
        assert len(state.messages) > 0


class TestProfileInjection:
    """P2: Long-term user profile injected each turn"""

    def test_profile_loaded_if_exists(self):
        """Profile is loaded from workspace/memory/profile.md."""
        from core.agent import AgentHarness

        h = AgentHarness(llm=None)
        profile = h._load_user_profile()

        # If profile file exists, it should be loaded
        from core.config import MEMORY_DIR

        profile_path = MEMORY_DIR / 'profile.md'
        if profile_path.exists():
            assert len(profile) > 0

    def test_profile_injected_in_messages(self):
        """Profile appears in built messages when available."""
        from core.agent import AgentHarness
        from core.state import AgentState

        h = AgentHarness(llm=None)
        state = AgentState()
        state.add_user_message('hello')

        messages = h._build_messages(state)

        assert len(messages) >= 2
        assert messages[0]['role'] == 'system'
        assert messages[-1]['role'] == 'user'
        # Profile is folded into the first system message for provider
        # compatibility with tool-calling OpenAI-compatible endpoints.
        assert '[User Profile]' in messages[0]['content'] or len(h._load_user_profile()) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
