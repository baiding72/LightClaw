use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::thread;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::Emitter;

#[derive(Serialize)]
struct RunSummary {
    id: String,
    path: String,
    modified_ms: u128,
    event_count: usize,
    title: String,
    run_type: String,
    session_id: Option<String>,
    pass_count: Option<i64>,
    fail_count: Option<i64>,
    model: Option<String>,
}

#[derive(Deserialize, Serialize)]
struct ChatTurnResult {
    session_id: String,
    run_id: String,
    run_path: String,
    answer: String,
}

#[derive(Serialize)]
struct WorkspaceFileEntry {
    path: String,
    is_dir: bool,
    size: u64,
    modified_ms: u128,
    depth: usize,
}

#[derive(Serialize)]
struct WorkspaceFileContent {
    path: String,
    content: String,
    truncated: bool,
}

fn repo_root() -> Result<PathBuf, String> {
    let manifest_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    manifest_dir
        .parent()
        .and_then(Path::parent)
        .map(Path::to_path_buf)
        .ok_or_else(|| "could not resolve repository root".to_string())
}

fn runs_dir() -> Result<PathBuf, String> {
    Ok(repo_root()?.join("runs"))
}

fn sessions_dir() -> Result<PathBuf, String> {
    Ok(repo_root()?.join("sessions"))
}

fn workspace_dir() -> Result<PathBuf, String> {
    Ok(repo_root()?.join("workspace"))
}

fn policy_config_path() -> Result<PathBuf, String> {
    Ok(repo_root()?.join("config").join("policy.json"))
}

fn approvals_dir() -> Result<PathBuf, String> {
    Ok(repo_root()?.join("runtime").join("approvals"))
}

fn safe_session_id(session_id: &str) -> String {
    let cleaned: String = session_id
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' || ch == '.' {
                ch
            } else {
                '-'
            }
        })
        .collect();
    let trimmed = cleaned.trim_matches('-');
    if trimmed.is_empty() {
        "default".to_string()
    } else {
        trimmed.chars().take(80).collect()
    }
}

fn safe_file_id(id: &str) -> String {
    let cleaned: String = id
        .chars()
        .map(|ch| {
            if ch.is_ascii_alphanumeric() || ch == '_' || ch == '-' || ch == '.' {
                ch
            } else {
                '-'
            }
        })
        .collect();
    if cleaned.is_empty() {
        "default".to_string()
    } else {
        cleaned
    }
}

fn now_millis() -> u128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|duration| duration.as_millis())
        .unwrap_or(0)
}

fn python_command() -> String {
    for candidate in [
        "/Users/baiding/miniconda3/bin/python",
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
        "python3",
        "python",
    ] {
        let probe = Command::new(candidate).arg("--version").output();
        if probe.is_ok() {
            return candidate.to_string();
        }
    }
    "python3".to_string()
}

fn parse_jsonl(path: &Path) -> Vec<Value> {
    let Ok(content) = fs::read_to_string(path) else {
        return Vec::new();
    };

    content
        .lines()
        .filter_map(|line| serde_json::from_str::<Value>(line).ok())
        .collect()
}

fn collect_workspace_files(root: &Path, dir: &Path, depth: usize, entries: &mut Vec<WorkspaceFileEntry>) -> Result<(), String> {
    if depth > 8 || entries.len() >= 400 {
        return Ok(());
    }

    let mut children = Vec::new();
    if !dir.exists() {
        return Ok(());
    }
    for entry in fs::read_dir(dir).map_err(|err| err.to_string())? {
        let entry = entry.map_err(|err| err.to_string())?;
        if entry
            .file_name()
            .to_str()
            .map(|name| name.starts_with('.'))
            .unwrap_or(false)
        {
            continue;
        }
        children.push(entry);
    }
    children.sort_by_key(|entry| {
        let path = entry.path();
        let is_file = path.is_file();
        (is_file, entry.file_name())
    });

    for entry in children {
        let path = entry.path();
        let metadata = entry.metadata().map_err(|err| err.to_string())?;
        let relative = path
            .strip_prefix(root)
            .map_err(|err| err.to_string())?
            .to_string_lossy()
            .to_string();
        let modified_ms = metadata
            .modified()
            .ok()
            .and_then(|time| time.elapsed().ok())
            .map(|elapsed| elapsed.as_millis())
            .unwrap_or(0);
        let is_dir = metadata.is_dir();
        entries.push(WorkspaceFileEntry {
            path: if is_dir { format!("{relative}/") } else { relative },
            is_dir,
            size: if metadata.is_file() { metadata.len() } else { 0 },
            modified_ms,
            depth,
        });
        if is_dir {
            collect_workspace_files(root, &path, depth + 1, entries)?;
        }
    }

    Ok(())
}

fn title_from_events(events: &[Value], fallback: &str) -> String {
    if let Some(case_id) = events
        .iter()
        .find_map(|event| event.get("case_id").and_then(Value::as_str))
    {
        return case_id.replace('_', " ");
    }

    if let Some(input) = events
        .iter()
        .find(|event| event.get("event").and_then(Value::as_str) == Some("user_input"))
        .and_then(|event| event.get("content_preview").and_then(Value::as_str))
    {
        return input.chars().take(42).collect();
    }

    if let Some(session_id) = events
        .iter()
        .find(|event| event.get("event").and_then(Value::as_str) == Some("interactive_session_started"))
        .and_then(|event| event.get("session_id").and_then(Value::as_str))
    {
        return format!("Interactive · {session_id}");
    }

    fallback.to_string()
}

fn enrich_ai_messages_from_transcript(events: &mut [Value]) -> Result<(), String> {
    let Some(session_id) = events
        .iter()
        .find_map(|event| event.get("session_id").and_then(Value::as_str))
        .map(str::to_string)
    else {
        return Ok(());
    };

    let transcript_path = sessions_dir()?.join(format!("{}.json", safe_session_id(&session_id)));
    if !transcript_path.exists() {
        return Ok(());
    }

    let transcript_content = fs::read_to_string(transcript_path).map_err(|err| err.to_string())?;
    let transcript: Value = serde_json::from_str(&transcript_content).map_err(|err| err.to_string())?;
    let assistant_contents: Vec<String> = transcript
        .as_array()
        .unwrap_or(&Vec::new())
        .iter()
        .filter(|item| item.get("role").and_then(Value::as_str) == Some("assistant"))
        .filter_map(|item| item.get("content").and_then(Value::as_str).map(str::to_string))
        .collect();

    let mut assistant_index = 0;
    for event in events.iter_mut() {
        if event.get("event").and_then(Value::as_str) != Some("ai_message") {
            continue;
        }
        if event.get("content").is_none() {
            if let Some(content) = assistant_contents.get(assistant_index) {
                if let Some(obj) = event.as_object_mut() {
                    obj.insert("content".to_string(), Value::String(content.clone()));
                }
            }
        }
        assistant_index += 1;
    }

    Ok(())
}

#[tauri::command]
fn list_runs() -> Result<Vec<RunSummary>, String> {
    let dir = runs_dir()?;
    if !dir.exists() {
        return Ok(Vec::new());
    }

    let mut runs = Vec::new();
    for entry in fs::read_dir(&dir).map_err(|err| err.to_string())? {
        let entry = entry.map_err(|err| err.to_string())?;
        let path = entry.path();
        if path.extension().and_then(|ext| ext.to_str()) != Some("jsonl") {
            continue;
        }

        let metadata = entry.metadata().map_err(|err| err.to_string())?;
        let modified_ms = metadata
            .modified()
            .ok()
            .and_then(|time| time.elapsed().ok())
            .map(|elapsed| elapsed.as_millis())
            .unwrap_or(0);
        let events = parse_jsonl(&path);
        let id = path
            .file_stem()
            .and_then(|stem| stem.to_str())
            .unwrap_or("unknown")
            .to_string();
        let run_type = if events.iter().any(|event| event.get("case_id").is_some()) {
            "eval"
        } else {
            "interactive"
        };
        let session_id = events
            .iter()
            .find_map(|event| event.get("session_id").and_then(Value::as_str))
            .map(str::to_string)
            .or_else(|| id.strip_prefix("interactive-").map(str::to_string));
        let summary = events
            .iter()
            .rev()
            .find(|event| event.get("event").and_then(Value::as_str) == Some("eval_summary"));

        runs.push(RunSummary {
            title: title_from_events(&events, &id),
            id,
            path: path.to_string_lossy().to_string(),
            modified_ms,
            event_count: events.len(),
            run_type: run_type.to_string(),
            session_id,
            pass_count: summary
                .and_then(|event| event.get("pass_count"))
                .and_then(Value::as_i64),
            fail_count: summary
                .and_then(|event| event.get("fail_count"))
                .and_then(Value::as_i64),
            model: events
                .iter()
                .find_map(|event| event.get("model").and_then(Value::as_str))
                .map(str::to_string),
        });
    }

    runs.sort_by_key(|run| run.modified_ms);
    Ok(runs)
}

#[tauri::command]
fn read_run(path: String) -> Result<Vec<Value>, String> {
    let requested = PathBuf::from(path);
    let canonical = requested.canonicalize().map_err(|err| err.to_string())?;
    let root = runs_dir()?.canonicalize().map_err(|err| err.to_string())?;
    if !canonical.starts_with(root) {
        return Err("run path escapes runs".to_string());
    }
    let mut events = parse_jsonl(&canonical);
    enrich_ai_messages_from_transcript(&mut events)?;
    Ok(events)
}

#[tauri::command]
fn list_agent_tools() -> Result<Vec<Value>, String> {
    let root = repo_root()?;
    let script = r#"
import json
from core.policy import tool_permission_for
from core.tools import ALL_TOOLS

items = []
for tool in ALL_TOOLS:
    schema = tool.get_schema()
    permission = tool_permission_for(schema.get("name", ""))
    params = schema.get("parameters", {})
    items.append({
        "name": schema.get("name", ""),
        "description": schema.get("description", ""),
        "parameters": params.get("properties", {}),
        "required": params.get("required", []),
        "permission": permission.key,
        "resource": permission.resource,
        "action": permission.action,
        "risk": permission.risk,
        "requires_consent": permission.requires_consent,
    })
print(json.dumps(items, ensure_ascii=False))
"#;
    let output = Command::new(python_command())
        .current_dir(root)
        .args(["-c", script])
        .output()
        .map_err(|err| err.to_string())?;

    if !output.status.success() {
        return Err(String::from_utf8_lossy(&output.stderr).to_string());
    }

    serde_json::from_slice::<Vec<Value>>(&output.stdout).map_err(|err| err.to_string())
}

#[tauri::command]
fn list_workspace_files() -> Result<Vec<WorkspaceFileEntry>, String> {
    let root = workspace_dir()?;
    fs::create_dir_all(&root).map_err(|err| err.to_string())?;
    let mut entries = Vec::new();
    collect_workspace_files(&root, &root, 0, &mut entries)?;
    Ok(entries)
}

#[tauri::command]
#[allow(non_snake_case)]
fn read_workspace_file(path: String) -> Result<WorkspaceFileContent, String> {
    let root = workspace_dir()?.canonicalize().map_err(|err| err.to_string())?;
    let requested = root.join(&path).canonicalize().map_err(|err| err.to_string())?;
    if !requested.starts_with(&root) {
        return Err("workspace file path escapes workspace".to_string());
    }
    if !requested.is_file() {
        return Err("workspace path is not a file".to_string());
    }
    let bytes = fs::read(&requested).map_err(|err| err.to_string())?;
    let max_bytes = 96 * 1024;
    let truncated = bytes.len() > max_bytes;
    let slice = if truncated { &bytes[..max_bytes] } else { &bytes[..] };
    let content = String::from_utf8(slice.to_vec()).map_err(|_| "file is not valid UTF-8 text".to_string())?;
    Ok(WorkspaceFileContent { path, content, truncated })
}

#[tauri::command]
fn write_workspace_file(path: String, content: String) -> Result<WorkspaceFileContent, String> {
    let root_path = workspace_dir()?;
    fs::create_dir_all(&root_path).map_err(|err| err.to_string())?;
    let root = root_path.canonicalize().map_err(|err| err.to_string())?;
    let requested = root.join(&path);
    let parent = requested
        .parent()
        .ok_or_else(|| "workspace file path has no parent".to_string())?;
    fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    let parent_canonical = parent.canonicalize().map_err(|err| err.to_string())?;
    if !parent_canonical.starts_with(&root) {
        return Err("workspace file path escapes workspace".to_string());
    }
    if requested.exists() && !requested.is_file() {
        return Err("workspace path is not a file".to_string());
    }
    fs::write(&requested, content.as_bytes()).map_err(|err| err.to_string())?;
    Ok(WorkspaceFileContent { path, content, truncated: false })
}

#[tauri::command]
fn get_policy_config() -> Result<Value, String> {
    let path = policy_config_path()?;
    let default = json!({
        "mode": "off",
        "approval_timeout_seconds": 300,
    });
    if !path.exists() {
        return Ok(default);
    }
    let content = fs::read_to_string(path).map_err(|err| err.to_string())?;
    let mut value = serde_json::from_str::<Value>(&content).unwrap_or(default.clone());
    if !value.is_object() {
        value = default;
    }
    if let Some(mode) = value.get("mode").and_then(Value::as_str) {
        let normalized = match mode {
            "monitor" => "auto",
            "enforce" | "ask" => "default",
            "read_only" => "plan",
            "off" | "default" | "plan" | "auto" => mode,
            _ => "off",
        };
        value["mode"] = Value::String(normalized.to_string());
    }
    Ok(value)
}

#[tauri::command]
fn set_policy_config(config: Value) -> Result<Value, String> {
    let mut mode = config
        .get("mode")
        .and_then(Value::as_str)
        .unwrap_or("off")
        .to_string();
    mode = match mode.as_str() {
        "monitor" => "auto".to_string(),
        "enforce" | "ask" => "default".to_string(),
        "read_only" => "plan".to_string(),
        _ => mode,
    };
    if !matches!(mode.as_str(), "off" | "default" | "plan" | "auto") {
        mode = "off".to_string();
    }
    let timeout = config
        .get("approval_timeout_seconds")
        .and_then(Value::as_i64)
        .unwrap_or(300)
        .clamp(10, 3600);
    let next = json!({
        "mode": mode,
        "approval_timeout_seconds": timeout,
    });
    let path = policy_config_path()?;
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).map_err(|err| err.to_string())?;
    }
    fs::write(
        &path,
        serde_json::to_string_pretty(&next).map_err(|err| err.to_string())?,
    )
    .map_err(|err| err.to_string())?;
    Ok(next)
}

#[tauri::command]
#[allow(non_snake_case)]
fn submit_tool_gate_decision(requestId: String, decision: String) -> Result<(), String> {
    let normalized = if decision == "allow" { "allow" } else { "deny" };
    let dir = approvals_dir()?;
    fs::create_dir_all(&dir).map_err(|err| err.to_string())?;
    let path = dir.join(format!("{}.json", safe_file_id(&requestId)));
    let payload = json!({
        "request_id": requestId,
        "decision": normalized,
        "ts": now_millis(),
    });
    fs::write(
        path,
        serde_json::to_string(&payload).map_err(|err| err.to_string())?,
    )
    .map_err(|err| err.to_string())
}

#[tauri::command]
#[allow(non_snake_case)]
fn create_eval_from_trace(path: String) -> Result<String, String> {
    let root = repo_root()?;
    let output = Command::new(python_command())
        .current_dir(root)
        .args(["-m", "evals.memory_policy_cases", "--from-trace", &path])
        .output()
        .map_err(|err| err.to_string())?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    if !output.status.success() {
        return Err(format!("{stdout}{stderr}"));
    }
    Ok(format!("{stdout}{stderr}"))
}

#[tauri::command]
#[allow(non_snake_case)]
fn start_eval_from_trace(path: String) -> Result<String, String> {
    let root = repo_root()?;
    let output = Command::new(python_command())
        .current_dir(root)
        .args(["-m", "evals.memory_policy_cases", "--start-from-trace", &path])
        .output()
        .map_err(|err| err.to_string())?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    Ok(format!("{stdout}{stderr}"))
}

#[tauri::command]
#[allow(non_snake_case)]
fn start_agent_eval(suite: Option<String>) -> Result<String, String> {
    let root = repo_root()?;
    let suite_name = suite.unwrap_or_else(|| "basic_tasks".to_string());
    let output = Command::new(python_command())
        .current_dir(root)
        .args(["-m", "evals.agent_eval_runner", "--suite", &suite_name])
        .output()
        .map_err(|err| err.to_string())?;

    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    Ok(format!("{stdout}{stderr}"))
}

#[tauri::command]
#[allow(non_snake_case)]
fn create_chat_session(sessionId: String) -> Result<ChatTurnResult, String> {
    let safe_id = safe_session_id(&sessionId);
    let run_id = format!("interactive-{safe_id}");
    let run_path = runs_dir()?.join(format!("{run_id}.jsonl"));
    let transcript_path = sessions_dir()?.join(format!("{safe_id}.json"));

    fs::create_dir_all(runs_dir()?).map_err(|err| err.to_string())?;
    fs::create_dir_all(sessions_dir()?).map_err(|err| err.to_string())?;
    fs::write(&transcript_path, "[]\n").map_err(|err| err.to_string())?;

    let event = json!({
        "ts": now_millis(),
        "run_id": run_id,
        "event": "interactive_session_started",
        "session_id": safe_id,
        "source": "mac_client"
    });
    fs::write(
        &run_path,
        format!("{}\n", serde_json::to_string(&event).map_err(|err| err.to_string())?),
    )
    .map_err(|err| err.to_string())?;

    Ok(ChatTurnResult {
        session_id: safe_id,
        run_id,
        run_path: run_path.to_string_lossy().to_string(),
        answer: String::new(),
    })
}

#[tauri::command]
#[allow(non_snake_case)]
fn send_chat_message(sessionId: String, message: String) -> Result<ChatTurnResult, String> {
    if message.trim().is_empty() {
        return Err("message is required".to_string());
    }

    let root = repo_root()?;
    let output = Command::new(python_command())
        .current_dir(root)
        .args([
            "-m",
            "interactive_turn",
            "--session-id",
            &sessionId,
            "--message",
            &message,
        ])
        .output()
        .map_err(|err| err.to_string())?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(stderr.to_string());
    }

    let stdout = String::from_utf8_lossy(&output.stdout);
    let last_line = stdout
        .lines()
        .rev()
        .find(|line| !line.trim().is_empty())
        .ok_or_else(|| "interactive turn returned no output".to_string())?;
    serde_json::from_str::<ChatTurnResult>(last_line).map_err(|err| err.to_string())
}

#[tauri::command]
#[allow(non_snake_case)]
async fn send_chat_message_stream(
    window: tauri::Window,
    sessionId: String,
    message: String,
) -> Result<(), String> {
    if message.trim().is_empty() {
        return Err("message is required".to_string());
    }

    let root = repo_root()?;
    let python = python_command();
    let session_id = sessionId;

    thread::spawn(move || {
        let spawn_result = Command::new(python)
            .current_dir(root)
            .args([
                "-m",
                "interactive_turn",
                "--stream",
                "--session-id",
                &session_id,
                "--message",
                &message,
            ])
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn();

        let Ok(mut child) = spawn_result else {
            let _ = window.emit("stream_error", &serde_json::json!({
                "type": "stream_error",
                "session_id": session_id,
                "error_type": "ProcessSpawnError",
                "error": spawn_result.err().map(|err| err.to_string()).unwrap_or_else(|| "failed to spawn stream process".to_string()),
            }));
            return;
        };

        let stderr = child.stderr.take();
        if let Some(stderr) = stderr {
            let stderr_window = window.clone();
            let stderr_session_id = session_id.clone();
            thread::spawn(move || {
                let reader = BufReader::new(stderr);
                for line in reader.lines().map_while(Result::ok) {
                    if line.trim().is_empty() {
                        continue;
                    }
                    let _ = stderr_window.emit("stream_stderr", &serde_json::json!({
                        "type": "stream_stderr",
                        "session_id": stderr_session_id,
                        "line": line,
                    }));
                }
            });
        }

        let Some(stdout) = child.stdout.take() else {
            let _ = window.emit("stream_error", &serde_json::json!({
                "type": "stream_error",
                "session_id": session_id,
                "error_type": "StdoutCaptureError",
                "error": "failed to capture stream stdout",
            }));
            return;
        };

        let reader = BufReader::new(stdout);
        for line in reader.lines().map_while(Result::ok) {
            if line.trim().is_empty() {
                continue;
            }
            match serde_json::from_str::<Value>(&line) {
                Ok(event) => {
                    let event_type = event
                        .get("type")
                        .and_then(|v| v.as_str())
                        .unwrap_or("unknown");
                    let _ = window.emit(event_type, &event);
                }
                Err(err) => {
                    let _ = window.emit("stream_error", &serde_json::json!({
                        "type": "stream_error",
                        "session_id": session_id,
                        "error_type": "StreamParseError",
                        "error": err.to_string(),
                        "line": line,
                    }));
                }
            }
        }

        match child.wait() {
            Ok(status) if status.success() => {}
            Ok(status) => {
                let _ = window.emit("stream_error", &serde_json::json!({
                    "type": "stream_error",
                    "session_id": session_id,
                    "error_type": "ProcessExitError",
                    "error": format!("Process exited with code {:?}", status.code()),
                    "code": status.code(),
                }));
            }
            Err(err) => {
                let _ = window.emit("stream_error", &serde_json::json!({
                    "type": "stream_error",
                    "session_id": session_id,
                    "error_type": "ProcessWaitError",
                    "error": err.to_string(),
                }));
            }
        }
    });

    Ok(())
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            list_runs,
            read_run,
            list_agent_tools,
            list_workspace_files,
            read_workspace_file,
            write_workspace_file,
            get_policy_config,
            set_policy_config,
            submit_tool_gate_decision,
            create_eval_from_trace,
            start_eval_from_trace,
            start_agent_eval,
            create_chat_session,
            send_chat_message,
            send_chat_message_stream,
        ])
        .run(tauri::generate_context!())
        .expect("error while running myClaw Harness Lab");
}
