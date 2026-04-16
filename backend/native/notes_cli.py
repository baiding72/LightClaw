#!/usr/bin/env python3
import json
import subprocess
import sys
from typing import Any


def _run_osascript(script: str, *args: str) -> str:
    proc = subprocess.run(
        ["osascript", "-", *args],
        input=script,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or "osascript failed")
    return proc.stdout.strip()


def _print_json(value: Any) -> None:
    json.dump(value, sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def create_note(payload: dict[str, Any]) -> dict[str, Any]:
    title = payload["title"]
    content = payload["content"]
    folder = payload.get("folder") or ""

    script = r'''
on joinFields(itemList, delim)
    set AppleScript's text item delimiters to delim
    set outputText to itemList as text
    set AppleScript's text item delimiters to ""
    return outputText
end joinFields

on run argv
    set noteTitle to item 1 of argv
    set noteContent to item 2 of argv
    set folderName to item 3 of argv
    set fieldSep to ASCII character 31

    tell application "Notes"
        if folderName is "" then
            set targetFolder to default folder of default account
        else
            set targetFolder to missing value
            repeat with acc in every account
                repeat with f in every folder of acc
                    if name of f is folderName then
                        set targetFolder to f
                        exit repeat
                    end if
                end repeat
                if targetFolder is not missing value then exit repeat
            end repeat
            if targetFolder is missing value then error "Folder not found: " & folderName
        end if

        set newBody to noteTitle & return & noteContent
        set newNote to make new note at targetFolder with properties {body:newBody}
        delay 0.2
        return my joinFields({id of newNote, name of newNote, plaintext of newNote, folderName, (creation date of newNote as «class isot» as string)}, fieldSep)
    end tell
end run
'''
    raw = _run_osascript(script, title, content, folder)
    note_id, note_title, plaintext, folder_name, creation_date = raw.split(chr(31))
    return {
        "id": note_id,
        "title": note_title,
        "plaintext": plaintext,
        "folder": folder_name,
        "creation_date": creation_date,
    }


def list_notes(payload: dict[str, Any]) -> dict[str, Any]:
    folder = payload.get("folder") or ""
    limit = int(payload.get("limit", 20))

    script = r'''
on joinRecords(itemList, delim)
    set AppleScript's text item delimiters to delim
    set outputText to itemList as text
    set AppleScript's text item delimiters to ""
    return outputText
end joinRecords

on run argv
    set folderName to item 1 of argv
    set noteLimit to (item 2 of argv) as integer
    set recordSep to ASCII character 30
    set fieldSep to ASCII character 31
    set rows to {}

    tell application "Notes"
        set sourceNotes to {}
        if folderName is "" then
            repeat with acc in every account
                set sourceNotes to sourceNotes & (every note of acc)
            end repeat
        else
            repeat with acc in every account
                repeat with f in every folder of acc
                    if name of f is folderName then
                        set sourceNotes to every note of f
                        exit repeat
                    end if
                end repeat
                if (count of sourceNotes) > 0 then exit repeat
            end repeat
        end if

        repeat with i from 1 to (count of sourceNotes)
            if i > noteLimit then exit repeat
            set n to item i of sourceNotes
            set end of rows to (id of n & fieldSep & name of n & fieldSep & plaintext of n & fieldSep & folderName & fieldSep & (creation date of n as «class isot» as string))
        end repeat
    end tell

    return my joinRecords(rows, recordSep)
end run
'''
    raw = _run_osascript(script, folder, str(limit))
    notes = []
    if raw:
        for row in raw.split(chr(30)):
            note_id, title, plaintext, folder_name, creation_date = row.split(chr(31))
            notes.append(
                {
                    "id": note_id,
                    "title": title,
                    "plaintext": plaintext,
                    "folder": folder_name,
                    "creation_date": creation_date,
                }
            )
    return {"notes": notes, "total": len(notes)}


def open_note(payload: dict[str, Any]) -> dict[str, Any]:
    note_id = payload["note_id"]

    script = r'''
on run argv
    set targetId to item 1 of argv
    tell application "Notes"
        repeat with n in every note
            if id of n is targetId then
                show n
                return id of n & linefeed & name of n
            end if
        end repeat
    end tell
    error "Note not found: " & targetId
end run
'''
    raw = _run_osascript(script, note_id)
    found_id, title = raw.splitlines()
    return {"id": found_id, "title": title, "opened": True}


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Missing command. Expected: create, list, open")

    command = sys.argv[1]
    payload_text = sys.stdin.read().strip() or "{}"
    payload = json.loads(payload_text)

    if command == "create":
        result = create_note(payload)
    elif command == "list":
        result = list_notes(payload)
    elif command == "open":
        result = open_note(payload)
    else:
        raise SystemExit(f"Unsupported command: {command}")

    _print_json(result)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        _print_json({"success": False, "error": str(exc)})
        raise SystemExit(1)
