#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import textwrap
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

try:
    import yaml
except Exception:
    yaml = None

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
except Exception:
    FileSystemEventHandler = None
    Observer = None

try:
    from ssh_remote import setup_remote, teardown_remote
except Exception:
    setup_remote = None
    teardown_remote = None


_BULLET_RE = re.compile(r"^\s*(?:[-*•・]|(?:\d+)[\)\.\:]?|\(\d+\))\s+")

# Regex patterns to parse token usage from Claude/Codex CLI output
_TOKEN_PATTERN = re.compile(
    r"(?:tokens?|トークン)[:\s]*(\d[\d,]*)",
    re.IGNORECASE
)
_USAGE_PATTERN = re.compile(
    r"(?:usage|使用量|context)[:\s]*(\d[\d,]*)\s*/\s*(\d[\d,]*)",
    re.IGNORECASE
)
_PERCENT_REMAINING_PATTERN = re.compile(r"(\d+)%\s*(?:left|remaining)", re.IGNORECASE)
_PERCENT_USED_PATTERN = re.compile(r"(\d+)%\s*(?:used|usage)", re.IGNORECASE)


@dataclass
class TokenUsage:
    """Tracks cumulative token usage across orchestrator operations."""
    total_input: int = 0
    total_output: int = 0
    total_combined: int = 0
    call_count: int = 0
    history: list = field(default_factory=list)

    # Configurable limits
    warning_threshold: float = 0.75  # Warn at 75% of limit
    compact_threshold: float = 0.85  # Auto-compact at 85% of limit
    max_tokens: int = 200000  # Default context limit

    # Callbacks for threshold events
    on_warning: Callable[["TokenUsage"], None] | None = None
    on_compact_needed: Callable[["TokenUsage"], None] | None = None

    def add_usage(self, input_tokens: int = 0, output_tokens: int = 0, label: str = "") -> None:
        """Record token usage from an operation."""
        self.total_input += input_tokens
        self.total_output += output_tokens
        combined = input_tokens + output_tokens
        self.total_combined += combined
        self.call_count += 1
        self.history.append({
            "label": label,
            "input": input_tokens,
            "output": output_tokens,
            "combined": combined,
            "cumulative": self.total_combined,
            "timestamp": dt.datetime.now().isoformat(),
        })
        self._check_thresholds()

    def usage_ratio(self) -> float:
        """Return current usage as a ratio of max_tokens."""
        if self.max_tokens <= 0:
            return 0.0
        return self.total_combined / self.max_tokens

    def _check_thresholds(self) -> None:
        """Check if thresholds are exceeded and trigger callbacks."""
        ratio = self.usage_ratio()
        if ratio >= self.compact_threshold and self.on_compact_needed:
            self.on_compact_needed(self)
        elif ratio >= self.warning_threshold and self.on_warning:
            self.on_warning(self)

    def to_dict(self) -> dict:
        """Export usage stats as a dictionary."""
        return {
            "total_input": self.total_input,
            "total_output": self.total_output,
            "total_combined": self.total_combined,
            "call_count": self.call_count,
            "usage_ratio": round(self.usage_ratio(), 4),
            "max_tokens": self.max_tokens,
            "warning_threshold": self.warning_threshold,
            "compact_threshold": self.compact_threshold,
            "history": self.history,
        }

    def status_message(self) -> str:
        """Generate a human-readable status message."""
        ratio = self.usage_ratio()
        return (
            f"トークン使用状況: {self.total_combined:,} / {self.max_tokens:,} "
            f"({ratio*100:.1f}%) - {self.call_count}回の呼び出し"
        )


def estimate_tokens(text: str) -> int:
    """Estimate token count from text (rough approximation)."""
    # Rough estimate: ~4 chars per token for English, ~1.5 for Japanese
    if not text:
        return 0
    # Count Japanese characters
    jp_chars = len(re.findall(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]', text))
    other_chars = len(text) - jp_chars
    return int(jp_chars / 1.5 + other_chars / 4)


def parse_token_usage(output: str) -> tuple[int, int]:
    """
    Parse token usage from CLI output.
    Returns (input_tokens, output_tokens) or estimates if not found.
    """
    # Try to find explicit usage pattern like "usage: 1234 / 200000"
    usage_match = _USAGE_PATTERN.search(output)
    if usage_match:
        used = int(usage_match.group(1).replace(",", ""))
        return (used, 0)

    # Try to find token count mentions
    token_matches = _TOKEN_PATTERN.findall(output)
    if token_matches:
        # Return the largest number found as a rough estimate
        tokens = [int(m.replace(",", "")) for m in token_matches]
        return (max(tokens), 0)

    # Fallback: estimate from output length
    return (0, estimate_tokens(output))


def parse_usage_from_json_lines(output: str) -> tuple[int, int]:
    """Parse usage info from JSON lines output. Returns (input_tokens, output_tokens)."""
    if not output:
        return (0, 0)
    for line in output.strip().split("\n"):
        try:
            data = json.loads(line)
        except Exception:
            continue
        usage = data.get("usage")
        if isinstance(usage, dict):
            input_tokens = int(usage.get("input_tokens", 0) or 0)
            output_tokens = int(usage.get("output_tokens", 0) or 0)
            if input_tokens or output_tokens:
                return (input_tokens, output_tokens)
    return (0, 0)


def detect_cli_type(cmd_base: list[str]) -> str:
    """
    Detect whether the command is for Claude or Codex CLI.
    Returns 'claude', 'codex', or 'unknown'.
    """
    if not cmd_base:
        return "unknown"
    cmd_str = " ".join(cmd_base).lower()
    if "claude" in cmd_str:
        return "claude"
    if "codex" in cmd_str:
        return "codex"
    return "unknown"


def call_compact_command(cmd_base: list[str], run_dir: Path, verbose: bool = False) -> bool:
    """
    Attempt to call /compact on the Claude or Codex session.
    Returns True if successful.
    """
    cli_type = detect_cli_type(cmd_base)

    if cli_type == "claude":
        try:
            compact_cmd = ["claude", "-p", "/compact"]
            result = subprocess.run(
                compact_cmd,
                input="/compact\n",
                text=True,
                capture_output=True,
                timeout=30,
                env=os.environ.copy(),
            )
            if verbose:
                print(f"[TokenManager] Claude /compact 実行結果: returncode={result.returncode}", file=sys.stderr)
            return result.returncode == 0
        except Exception as e:
            if verbose:
                print(f"[TokenManager] Claude /compact 実行エラー: {e}", file=sys.stderr)
            return False

    elif cli_type == "codex":
        # Codex CLI uses different commands for context management
        # Try 'codex compact' or signal via environment
        try:
            # First try: codex with compact flag if available
            compact_cmd = ["codex", "compact"]
            result = subprocess.run(
                compact_cmd,
                text=True,
                capture_output=True,
                timeout=30,
                env=os.environ.copy(),
            )
            if result.returncode == 0:
                if verbose:
                    print(f"[TokenManager] Codex compact 実行成功", file=sys.stderr)
                return True

            # Fallback: try sending /compact as input to codex exec
            compact_cmd = ["codex", "exec", "--skip-git-repo-check"]
            result = subprocess.run(
                compact_cmd,
                input="/compact\n",
                text=True,
                capture_output=True,
                timeout=30,
                env=os.environ.copy(),
            )
            if verbose:
                print(f"[TokenManager] Codex /compact 実行結果: returncode={result.returncode}", file=sys.stderr)
            return result.returncode == 0
        except Exception as e:
            if verbose:
                print(f"[TokenManager] Codex compact 実行エラー: {e}", file=sys.stderr)
            return False

    return False


def call_status_command(cmd_base: list[str], verbose: bool = False) -> str:
    """
    Attempt to call /status on the Claude or Codex session.
    Returns status output or empty string if failed.
    """
    cli_type = detect_cli_type(cmd_base)

    if cli_type == "claude":
        try:
            # Minimal token usage check (JSON) to reduce token consumption
            status_cmd = ["claude", "-p", "--output-format", "json", "hello"]
            result = subprocess.run(
                status_cmd,
                text=True,
                capture_output=True,
                timeout=30,
                env=os.environ.copy(),
            )
            if verbose:
                print(f"[TokenManager] Claude usage 実行結果: returncode={result.returncode}", file=sys.stderr)
            input_tokens, output_tokens = parse_usage_from_json_lines(result.stdout or "")
            total_tokens = input_tokens + output_tokens
            if total_tokens:
                used_pct = round((total_tokens * 100) / 200000, 1)
                return f"usage: {total_tokens} / 200000 ({used_pct}%)"
            return result.stdout or ""
        except Exception as e:
            if verbose:
                print(f"[TokenManager] Claude usage 実行エラー: {e}", file=sys.stderr)
            return ""

    elif cli_type == "codex":
        try:
            # Prefer codex status (no token consumption) and parse remaining percentage
            status_cmd = ["codex", "status"]
            result = subprocess.run(
                status_cmd,
                text=True,
                capture_output=True,
                timeout=30,
                env=os.environ.copy(),
            )
            if result.stdout:
                remaining_match = _PERCENT_REMAINING_PATTERN.search(result.stdout)
                if remaining_match:
                    return f"remaining: {remaining_match.group(1)}%"
                used_match = _PERCENT_USED_PATTERN.search(result.stdout)
                if used_match:
                    return f"usage: {used_match.group(1)}%"

            # Fallback: minimal JSON exec to estimate usage
            status_cmd = ["codex", "exec", "--skip-git-repo-check", "--json", "hello"]
            result = subprocess.run(
                status_cmd,
                text=True,
                capture_output=True,
                timeout=30,
                env=os.environ.copy(),
            )
            if verbose:
                print(f"[TokenManager] Codex JSON 実行結果: returncode={result.returncode}", file=sys.stderr)
            input_tokens, output_tokens = parse_usage_from_json_lines(result.stdout or "")
            total_tokens = input_tokens + output_tokens
            if total_tokens:
                used_pct = round((total_tokens * 100) / 400000, 1)
                return f"usage: {total_tokens} / 400000 ({used_pct}%)"
            return result.stdout or ""
        except Exception as e:
            if verbose:
                print(f"[TokenManager] Codex usage 実行エラー: {e}", file=sys.stderr)
            return ""

    return ""


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def ensure_run_dir(base: Path, forced: Path | None = None) -> Path:
    if forced is not None:
        forced.mkdir(parents=True, exist_ok=True)
        return forced
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base / "runs" / f"{stamp}_{uuid.uuid4().hex[:6]}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def extract_json(text: str) -> dict:
    # Try to strip code fences if present.
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fenced:
        return json.loads(fenced.group(1))
    # Fallback: grab the first {...} block.
    raw = re.search(r"\{.*\}", text, re.S)
    if not raw:
        raise ValueError("JSONが見つかりませんでした。")
    return json.loads(raw.group(0))


def ensure_yaml_available() -> None:
    if yaml is None:
        raise RuntimeError("PyYAMLが必要です。'pip install pyyaml' を実行してください。")


def extract_yaml(text: str) -> dict:
    ensure_yaml_available()
    fenced = re.search(r"```(?:yaml|yml)?\s*(.*?)\s*```", text, re.S)
    if fenced:
        data = yaml.safe_load(fenced.group(1))
        if isinstance(data, dict):
            return data
    raw = text.strip()
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError("YAMLが辞書形式ではありません。")
    return data


def read_yaml(path: Path) -> dict:
    ensure_yaml_available()
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_yaml(path: Path, data: dict) -> None:
    ensure_yaml_available()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    tmp.replace(path)


class WatchHandle:
    def __init__(self, path: Path):
        self.path = path
        self.event = threading.Event()
        self.observer = None
        if Observer is None or FileSystemEventHandler is None:
            return

        class Handler(FileSystemEventHandler):
            def on_modified(inner_self, event):
                if Path(event.src_path).resolve() == self.path.resolve():
                    self.event.set()

            def on_created(inner_self, event):
                if Path(event.src_path).resolve() == self.path.resolve():
                    self.event.set()

        self._handler = Handler()
        self.observer = Observer()
        self.observer.schedule(self._handler, str(self.path.parent), recursive=False)
        self.observer.start()

    def wait(self, timeout: float = 2.0) -> None:
        if self.observer is None:
            time.sleep(timeout)
            return
        self.event.wait(timeout)
        self.event.clear()

    def stop(self) -> None:
        if self.observer is None:
            return
        self.observer.stop()
        self.observer.join()


def command_uses(cmd_tmpl: list[str], placeholder: str) -> bool:
    token = "{" + placeholder + "}"
    return any(token in part for part in cmd_tmpl)


def write_status(run_dir: Path, status: dict) -> None:
    status["updated_at"] = dt.datetime.now().isoformat()
    (run_dir / "status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def split_task_lines(task: str) -> list[str]:
    lines = [line.strip() for line in task.splitlines() if line.strip()]
    if not lines:
        return []
    bullets = []
    for line in lines:
        if _BULLET_RE.match(line):
            bullets.append(_BULLET_RE.sub("", line).strip())
    if len(bullets) >= 2:
        return [b for b in bullets if b]
    return [task.strip()]


def unique_name(name: str, used: set[str]) -> str:
    if name not in used:
        return name
    idx = 2
    while f"{name}-{idx}" in used:
        idx += 1
    return f"{name}-{idx}"


def normalize_dependency_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        deps: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                deps.append(item.strip())
        return deps
    return []


def normalize_task_entry(item, default_group: str) -> dict | None:
    if isinstance(item, str):
        if not item.strip():
            return None
        return {
            "id": "",
            "task": item.strip(),
            "notes": "",
            "preferred": "",
            "deps": [],
            "group": default_group,
        }
    if not isinstance(item, dict):
        return None
    task_text = (
        item.get("task")
        or item.get("summary")
        or item.get("detail")
        or item.get("instruction")
    )
    if not task_text:
        return None
    return {
        "id": str(item.get("id") or item.get("task_id") or item.get("name") or "").strip(),
        "task": str(task_text).strip(),
        "notes": str(item.get("notes") or "").strip(),
        "preferred": str(
            item.get("preferred_instrument")
            or item.get("instrument")
            or item.get("role")
            or ""
        ).strip(),
        "deps": normalize_dependency_list(
            item.get("deps") or item.get("depends_on") or item.get("dependencies")
        ),
        "group": default_group,
    }


def normalize_tasks(score: dict, task: str) -> list[dict]:
    tasks: list[dict] = []

    raw_dag = score.get("dag")
    raw_bag = score.get("bag")
    if isinstance(raw_dag, list):
        for item in raw_dag:
            entry = normalize_task_entry(item, "dag")
            if entry:
                tasks.append(entry)
    if isinstance(raw_bag, list):
        for item in raw_bag:
            entry = normalize_task_entry(item, "bag")
            if entry:
                tasks.append(entry)

    raw_performers = score.get("performers")
    if not tasks and isinstance(raw_performers, list):
        for item in raw_performers:
            entry = normalize_task_entry(item, "bag")
            if entry:
                if isinstance(item, dict):
                    entry["preferred"] = str(item.get("name") or item.get("instrument") or "").strip()
                tasks.append(entry)

    raw_tasks = score.get("tasks")
    if not tasks and isinstance(raw_tasks, list):
        for item in raw_tasks:
            entry = normalize_task_entry(item, "bag")
            if entry:
                tasks.append(entry)

    if not tasks:
        raw_instruments = score.get("instruments")
        if isinstance(raw_instruments, list):
            for item in raw_instruments:
                entry = normalize_task_entry(item, "bag")
                if entry:
                    if isinstance(item, dict):
                        entry["preferred"] = str(item.get("name") or "").strip()
                    tasks.append(entry)

    if not tasks:
        for part in split_task_lines(task):
            if part.strip():
                tasks.append(
                    {
                        "id": "",
                        "task": part.strip(),
                        "notes": "",
                        "preferred": "",
                        "deps": [],
                        "group": "bag",
                    }
                )

    if not tasks and task.strip():
        tasks = [
            {
                "id": "",
                "task": task.strip(),
                "notes": "",
                "preferred": "",
                "deps": [],
                "group": "bag",
            }
        ]
    return tasks


def assign_instruments(tasks: list[dict], instrument_pool: list[str]) -> list[dict]:
    used: set[str] = set()
    assigned: list[dict] = []
    pool = [name for name in instrument_pool if isinstance(name, str) and name.strip()]
    pool_index = 0

    for idx, item in enumerate(tasks, start=1):
        preferred = (item.get("preferred") or "").strip()
        name = ""
        if preferred:
            name = unique_name(preferred, used)
        else:
            while pool_index < len(pool) and pool[pool_index] in used:
                pool_index += 1
            if pool_index < len(pool):
                name = unique_name(pool[pool_index], used)
                pool_index += 1
            else:
                name = f"演奏者-{idx}"
        used.add(name)
        assigned.append(
            {
                "name": name,
                "task": (item.get("task") or "").strip(),
                "notes": (item.get("notes") or "").strip(),
                "id": (item.get("id") or "").strip(),
                "deps": item.get("deps") or [],
                "group": (item.get("group") or "").strip(),
            }
        )
    return assigned


def normalize_assignments(assignments: list[dict], verbose: bool) -> list[dict]:
    used_ids: set[str] = set()
    for idx, inst in enumerate(assignments, start=1):
        raw_id = str(inst.get("id") or inst.get("task_id") or "").strip()
        if not raw_id:
            raw_id = f"task-{idx}"
        if raw_id in used_ids:
            unique_id = unique_name(raw_id, used_ids)
            if verbose:
                print(
                    f"警告: タスクID '{raw_id}' が重複したため '{unique_id}' に変更しました。",
                    file=sys.stderr,
                )
            raw_id = unique_id
        used_ids.add(raw_id)
        inst["id"] = raw_id
        inst["deps"] = normalize_dependency_list(inst.get("deps"))

    for inst in assignments:
        deps = [dep for dep in inst.get("deps") or [] if dep and dep != inst["id"]]
        # Drop unknown deps to avoid deadlocks
        filtered = [dep for dep in deps if dep in used_ids]
        if verbose and len(filtered) != len(deps):
            unknown = [dep for dep in deps if dep not in used_ids]
            if unknown:
                print(
                    f"警告: 未定義の依存ID {unknown} を無視しました。",
                    file=sys.stderr,
                )
        inst["deps"] = filtered
    return assignments


def normalize_score(score: dict, task: str, instrument_pool: list[str]) -> dict:
    tasks = normalize_tasks(score, task)
    assignments = assign_instruments(tasks, instrument_pool)
    refined = score.get("refined_task") or score.get("refined") or ""
    return {
        "title": score.get("title") or "分担スコア",
        "refined_task": refined or task,
        "global_notes": score.get("global_notes") or "",
        "instruments": assignments,
        "performers": assignments,
    }


def apply_permission_flags(cmd: list[str], permissions: dict, cli_type: str | None = None) -> list[str]:
    """Apply permission flags to a command based on config.

    Args:
        cmd: The base command list
        permissions: The permissions config dict with 'claude' and 'codex' keys
        cli_type: Override CLI type detection ('claude' or 'codex')

    Returns:
        Modified command list with permission flags added
    """
    if not cmd:
        return cmd

    # Detect CLI type if not provided
    if cli_type is None:
        cli_type = detect_cli_type(cmd)
        if cli_type == "unknown":
            return cmd

    result = list(cmd)

    if cli_type == "claude":
        claude_perms = permissions.get("claude", {})
        mode = claude_perms.get("mode")
        add_dirs = claude_perms.get("add_dirs", [])

        # Find insertion point (after 'claude' but before prompt-related args)
        insert_idx = 1
        for i, part in enumerate(result):
            if part in ("-p", "--print", "--system-prompt"):
                insert_idx = i
                break

        # Add permission mode flag
        if mode == "bypassPermissions":
            result.insert(insert_idx, "--dangerously-skip-permissions")
            insert_idx += 1
        elif mode and mode != "default":
            result.insert(insert_idx, f"--permission-mode={mode}")
            insert_idx += 1

        # Add directory flags
        for d in add_dirs:
            result.insert(insert_idx, "--add-dir")
            insert_idx += 1
            result.insert(insert_idx, d)
            insert_idx += 1

    elif cli_type == "codex":
        codex_perms = permissions.get("codex", {})
        sandbox = codex_perms.get("sandbox")
        full_auto = codex_perms.get("full_auto", False)
        add_dirs = codex_perms.get("add_dirs", [])

        # Find insertion point (after 'codex exec' but before other args)
        insert_idx = 1
        for i, part in enumerate(result):
            if part == "exec":
                insert_idx = i + 1
                break

        # Add full-auto flag (skips confirmation prompts)
        if full_auto:
            result.insert(insert_idx, "--full-auto")
            insert_idx += 1
        # Add sandbox flag
        elif sandbox:
            result.insert(insert_idx, f"--sandbox={sandbox}")
            insert_idx += 1

        # Add directory flags
        for d in add_dirs:
            result.insert(insert_idx, "--add-dir")
            insert_idx += 1
            result.insert(insert_idx, d)
            insert_idx += 1

    return result


def run_external(
    cmd_tmpl: list[str],
    prompt: str,
    run_dir: Path,
    label: str,
    timeout_sec: int | None,
    dry_run: bool,
    extra_vars: dict | None = None,
    token_tracker: TokenUsage | None = None,
) -> dict:
    extra_vars = extra_vars or {}
    prompt_path = run_dir / f"{label}_prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")

    stdout_path = run_dir / f"{label}_stdout.txt"
    stderr_path = run_dir / f"{label}_stderr.txt"

    if not cmd_tmpl:
        stderr_path.write_text("コマンドが未設定です。", encoding="utf-8")
        stdout_path.write_text("", encoding="utf-8")
        return {
            "cmd": [],
            "stdout": "",
            "stderr": "コマンドが未設定です。",
            "returncode": 1,
            "used_stdin": False,
            "tokens_input": 0,
            "tokens_output": 0,
        }

    uses_prompt = command_uses(cmd_tmpl, "prompt")
    uses_prompt_file = command_uses(cmd_tmpl, "prompt_file")
    fmt_vars = {
        "prompt": prompt,
        "prompt_file": str(prompt_path),
        **extra_vars,
    }
    cmd = [part.format(**fmt_vars) for part in cmd_tmpl]
    stdin_text = None if (uses_prompt or uses_prompt_file) else prompt

    if dry_run:
        stdout_path.write_text("[dry-run] 実行をスキップしました。", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        return {
            "cmd": cmd,
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "used_stdin": stdin_text is not None,
            "tokens_input": 0,
            "tokens_output": 0,
        }

    result = subprocess.run(
        cmd,
        input=stdin_text,
        text=True,
        capture_output=True,
        timeout=timeout_sec,
        env=os.environ.copy(),
    )
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    # Track token usage
    input_tokens = estimate_tokens(prompt)
    output_text = result.stdout or ""
    parsed_input, parsed_output = parse_token_usage(output_text)
    output_tokens = parsed_output if parsed_output else estimate_tokens(output_text)
    if parsed_input:
        input_tokens = parsed_input

    if token_tracker:
        token_tracker.add_usage(input_tokens, output_tokens, label)

    return {
        "cmd": cmd,
        "stdout": result.stdout or "",
        "stderr": result.stderr or "",
        "returncode": result.returncode,
        "used_stdin": stdin_text is not None,
        "tokens_input": input_tokens,
        "tokens_output": output_tokens,
    }


def rewriter_prompt(task: str, instruments: list[str]) -> str:
    """Rewriter prompt (Japanese) - relies on CLAUDE.md for full instructions."""
    inst_list = ", ".join(instruments)
    return f"タスク: {task}\n楽器: {inst_list}"


def concertmaster_initial_prompt(refined_task: str, global_notes: str, performer: dict) -> str:
    """Initial prompt (English) - relies on AGENT.md for schema."""
    return (
        "YOU ARE THE CONCERTMASTER. OUTPUT ONLY YAML. DO NOT DO ANY WORK.\n"
        "Your ONLY job is to give the first instruction to the performer.\n"
        "DO NOT read files. DO NOT execute commands. DO NOT generate code.\n"
        "The PERFORMER will do all the actual work.\n\n"
        f"Task: {refined_task}\n"
        f"Notes: {global_notes}\n"
        f"Performer: {performer.get('name','')} - {performer.get('task','')}\n\n"
        "Now output ONLY this YAML format:\n"
        "action: reply\n"
        "reply: \"Your brief instruction to performer\"\n"
        "reason: \"Why\""
    )


def concertmaster_review_prompt(refined_task: str, global_notes: str, performer: dict, output: str) -> str:
    """Review prompt (English) - relies on AGENT.md for schema.
    Include a clear question when action is needs_user_confirm.
    """
    # Truncate long output to save tokens
    max_output_len = 2000
    if len(output) > max_output_len:
        output = output[:max_output_len] + "\n...(truncated)"
    return (
        "YOU ARE THE CONCERTMASTER. OUTPUT ONLY YAML. DO NOT DO ANY WORK.\n"
        "Review the performer's output and decide: done, reply, or needs_user_confirm.\n"
        "If you choose needs_user_confirm, you MUST include a concise 'question' field describing what needs confirmation.\n"
        "DO NOT read files. DO NOT execute commands. DO NOT generate code.\n\n"
        f"Task: {refined_task}\n"
        f"Performer: {performer.get('name','')}\n"
        f"Output:\n{output}\n\n"
        "YAML format (choose one):\n"
        "For reply:   action: reply / reply: \"instruction\" / reason: \"why\"\n"
        "For done:    action: done / reason: \"why complete\"\n"
        "For confirm: action: needs_user_confirm / question: \"what to confirm\" / reason: \"why\"\n\n"
        "IMPORTANT: If using needs_user_confirm, 'question' field is REQUIRED and must summarize what needs user decision."
    )


def performer_prompt(
    instrument: str,
    task: str,
    global_notes: str,
    extra_notes: str | None,
) -> str:
    """Performer prompt (English) - relies on AGENT.md for schema."""
    notes = f" ({extra_notes})" if extra_notes else ""
    return f"Role: {instrument}\nTask: {task}{notes}"


def mix_prompt(score: dict, performances: list[dict]) -> str:
    """Mix prompt (Japanese output) - relies on CLAUDE.md."""
    parts = []
    for perf in performances:
        # Truncate long outputs
        out = perf['output'][:1500] if len(perf['output']) > 1500 else perf['output']
        parts.append(f"[{perf['instrument']}] {out}")
    joined = "\n".join(parts)
    return f"統合して日本語で出力:\n{joined}"


def local_mix(score: dict, performances: list[dict]) -> str:
    lines = []
    title = score.get("title") or "統合結果"
    lines.append(f"{title}")
    lines.append("=" * len(title))
    global_notes = score.get("global_notes")
    if global_notes:
        lines.append(f"全体方針: {global_notes}")
        lines.append("")
    for perf in performances:
        lines.append(f"[{perf['instrument']}]")
        lines.append(perf["output"].strip() or "（出力なし）")
        lines.append("")
    return "\n".join(lines).strip()


def init_exchange(path: Path, performer: dict) -> dict:
    data = {
        "performer": {
            "name": performer.get("name", ""),
            "task": performer.get("task", ""),
            "notes": performer.get("notes", ""),
        },
        "status": "waiting_for_concertmaster",
        "turn": 0,
        "history": [],
        "pending": {},
        "updated_at": dt.datetime.now().isoformat(),
    }
    write_yaml(path, data)
    return data


def append_exchange_message(data: dict, role: str, content: str, msg_type: str = "message") -> dict:
    history = data.get("history") or []
    history.append(
        {
            "role": role,
            "type": msg_type,
            "content": content,
            "timestamp": dt.datetime.now().isoformat(),
        }
    )
    data["history"] = history
    data["updated_at"] = dt.datetime.now().isoformat()
    return data


def get_last_message(data: dict, role: str) -> str | None:
    history = data.get("history") or []
    for item in reversed(history):
        if item.get("role") == role:
            return item.get("content")
    return None


def build_performer_prompt(data: dict, performer: dict) -> str:
    """Build performer prompt with conversation context."""
    history = data.get("history") or []
    task = performer.get("task", "")

    last_output = ""
    for item in reversed(history):
        if item.get("role") == "performer":
            last_output = (item.get("content", "") or "")[:1000]
            break

    last_instruction = ""
    for item in reversed(history):
        if item.get("role") == "concertmaster":
            last_instruction = item.get("content", "") or ""
            break

    if not last_instruction:
        return task

    parts = [f"Task: {task}"]
    if last_output:
        parts.append(f"Your previous output:\n{last_output}")
    parts.append(f"New instruction: {last_instruction}")

    return "\n\n".join(parts)


def read_exchange(path: Path) -> dict:
    data = read_yaml(path)
    if not data:
        return {}
    return data


def update_exchange(path: Path, lock: threading.Lock, update_fn) -> dict:
    with lock:
        data = read_exchange(path)
        data = update_fn(data)
        write_yaml(path, data)
        return data


def parse_action_output(text: str) -> dict:
    try:
        return extract_yaml(text)
    except Exception:
        return {"action": "reply", "reply": text.strip(), "reason": "YAML解析に失敗したため全文を返却"}

def extract_choices_from_question(question: str) -> list[str]:
    """質問文から番号付き選択肢を抽出する。
    
    例: "(1) 日付順 (2) カテゴリ別 (3) その他" -> ["1: 日付順", "2: カテゴリ別", "3: その他"]
    """
    import re
    # パターン: (1) ... (2) ... または 1. ... 2. ... または 1) ... 2) ...
    patterns = [
        r'\((\d+)\)\s*([^(]+?)(?=\s*\(\d+\)|$)',  # (1) text (2) text
        r'(?:^|\s)(\d+)\.\s*([^0-9]+?)(?=\s*\d+\.|$)',  # 1. text 2. text
        r'(?:^|\s)(\d+)\)\s*([^0-9]+?)(?=\s*\d+\)|$)',  # 1) text 2) text
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, question, re.DOTALL)
        if len(matches) >= 2:  # 少なくとも2つの選択肢がある場合
            return [f"{num}: {text.strip()}" for num, text in matches]
    
    return []


def normalize_confirm_payload(action_data: dict) -> dict:
    confirm = action_data.get("confirm") or {}
    confirm_type = (confirm.get("type") or action_data.get("confirm_type") or "").strip().lower()
    question = confirm.get("question") or action_data.get("question") or ""
    reason = confirm.get("reason") or action_data.get("reason") or ""
    if not question:
        question = "確認内容が未設定です"
    options = confirm.get("options") or confirm.get("choices") or action_data.get("options") or action_data.get("choices") or []
    if isinstance(options, str):
        options = [options]
    options = [str(opt) for opt in options if opt]
    
    # 質問文から選択肢を自動検出（明示的なoptionsがない場合）
    if not options:
        extracted = extract_choices_from_question(str(question))
        if extracted:
            options = extracted
    
    # confirm_type を決定: 明示的に指定されていない場合、optionsがあればchoice、なければok_ng
    if confirm_type not in ("ok_ng", "choice", "free_text"):
        if options:
            confirm_type = "choice"
        else:
            confirm_type = "ok_ng"
    
    ok_reply = confirm.get("ok_reply") or action_data.get("ok_reply") or action_data.get("reply") or ""
    ng_reply = confirm.get("ng_reply") or action_data.get("ng_reply") or ""
    choice_template = confirm.get("choice_reply_template") or action_data.get("choice_reply_template") or ""
    return {
        "type": confirm_type,
        "question": str(question),
        "reason": str(reason) if reason else "",
        "options": options,
        "ok_reply": str(ok_reply) if ok_reply else "",
        "ng_reply": str(ng_reply) if ng_reply else "",
        "choice_reply_template": str(choice_template) if choice_template else "",
    }


def build_reply_from_pending(pending: dict) -> str:
    pending_type = (pending.get("type") or "ok_ng").strip().lower()
    question = pending.get("question") or ""
    
    if pending_type == "choice":
        choice = pending.get("user_choice") or pending.get("user_reply") or ""
        template = pending.get("choice_reply_template") or ""
        if template:
            return template.replace("{choice}", str(choice))
        if question:
            return f"ユーザーへの質問「{question}」に対する選択: {choice}。この選択で進めてください。"
        return f"ユーザー選択: {choice}。この選択で進めてください。"

    if pending_type == "free_text":
        user_text = pending.get("user_reply") or ""
        if question:
            return f"ユーザーへの質問「{question}」に対する回答: {user_text}。この回答に基づいて進めてください。"
        return f"ユーザー回答: {user_text}"

    # ok_ng type
    decision = pending.get("user_reply")
    if not decision:
        decision = "OK" if pending.get("user_approved") else "NG"
    normalized = str(decision).strip().lower()
    
    if normalized in ("ok", "yes", "y", "true", "1", "承認", "はい"):
        # OKの場合、質問文を含めて何を承認したかを明確にする
        ok_reply = pending.get("ok_reply")
        if ok_reply:
            return ok_reply
        if question:
            return f"ユーザーへの質問「{question}」に対する回答: OK（承認）。提案通り進めてください。"
        return "ユーザー回答: OK。提案通り進めてください。"
    
    # NGの場合
    ng_reply = pending.get("ng_reply")
    if ng_reply:
        return ng_reply
    if question:
        return f"ユーザーへの質問「{question}」に対する回答: NG（却下）。修正案を提示してください。"
    return "ユーザー回答: NG。修正案を提示してください。"


def concertmaster_worker(
    exchange_path: Path,
    performer: dict,
    refined_task: str,
    global_notes: str,
    concertmaster_cmd: list[str],
    timeout_sec: int | None,
    run_dir: Path,
    label_prefix: str,
    lock: threading.Lock,
    stop_event: threading.Event,
    verbose: bool,
    max_turns: int,
    dry_run: bool,
    token_tracker: TokenUsage | None = None,
) -> None:
    watcher = WatchHandle(exchange_path)
    turn = 0
    try:
        while not stop_event.is_set():
            data = read_exchange(exchange_path)
            status = data.get("status")
            if status in ("done", "error"):
                break

            if status == "waiting_for_user":
                pending = data.get("pending") or {}
                if pending.get("user_reply") or pending.get("user_choice") or pending.get("user_approved"):
                    reply = build_reply_from_pending(pending)

                    def apply_user(d: dict) -> dict:
                        append_exchange_message(d, "concertmaster", reply, "prompt")
                        d["status"] = "waiting_for_performer"
                        d["pending"] = {}
                        d["turn"] = d.get("turn", 0) + 1
                        return d

                    update_exchange(exchange_path, lock, apply_user)
                else:
                    watcher.wait(1.5)
                continue

            if status != "waiting_for_concertmaster":
                watcher.wait(1.5)
                continue

            if turn >= max_turns:
                def force_done(d: dict) -> dict:
                    d["status"] = "done"
                    return d

                update_exchange(exchange_path, lock, force_done)
                break

            performer_output = get_last_message(data, "performer")
            if performer_output:
                prompt = concertmaster_review_prompt(refined_task, global_notes, performer, performer_output)
            else:
                prompt = concertmaster_initial_prompt(refined_task, global_notes, performer)

            result = run_external(
                concertmaster_cmd,
                prompt,
                run_dir,
                f"{label_prefix}_{turn}",
                timeout_sec,
                dry_run,
                extra_vars={"instrument": performer.get("name", "")},
                token_tracker=token_tracker,
            )
            output = result["stdout"].strip()
            action_data = parse_action_output(output)
            action = (action_data.get("action") or "reply").strip()
            reply = (action_data.get("reply") or "").strip()

            if action == "done":
                def apply_done(d: dict) -> dict:
                    append_exchange_message(d, "concertmaster", action_data.get("reason", ""), "review")
                    d["status"] = "done"
                    d["pending"] = {}
                    return d

                update_exchange(exchange_path, lock, apply_done)
                break
            if action == "needs_user_confirm":
                confirm = normalize_confirm_payload(action_data)

                def apply_user_wait(d: dict) -> dict:
                    append_exchange_message(d, "concertmaster", action_data.get("reason", ""), "review")
                    d["status"] = "waiting_for_user"
                    d["pending"] = {
                        "type": confirm["type"],
                        "question": confirm["question"],
                        "reason": confirm.get("reason", ""),
                        "options": confirm["options"],
                        "ok_reply": confirm["ok_reply"],
                        "ng_reply": confirm["ng_reply"],
                        "choice_reply_template": confirm["choice_reply_template"],
                        "user_reply": "",
                        "user_choice": "",
                        "user_approved": False,
                    }
                    return d

                update_exchange(exchange_path, lock, apply_user_wait)
                continue

            if not reply:
                reply = "続けてください。"

            def apply_reply(d: dict) -> dict:
                append_exchange_message(d, "concertmaster", reply, "prompt")
                d["status"] = "waiting_for_performer"
                d["pending"] = {}
                d["turn"] = d.get("turn", 0) + 1
                return d

            update_exchange(exchange_path, lock, apply_reply)
            turn += 1
    finally:
        watcher.stop()


def performer_worker(
    exchange_path: Path,
    performer: dict,
    performer_cmd: list[str],
    timeout_sec: int | None,
    run_dir: Path,
    label_prefix: str,
    lock: threading.Lock,
    stop_event: threading.Event,
    max_turns: int,
    dry_run: bool,
    token_tracker: TokenUsage | None = None,
) -> None:
    watcher = WatchHandle(exchange_path)
    turn = 0
    try:
        while not stop_event.is_set():
            data = read_exchange(exchange_path)
            status = data.get("status")
            if status in ("done", "error"):
                break
            if status != "waiting_for_performer":
                watcher.wait(1.5)
                continue

            prompt = build_performer_prompt(data, performer)
            result = run_external(
                performer_cmd,
                prompt,
                run_dir,
                f"{label_prefix}_{turn}",
                timeout_sec,
                dry_run,
                extra_vars={"instrument": performer.get("name", "")},
                token_tracker=token_tracker,
            )
            output = result["stdout"].strip()
            turn += 1

            def apply_output(d: dict) -> dict:
                append_exchange_message(d, "performer", output, "response")
                d["status"] = "waiting_for_concertmaster"
                return d

            update_exchange(exchange_path, lock, apply_output)
    finally:
        watcher.stop()


def fallback_score(task: str, instruments: list[str]) -> dict:
    return {
        "title": "分担スコア（フォールバック）",
        "refined_task": task,
        "global_notes": "指揮者のJSON出力が取得できなかったため、同一タスクを分配。",
        "tasks": [task],
    }


def run(
    task: str,
    config_path: Path,
    dry_run: bool,
    verbose: bool,
    run_dir: Path | None,
) -> int:
    config = load_config(config_path)
    base_dir = config_path.parent
    run_dir = ensure_run_dir(base_dir, run_dir)

    # Set up SSH remote filesystem if configured
    _ssh_remote_active = False
    if setup_remote is not None:
        ssh_ok, ssh_msg, ssh_local_path = setup_remote(config)
        if ssh_ok and ssh_local_path:
            _ssh_remote_active = True
            if verbose:
                print(f"[SSHRemote] {ssh_msg}", file=sys.stderr)
            # Inject mount path into permissions.*.add_dirs if auto_add_dirs is set
            ssh_cfg = config.get("ssh_remote") or {}
            if ssh_cfg.get("auto_add_dirs", True):
                permissions = config.get("permissions") or {}
                for cli_name in ("claude", "codex"):
                    cli_perms = permissions.get(cli_name) or {}
                    add_dirs = list(cli_perms.get("add_dirs") or [])
                    if ssh_local_path not in add_dirs:
                        add_dirs.append(ssh_local_path)
                        cli_perms["add_dirs"] = add_dirs
                    permissions[cli_name] = cli_perms
                config["permissions"] = permissions
        elif not ssh_ok and config.get("ssh_remote", {}).get("enabled"):
            print(f"[SSHRemote] 警告: {ssh_msg}", file=sys.stderr)

    write_status(
        run_dir,
        {
            "stage": "initialized",
            "progress": 0.0,
            "task": task,
        },
    )

    try:
        ensure_yaml_available()

        # Initialize token tracker with config values
        token_config = config.get("token_management") or {}
        token_tracker = TokenUsage(
            max_tokens=token_config.get("max_tokens", 200000),
            warning_threshold=token_config.get("warning_threshold", 0.75),
            compact_threshold=token_config.get("compact_threshold", 0.85),
        )

        # Track compact attempts to avoid infinite loops
        compact_attempts = [0]
        max_compact_attempts = token_config.get("max_compact_attempts", 3)

        def on_token_warning(tracker: TokenUsage) -> None:
            """Called when token usage exceeds warning threshold."""
            msg = f"[TokenManager] 警告: {tracker.status_message()}"
            print(msg, file=sys.stderr)
            # Write warning to status
            write_status(
                run_dir,
                {
                    "stage": "token_warning",
                    "progress": tracker.usage_ratio(),
                    "task": task,
                    "token_usage": tracker.to_dict(),
                },
            )

        def on_compact_needed(tracker: TokenUsage) -> None:
            """Called when token usage exceeds compact threshold."""
            if compact_attempts[0] >= max_compact_attempts:
                print(
                    f"[TokenManager] コンパクト試行回数上限 ({max_compact_attempts}) に達しました。",
                    file=sys.stderr,
                )
                return

            compact_attempts[0] += 1
            print(
                f"[TokenManager] トークン使用量がしきい値を超えました。"
                f" /compact を実行します... (試行 {compact_attempts[0]}/{max_compact_attempts})",
                file=sys.stderr,
            )

            # Try compacting both Claude and Codex sessions
            rewriter_cfg = config.get("rewriter") or config.get("conductor") or {}
            concertmaster_cfg = config.get("concertmaster") or {}
            performer_cfg = config.get("performer") or {}

            cmd_bases = [
                ("rewriter", rewriter_cfg.get("cmd", [])),
                ("concertmaster", concertmaster_cfg.get("cmd", [])),
                ("performer", performer_cfg.get("cmd", [])),
            ]

            compact_results = {}
            for name, cmd_base in cmd_bases:
                cli_type = detect_cli_type(cmd_base)
                if cli_type == "unknown":
                    continue

                if verbose:
                    status_output = call_status_command(cmd_base, verbose=True)
                    if status_output:
                        print(f"[TokenManager] {name} ({cli_type}) /status 結果:\n{status_output[:500]}", file=sys.stderr)

                success = call_compact_command(cmd_base, run_dir, verbose=verbose)
                compact_results[name] = {"cli_type": cli_type, "success": success}

                if success:
                    print(f"[TokenManager] {name} ({cli_type}) /compact が正常に完了しました。", file=sys.stderr)
                else:
                    print(f"[TokenManager] {name} ({cli_type}) /compact の実行に失敗しました。", file=sys.stderr)

            # Check if any compact succeeded
            any_success = any(r["success"] for r in compact_results.values())
            if any_success:
                # Reset tracker partially after compaction (estimate 50% reduction)
                tracker.total_combined = int(tracker.total_combined * 0.5)
                tracker.total_input = int(tracker.total_input * 0.5)
                tracker.total_output = int(tracker.total_output * 0.5)

            # Save compact event to run directory
            compact_log = run_dir / "compact_events.json"
            events = []
            if compact_log.exists():
                try:
                    events = json.loads(compact_log.read_text(encoding="utf-8"))
                except Exception:
                    pass
            events.append({
                "attempt": compact_attempts[0],
                "results": compact_results,
                "any_success": any_success,
                "usage_before": tracker.total_combined,
                "timestamp": dt.datetime.now().isoformat(),
            })
            compact_log.write_text(
                json.dumps(events, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        # Set callbacks (only once to avoid duplicate warnings)
        warning_fired = [False]
        compact_fired = [False]

        def on_warning_once(tracker: TokenUsage) -> None:
            if not warning_fired[0]:
                warning_fired[0] = True
                on_token_warning(tracker)

        def on_compact_once(tracker: TokenUsage) -> None:
            if not compact_fired[0]:
                compact_fired[0] = True
                on_compact_needed(tracker)
                # Reset flag to allow another compact if needed
                compact_fired[0] = False

        token_tracker.on_warning = on_warning_once
        token_tracker.on_compact_needed = on_compact_once

        instrument_pool = config.get("instrument_pool") or config.get("instruments") or []
        if not instrument_pool and verbose:
            print(
                "警告: instrument_pool が空のため、演奏者名は自動生成します。",
                file=sys.stderr,
            )

        # Get permission settings and apply to commands
        permissions = config.get("permissions", {})

        rewriter_cfg = config.get("rewriter") or config.get("conductor") or {}
        concertmaster_cfg = config.get("concertmaster") or config.get("performer") or {}
        performer_cfg = config.get("performer") or {}
        max_turns = int(config.get("max_turns_performer", 3))

        # Apply permission flags to commands
        if rewriter_cfg.get("cmd"):
            rewriter_cfg = dict(rewriter_cfg)
            rewriter_cfg["cmd"] = apply_permission_flags(rewriter_cfg["cmd"], permissions)
        if concertmaster_cfg.get("cmd"):
            concertmaster_cfg = dict(concertmaster_cfg)
            concertmaster_cfg["cmd"] = apply_permission_flags(concertmaster_cfg["cmd"], permissions)
        if performer_cfg.get("cmd"):
            performer_cfg = dict(performer_cfg)
            performer_cfg["cmd"] = apply_permission_flags(performer_cfg["cmd"], permissions)

        # SSH Remote Execution Mode: override performer and concertmaster config
        ssh_exec_cfg = config.get("ssh_remote") or {}
        if ssh_exec_cfg.get("enabled"):
            ssh_executor_path = str(base_dir / "ssh_executor.py")
            agent_ssh_path = str(base_dir / "AGENT_SSH.md")

            # Override performer command to use ssh_executor.py
            performer_cfg = dict(performer_cfg)
            performer_cfg["cmd"] = [sys.executable, ssh_executor_path]

            # Override concertmaster system prompt to AGENT_SSH.md
            if concertmaster_cfg.get("cmd"):
                concertmaster_cfg = dict(concertmaster_cfg)
                new_cmd = []
                for part in concertmaster_cfg["cmd"]:
                    if part == "AGENT.md":
                        new_cmd.append(agent_ssh_path)
                    else:
                        new_cmd.append(part)
                concertmaster_cfg["cmd"] = new_cmd

            if verbose:
                print(
                    f"[SSHRemote] Performer mode: ssh_executor "
                    f"(host={ssh_exec_cfg.get('host', '?')})",
                    file=sys.stderr,
                )

        write_status(
            run_dir,
            {
                "stage": "rewriter",
                "progress": 0.05,
                "task": task,
            },
        )

        score = None
        score_source = "fallback"
        rewriter_result = run_external(
            rewriter_cfg.get("cmd", []),
            rewriter_prompt(task, instrument_pool),
            run_dir,
            "rewriter",
            rewriter_cfg.get("timeout_sec"),
            dry_run,
            token_tracker=token_tracker,
        )
        if rewriter_result["returncode"] == 0 and rewriter_result["stdout"].strip():
            try:
                score = extract_yaml(rewriter_result["stdout"])
                score_source = "rewriter"
            except Exception as exc:
                if verbose:
                    print(f"警告: 指揮者YAMLの解析に失敗: {exc}", file=sys.stderr)
        if not score:
            score = fallback_score(task, instrument_pool)

        raw_score = score
        score = normalize_score(raw_score, task, instrument_pool)
        assignments = normalize_assignments(score.get("instruments", []), verbose)
        score["instruments"] = assignments
        score["performers"] = assignments

        write_yaml(run_dir / "score.yaml", score)
        (run_dir / "score.json").write_text(
            json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if score_source == "rewriter":
            write_yaml(run_dir / "score_raw.yaml", raw_score)
        mix_with_conductor = bool(config.get("mix_with_conductor"))
        total_steps = max(len(assignments), 1) + 2
        completed_steps = 1
        write_status(
            run_dir,
            {
                "stage": "rewriter_done",
                "progress": completed_steps / total_steps,
                "task": task,
            },
        )

        exchanges_dir = run_dir / "exchanges"
        exchanges_dir.mkdir(parents=True, exist_ok=True)

        threads: list[threading.Thread] = []
        exchange_paths: list[Path | None] = [None] * len(assignments)
        exchange_locks: list[threading.Lock | None] = [None] * len(assignments)
        stop_events: list[threading.Event | None] = [None] * len(assignments)
        task_states = [
            {
                "index": idx,
                "id": inst.get("id") or f"task-{idx + 1}",
                "deps": inst.get("deps") or [],
                "status": "pending",
            }
            for idx, inst in enumerate(assignments)
        ]
        done_ids: set[str] = set()

        def deps_done(state: dict) -> bool:
            deps = state.get("deps") or []
            return all(dep in done_ids for dep in deps)

        def start_task(state: dict) -> None:
            idx = state["index"]
            inst = assignments[idx]
            exchange_path = exchanges_dir / f"exchange_{idx + 1}.yaml"
            init_exchange(exchange_path, inst)
            exchange_paths[idx] = exchange_path
            lock = threading.Lock()
            exchange_locks[idx] = lock
            stop_event = threading.Event()
            stop_events[idx] = stop_event

            cm_thread = threading.Thread(
                target=concertmaster_worker,
                name=f"concertmaster-{idx + 1}",
                args=(
                    exchange_path,
                    inst,
                    score.get("refined_task", task),
                    score.get("global_notes", ""),
                    concertmaster_cfg.get("cmd", []),
                    concertmaster_cfg.get("timeout_sec"),
                    run_dir,
                    f"concertmaster_{idx + 1}",
                    lock,
                    stop_event,
                    verbose,
                    max_turns,
                    dry_run,
                    token_tracker,
                ),
            )
            perf_thread = threading.Thread(
                target=performer_worker,
                name=f"performer-{idx + 1}",
                args=(
                    exchange_path,
                    inst,
                    performer_cfg.get("cmd", []),
                    performer_cfg.get("timeout_sec"),
                    run_dir,
                    f"performer_{idx + 1}",
                    lock,
                    stop_event,
                    max_turns,
                    dry_run,
                    token_tracker,
                ),
            )
            threads.extend([cm_thread, perf_thread])
            cm_thread.start()
            perf_thread.start()
            state["status"] = "running"

        # Monitor progress and schedule only ready tasks
        while True:
            # Start ready tasks
            for state in task_states:
                if state["status"] == "pending" and deps_done(state):
                    start_task(state)

            # Update completion counts
            done_count = 0
            running_count = 0
            for state in task_states:
                idx = state["index"]
                path = exchange_paths[idx]
                if state["status"] == "running" and path is not None:
                    data = read_exchange(path)
                    if data.get("status") == "done":
                        state["status"] = "done"
                        done_ids.add(state["id"])
                    elif data.get("status") == "error":
                        state["status"] = "error"
                if state["status"] == "done":
                    done_count += 1
                if state["status"] == "running":
                    running_count += 1

            completed_steps = 1 + done_count
            write_status(
                run_dir,
                {
                    "stage": "performer",
                    "progress": min(completed_steps / total_steps, 0.95),
                    "task": task,
                    "performer_index": done_count,
                    "performer_total": len(assignments),
                },
            )

            if done_count >= len(assignments):
                break

            pending_count = sum(1 for state in task_states if state["status"] == "pending")
            if running_count == 0 and pending_count == 0:
                break
            if running_count == 0 and pending_count > 0:
                # Deadlock: pending tasks exist but none are ready
                if verbose:
                    print("警告: 依存関係の循環により実行できないタスクがあります。", file=sys.stderr)
                break

            time.sleep(1.5)

        for t in threads:
            t.join()

        performances: list[dict] = []
        for idx, inst in enumerate(assignments, start=1):
            exchange_path = exchange_paths[idx - 1]
            data = read_exchange(exchange_path) if exchange_path else {}
            output = get_last_message(data, "performer") or ""
            performances.append({"instrument": inst.get("name") or f"Instrument-{idx}", "output": output})

        if mix_with_conductor:
            write_status(
                run_dir,
                {
                    "stage": "mix",
                    "progress": completed_steps / total_steps,
                    "task": task,
                },
            )
            mix_result = run_external(
                rewriter_cfg.get("cmd", []),
                mix_prompt(score, performances),
                run_dir,
                "mix",
                rewriter_cfg.get("timeout_sec"),
                dry_run,
                token_tracker=token_tracker,
            )
            final_text = mix_result["stdout"].strip()
            completed_steps += 1
            write_status(
                run_dir,
                {
                    "stage": "mix_done",
                    "progress": completed_steps / total_steps,
                    "task": task,
                },
            )
        else:
            final_text = local_mix(score, performances)

        (run_dir / "final.txt").write_text(final_text, encoding="utf-8")

        # Save token usage statistics
        (run_dir / "token_usage.json").write_text(
            json.dumps(token_tracker.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        if verbose:
            print(f"[TokenManager] 最終: {token_tracker.status_message()}", file=sys.stderr)

        (run_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "task": task,
                    "run_dir": str(run_dir),
                    "dry_run": dry_run,
                    "score_source": score_source,
                    "timestamp": dt.datetime.now().isoformat(),
                    "token_usage_summary": {
                        "total_combined": token_tracker.total_combined,
                        "call_count": token_tracker.call_count,
                        "usage_ratio": round(token_tracker.usage_ratio(), 4),
                    },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
        )

        completed_steps += 1
        write_status(
            run_dir,
            {
                "stage": "done",
                "progress": min(completed_steps / total_steps, 1.0),
                "task": task,
                "result_file": str(run_dir / "final.txt"),
            },
        )

        print(final_text)
        print(f"\n保存先: {run_dir}")
        return 0
    except Exception as exc:
        write_status(
            run_dir,
            {
                "stage": "error",
                "progress": 1.0,
                "task": task,
                "error": str(exc),
            },
        )
        print(f"エラー: {exc}", file=sys.stderr)
        return 1
    finally:
        # Tear down SSH remote filesystem
        if _ssh_remote_active and teardown_remote is not None:
            try:
                td_ok, td_msg = teardown_remote(config)
                if verbose:
                    print(f"[SSHRemote] teardown: {td_msg}", file=sys.stderr)
            except Exception as td_exc:
                print(f"[SSHRemote] teardown error: {td_exc}", file=sys.stderr)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Claude Codeを指揮者、Codexを演奏者として協調させるCLI。",
    )
    parser.add_argument(
        "--task",
        help="実行したいタスク（未指定なら標準入力から読み込み）",
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="設定ファイルのパス（既定: config.json）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="外部コマンドを実行せず、プロンプト生成のみ行う",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="詳細ログを標準エラーに出力",
    )
    parser.add_argument(
        "--run-dir",
        help="実行結果の出力先ディレクトリ（未指定なら自動生成）",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    task = args.task
    if not task:
        task = sys.stdin.read().strip()
    if not task:
        print("エラー: task が空です。", file=sys.stderr)
        return 2
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        print(f"エラー: 設定ファイルが見つかりません: {config_path}", file=sys.stderr)
        return 2
    run_dir = Path(args.run_dir).expanduser().resolve() if args.run_dir else None
    return run(task, config_path, args.dry_run, args.verbose, run_dir)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
