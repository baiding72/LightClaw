"""Tests for sandboxed file tools."""

from core.tools.files import OFFICE_DIR, list_office_files, read_office_file, update_office_file, write_office_file


def test_write_read_and_list_office_file():
    relative_path = "notes/react-tool-test.txt"
    target = OFFICE_DIR / relative_path
    if target.exists():
        target.unlink()

    write_result = write_office_file.invoke({"relative_path": relative_path, "content": "ReAct note"})

    assert "Wrote 10 characters" in write_result
    assert read_office_file.invoke({"relative_path": relative_path}) == "ReAct note"
    assert "notes/" in list_office_files.invoke({"relative_path": "."})
    assert "notes/react-tool-test.txt" in list_office_files.invoke({"relative_path": "notes"})

    overwrite_result = write_office_file.invoke({"relative_path": relative_path, "content": "new"})
    assert "already exists" in overwrite_result

    update_result = update_office_file.invoke({"relative_path": relative_path, "content": "updated"})
    assert "Updated 7 characters" in update_result
    assert read_office_file.invoke({"relative_path": relative_path}) == "updated"


def test_list_office_files_treats_empty_path_as_root():
    result = list_office_files.invoke({"relative_path": ""})

    assert "Error: relative_path is required" not in result
    assert result


def test_file_tools_reject_path_escape():
    result = read_office_file.invoke({"relative_path": "../../README.md"})

    assert result.startswith("Error:")
    assert "escapes" in result
