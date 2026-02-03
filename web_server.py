#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import threading
import uuid
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "runs"
WEB_DIR = ROOT / "web"
CONFIG_PATH = ROOT / "config.json"
CORS_ORIGIN: str | None = None
API_TOKEN: str | None = None

# Default stall timeout in seconds (no log updates for this long = stalled)
DEFAULT_STALL_TIMEOUT_SEC = 120
# Default stall-to-error timeout in seconds (stalled for this long = error)
DEFAULT_STALL_ERROR_TIMEOUT_SEC = 600

try:
    import yaml
except Exception:
    yaml = None

_jobs_lock = threading.Lock()
_active_jobs: dict[str, dict] = {}


def now_iso() -> str:
    return dt.datetime.now().isoformat()


def safe_json_load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_yaml_load(path: Path) -> dict:
    if yaml is None:
        return {}
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def read_config() -> dict:
    """Read the orchestrator config file."""
    if not CONFIG_PATH.exists():
        return {}
    return safe_json_load(CONFIG_PATH)


def get_cli_token_status() -> dict:
    """Get token status from Claude and Codex CLIs.

    For Claude Code, uses ccusage to get 5-hour block data and calculates usage percentage.
    For Codex, reads rate limits from ~/.codex/sessions/**/*.jsonl

    The 5-hour block percentage is calculated relative to historical max usage,
    which provides a practical estimate of how close to the rate limit you are.
    """
    import os

    result = {
        "claude": {
            "available": False,
            "raw_output": "",
            "error": None,
            "used_percentage": None,
            "short_term_percentage": None,
            "weekly_percentage": None,
            "rate_limit_5h": None,
            "weekly_token_limit": None,
            "daily_tokens": None,
            "weekly_tokens": None,
            "total_tokens": None,
        },
        "codex": {
            "available": False,
            "raw_output": "",
            "error": None,
            "used_percentage": None,
            "short_term_percentage": None,
            "weekly_percentage": None,
            "rate_limit_5h": None,
            "weekly_token_limit": None,
        },
    }

    # Check Claude Code token usage using ccusage
    try:
        # Get all blocks to find historical max and active block
        proc = subprocess.run(
            ["npx", "ccusage@latest", "blocks", "--json"],
            text=True,
            capture_output=True,
            timeout=30,
            env=os.environ.copy(),
        )
        if proc.returncode == 0 and proc.stdout:
            blocks_data = json.loads(proc.stdout)
            blocks = blocks_data.get("blocks", [])

            if blocks:
                result["claude"]["available"] = True

                # Find active block and historical max
                active_block = None
                max_tokens = 0
                for block in blocks:
                    if block.get("isGap"):
                        continue
                    total = block.get("totalTokens", 0)
                    if total > max_tokens:
                        max_tokens = total
                    if block.get("isActive"):
                        active_block = block

                if active_block:
                    current_tokens = active_block.get("totalTokens", 0)
                    result["claude"]["daily_tokens"] = current_tokens

                    # Calculate percentage relative to historical max
                    if max_tokens > 0:
                        pct = round((current_tokens / max_tokens) * 100, 1)
                        result["claude"]["short_term_percentage"] = pct
                        result["claude"]["used_percentage"] = pct

                    # Get block end time for reset info
                    end_time_str = active_block.get("endTime", "")
                    reset_info = ""
                    if end_time_str:
                        try:
                            end_time = dt.datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
                            local_end = end_time.astimezone()
                            reset_info = f" (リセット: {local_end.strftime('%H:%M')})"
                        except (ValueError, TypeError):
                            pass

                    if max_tokens > 0:
                        pct = round((current_tokens / max_tokens) * 100, 1)
                        result["claude"]["rate_limit_5h"] = f"{pct}%{reset_info}"

                    # Build raw output
                    lines = []
                    lines.append(f"5時間ブロック: {current_tokens:,} トークン")
                    if max_tokens > 0:
                        lines.append(f"過去最大: {max_tokens:,} トークン")
                    projection = active_block.get("projection", {})
                    if projection.get("totalTokens"):
                        lines.append(f"予測: {projection['totalTokens']:,} トークン")
                    result["claude"]["raw_output"] = "\n".join(lines)

        # Also get weekly data from ccusage
        proc_daily = subprocess.run(
            ["npx", "ccusage@latest", "--json"],
            text=True,
            capture_output=True,
            timeout=30,
            env=os.environ.copy(),
        )
        if proc_daily.returncode == 0 and proc_daily.stdout:
            daily_data = json.loads(proc_daily.stdout)
            daily_entries = daily_data.get("daily", [])

            # Sum tokens for last 7 days
            week_ago = (dt.date.today() - dt.timedelta(days=7)).isoformat()
            weekly_tokens = 0
            for entry in daily_entries:
                if entry.get("date", "") >= week_ago:
                    weekly_tokens += entry.get("totalTokens", 0)

            if weekly_tokens > 0:
                result["claude"]["weekly_tokens"] = weekly_tokens

                # Calculate total from all daily entries
                total_tokens = sum(e.get("totalTokens", 0) for e in daily_entries)
                result["claude"]["total_tokens"] = total_tokens

                # For weekly percentage, use a rough estimate
                # Claude Pro weekly limit is approximately 50-100M tokens based on usage patterns
                # We'll use the sum of historical max blocks * 7 as a rough weekly limit
                if max_tokens > 0:
                    # Estimate: if you could hit max every 5h block, ~33 blocks/week
                    estimated_weekly_limit = max_tokens * 33
                    weekly_pct = round((weekly_tokens / estimated_weekly_limit) * 100, 1)
                    result["claude"]["weekly_percentage"] = weekly_pct
                    result["claude"]["weekly_token_limit"] = f"{weekly_pct}% ({weekly_tokens:,} トークン)"

        if not result["claude"]["available"]:
            # Fallback: check if claude command is available
            proc = subprocess.run(
                ["claude", "--version"],
                text=True,
                capture_output=True,
                timeout=10,
                env=os.environ.copy(),
            )
            if proc.returncode == 0:
                result["claude"]["available"] = True
                result["claude"]["raw_output"] = "ccusage データなし"
            else:
                result["claude"]["error"] = "claude コマンドが見つかりません"
    except FileNotFoundError:
        result["claude"]["error"] = "ccusage が見つかりません (npx ccusage@latest)"
    except json.JSONDecodeError:
        result["claude"]["error"] = "ccusage の出力を解析できませんでした"
    except subprocess.TimeoutExpired:
        result["claude"]["error"] = "タイムアウト"
    except Exception as e:
        result["claude"]["error"] = str(e)

    # Check Codex token usage from session files
    try:
        codex_sessions_dir = Path.home() / ".codex" / "sessions"
        if codex_sessions_dir.exists():
            # Find the most recent session file
            session_files = list(codex_sessions_dir.glob("**/*.jsonl"))
            if session_files:
                # Sort by modification time to get the most recent
                session_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                latest_session = session_files[0]

                # Read the session file and find the last rate_limits info
                rate_limits = None
                token_usage = None
                with open(latest_session, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            if data.get("type") == "event_msg":
                                payload = data.get("payload", {})
                                if payload.get("type") == "token_count":
                                    info = payload.get("info") or {}
                                    if "rate_limits" in payload:
                                        rate_limits = payload["rate_limits"]
                                    if info and "total_token_usage" in info:
                                        token_usage = info["total_token_usage"]
                        except json.JSONDecodeError:
                            continue

                if rate_limits:
                    result["codex"]["available"] = True
                    primary = rate_limits.get("primary", {})
                    secondary = rate_limits.get("secondary", {})

                    # Primary: 5-hour rate limit
                    primary_pct = primary.get("used_percent")
                    if primary_pct is not None:
                        result["codex"]["rate_limit_5h"] = f"{primary_pct}%"
                        resets_at = primary.get("resets_at")
                        if resets_at:
                            reset_time = dt.datetime.fromtimestamp(resets_at)
                            result["codex"]["rate_limit_5h"] += f" (リセット: {reset_time.strftime('%H:%M')})"

                    # Secondary: weekly rate limit
                    secondary_pct = secondary.get("used_percent")
                    if secondary_pct is not None:
                        result["codex"]["weekly_token_limit"] = f"{secondary_pct}%"
                        resets_at = secondary.get("resets_at")
                        if resets_at:
                            reset_time = dt.datetime.fromtimestamp(resets_at)
                            result["codex"]["weekly_token_limit"] += f" (リセット: {reset_time.strftime('%m/%d %H:%M')})"

                    # Set both short-term and weekly percentages
                    if primary_pct is not None:
                        result["codex"]["used_percentage"] = primary_pct
                        result["codex"]["short_term_percentage"] = primary_pct
                    if secondary_pct is not None:
                        result["codex"]["weekly_percentage"] = secondary_pct

                    # Build raw output
                    lines = []
                    if primary_pct is not None:
                        lines.append(f"5時間制限: {primary_pct}%")
                    if secondary_pct is not None:
                        lines.append(f"週間制限: {secondary_pct}%")
                    if token_usage:
                        total = token_usage.get("total_tokens", 0)
                        lines.append(f"セッショントークン: {total:,}")
                    result["codex"]["raw_output"] = "\n".join(lines) if lines else "利用可能"
                else:
                    result["codex"]["available"] = True
                    result["codex"]["raw_output"] = "セッションデータなし"
            else:
                result["codex"]["available"] = True
                result["codex"]["raw_output"] = "セッション履歴なし"
        else:
            # Fallback: check if codex command exists
            proc = subprocess.run(
                ["codex", "--version"],
                text=True,
                capture_output=True,
                timeout=10,
                env=os.environ.copy(),
            )
            if proc.returncode == 0:
                result["codex"]["available"] = True
                result["codex"]["raw_output"] = proc.stdout.strip() if proc.stdout else "利用可能"
            else:
                result["codex"]["error"] = proc.stderr.strip() if proc.stderr else "codex コマンドが見つかりません"
    except FileNotFoundError:
        result["codex"]["error"] = "codex コマンドが見つかりません"
    except subprocess.TimeoutExpired:
        result["codex"]["error"] = "タイムアウト"
    except Exception as e:
        result["codex"]["error"] = str(e)

    return result


def write_config(config: dict) -> None:
    """Write the orchestrator config file with backup."""
    # Create backup
    if CONFIG_PATH.exists():
        backup_path = CONFIG_PATH.with_suffix(".json.bak")
        backup_path.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    # Write new config
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_status(run_dir: Path) -> dict:
    status = safe_json_load(run_dir / "status.json")
    meta = safe_json_load(run_dir / "metadata.json")
    if meta.get("task") and not status.get("task"):
        status["task"] = meta["task"]
    if meta.get("timestamp") and not status.get("started_at"):
        status["started_at"] = meta["timestamp"]
    return status


def get_last_log_update(run_dir: Path) -> tuple[str | None, float | None]:
    """Get the most recent log file modification time.

    Returns:
        Tuple of (ISO timestamp string, seconds since last update) or (None, None) if no logs.
    """
    latest_mtime: float | None = None

    # Check all log files
    log_patterns = [
        "conductor_stdout.txt", "conductor_stderr.txt",
        "rewriter_stdout.txt", "rewriter_stderr.txt",
        "mix_stdout.txt", "mix_stderr.txt",
        "performer_*_stdout.txt", "performer_*_stderr.txt",
        "concertmaster_*_stdout.txt", "concertmaster_*_stderr.txt",
    ]

    for pattern in log_patterns:
        for path in run_dir.glob(pattern):
            if path.exists():
                mtime = path.stat().st_mtime
                if latest_mtime is None or mtime > latest_mtime:
                    latest_mtime = mtime

    # Also check status.json for updates
    status_path = run_dir / "status.json"
    if status_path.exists():
        mtime = status_path.stat().st_mtime
        if latest_mtime is None or mtime > latest_mtime:
            latest_mtime = mtime

    if latest_mtime is None:
        return None, None

    import time
    last_update_iso = dt.datetime.fromtimestamp(latest_mtime).isoformat()
    seconds_since_update = time.time() - latest_mtime
    return last_update_iso, seconds_since_update


def get_run_summary(run_dir: Path, process: subprocess.Popen | None = None) -> dict:
    status = read_status(run_dir)
    final_path = run_dir / "final.txt"

    # Get last log update info
    last_log_update, seconds_since_update = get_last_log_update(run_dir)

    # Read stall timeout from config
    config = read_config()
    stall_timeout = config.get("stall_timeout_sec", DEFAULT_STALL_TIMEOUT_SEC)
    stall_error_timeout = config.get("stall_error_timeout_sec", DEFAULT_STALL_ERROR_TIMEOUT_SEC)

    summary = {
        "id": run_dir.name,
        "run_dir": str(run_dir),
        "task": status.get("task", ""),
        "stage": status.get("stage", "unknown"),
        "progress": status.get("progress", 0.0),
        "updated_at": status.get("updated_at"),
        "started_at": status.get("started_at"),
        "result_file": status.get("result_file"),
        "error": status.get("error"),
        # Performer tracking fields
        "performer_index": status.get("performer_index"),
        "performer_total": status.get("performer_total"),
        "performer_name": status.get("performer_name"),
        # Log tracking fields
        "last_log_update": last_log_update,
        "seconds_since_log_update": int(seconds_since_update) if seconds_since_update is not None else None,
    }

    is_running = False
    if process is not None:
        summary["pid"] = process.pid
        is_running = process.poll() is None
        summary["returncode"] = process.poll()

    # Detect stalled job: process finished but stage not terminal, or no updates for too long
    is_terminal = status.get("stage") in ("done", "error", "killed", "stalled")
    is_stalled = False

    if not is_terminal:
        # Check if process died but stage wasn't updated
        if process is not None and not is_running:
            is_stalled = True
        # Check if no log updates for stall_timeout seconds
        elif seconds_since_update is not None and seconds_since_update > stall_timeout:
            is_stalled = True

    if is_stalled and not is_terminal:
        # Check if stalled long enough to be considered an error
        if seconds_since_update is not None and seconds_since_update > stall_error_timeout:
            summary["stage"] = "error"
            summary["stalled"] = True
            minutes = int(seconds_since_update // 60)
            summary["error"] = f"ジョブがエラーになりました（{minutes}分間更新なし）"
        else:
            summary["stage"] = "stalled"
            summary["stalled"] = True
            if not summary.get("error"):
                if seconds_since_update is not None:
                    minutes = int(seconds_since_update // 60)
                    summary["error"] = f"ジョブが停滞しました（{minutes}分間更新なし）"
                else:
                    summary["error"] = "ジョブが途中で停止しました"
        # Mark as not running since it's stalled
        is_running = False

    summary["running"] = is_running

    if final_path.exists():
        summary["has_result"] = True
    return summary


def get_score(run_dir: Path) -> dict | None:
    """Load score.json which contains performer assignments."""
    score_path = run_dir / "score.json"
    if score_path.exists():
        return safe_json_load(score_path)
    return None


def list_logs(run_dir: Path) -> list[dict]:
    """List available log files in the run directory."""
    logs = []
    log_patterns = [
        ("conductor_stdout.txt", "conductor", "stdout"),
        ("conductor_stderr.txt", "conductor", "stderr"),
        ("rewriter_stdout.txt", "rewriter", "stdout"),
        ("rewriter_stderr.txt", "rewriter", "stderr"),
        ("mix_stdout.txt", "mix", "stdout"),
        ("mix_stderr.txt", "mix", "stderr"),
    ]
    for filename, stage, log_type in log_patterns:
        path = run_dir / filename
        if path.exists():
            logs.append({
                "filename": filename,
                "stage": stage,
                "type": log_type,
                "size": path.stat().st_size,
            })
    # Find performer logs
    for path in sorted(run_dir.glob("performer_*_stdout.txt")):
        idx = path.name.replace("performer_", "").replace("_stdout.txt", "")
        idx = idx.split("_")[0]
        logs.append({
            "filename": path.name,
            "stage": f"performer_{idx}",
            "type": "stdout",
            "size": path.stat().st_size,
        })
    for path in sorted(run_dir.glob("performer_*_stderr.txt")):
        idx = path.name.replace("performer_", "").replace("_stderr.txt", "")
        idx = idx.split("_")[0]
        logs.append({
            "filename": path.name,
            "stage": f"performer_{idx}",
            "type": "stderr",
            "size": path.stat().st_size,
        })
    # Find concertmaster logs
    for path in sorted(run_dir.glob("concertmaster_*_stdout.txt")):
        idx = path.name.replace("concertmaster_", "").replace("_stdout.txt", "")
        idx = idx.split("_")[0]
        logs.append({
            "filename": path.name,
            "stage": f"concertmaster_{idx}",
            "type": "stdout",
            "size": path.stat().st_size,
        })
    for path in sorted(run_dir.glob("concertmaster_*_stderr.txt")):
        idx = path.name.replace("concertmaster_", "").replace("_stderr.txt", "")
        idx = idx.split("_")[0]
        logs.append({
            "filename": path.name,
            "stage": f"concertmaster_{idx}",
            "type": "stderr",
            "size": path.stat().st_size,
        })
    return logs


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


def normalize_pending_for_api(pending: dict) -> dict:
    """APIレスポンス用にpendingを正規化。質問文から選択肢を自動検出。"""
    if not pending:
        return pending
    
    pending = dict(pending)  # コピーを作成
    options = pending.get("options") or []
    question = pending.get("question") or ""
    pending_type = (pending.get("type") or "ok_ng").strip().lower()
    
    # optionsが空で、質問文に選択肢が含まれている場合は自動検出
    if not options and question:
        extracted = extract_choices_from_question(question)
        if extracted:
            pending["options"] = extracted
            # タイプも choice に変更
            if pending_type not in ("choice", "free_text"):
                pending["type"] = "choice"
    
    return pending


def list_exchanges(run_dir: Path) -> list[dict]:
    exchanges_dir = run_dir / "exchanges"
    if not exchanges_dir.exists():
        return []
    items = []
    for path in sorted(exchanges_dir.glob("exchange_*.yaml")):
        data = safe_yaml_load(path)
        pending = data.get("pending") or {}
        # 質問文から選択肢を自動検出（optionsが空の場合）
        pending = normalize_pending_for_api(pending)
        items.append(
            {
                "id": path.stem.replace("exchange_", ""),
                "filename": path.name,
                "status": data.get("status"),
                "updated_at": data.get("updated_at"),
                "performer": (data.get("performer") or {}),
                "pending": pending,
            }
        )
    return items


def read_exchange(run_dir: Path, exchange_id: str) -> dict | None:
    exchanges_dir = run_dir / "exchanges"
    path = exchanges_dir / f"exchange_{exchange_id}.yaml"
    if not path.exists():
        return None
    return safe_yaml_load(path)


def update_exchange_reply(
    run_dir: Path,
    exchange_id: str,
    reply: str,
    approved: bool,
    choice: str | None = None,
) -> dict | None:
    if yaml is None:
        return None
    exchanges_dir = run_dir / "exchanges"
    path = exchanges_dir / f"exchange_{exchange_id}.yaml"
    if not path.exists():
        return None
    data = safe_yaml_load(path)
    pending = data.get("pending") or {}
    pending["user_reply"] = reply
    if choice:
        pending["user_choice"] = choice
    pending["user_approved"] = bool(approved)
    data["pending"] = pending
    data["updated_at"] = now_iso()
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return data


def read_log_file(run_dir: Path, filename: str) -> str | None:
    """Read a specific log file safely."""
    # Only allow known log file patterns
    allowed_patterns = [
        "conductor_stdout.txt", "conductor_stderr.txt", "conductor_prompt.txt",
        "rewriter_stdout.txt", "rewriter_stderr.txt", "rewriter_prompt.txt",
        "mix_stdout.txt", "mix_stderr.txt", "mix_prompt.txt",
    ]
    if filename in allowed_patterns:
        path = run_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    # Check performer log patterns
    import re
    if re.match(r"^performer_\d+_\d+_(stdout|stderr|prompt)\.txt$", filename):
        path = run_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    if re.match(r"^performer_\d+_(stdout|stderr|prompt)\.txt$", filename):
        path = run_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    if re.match(r"^concertmaster_\d+_\d+_(stdout|stderr|prompt)\.txt$", filename):
        path = run_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None
    if re.match(r"^concertmaster_\d+_(stdout|stderr|prompt)\.txt$", filename):
        path = run_dir / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        return None


def list_runs() -> list[dict]:
    summaries: list[dict] = []
    seen = set()
    with _jobs_lock:
        for job_id, job in _active_jobs.items():
            summaries.append(get_run_summary(Path(job["run_dir"]), job["process"]))
            seen.add(job_id)

    if RUNS_DIR.exists():
        for run_dir in sorted(RUNS_DIR.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            if run_dir.name in seen:
                continue
            summaries.append(get_run_summary(run_dir))
    return summaries


def start_job(task: str, config_path: Path | None) -> dict:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_id = f"{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cfg = config_path or (ROOT / "config.json")
    if not cfg.exists():
        raise FileNotFoundError(f"設定ファイルが見つかりません: {cfg}")
    cmd = [
        sys.executable,
        str(ROOT / "orchestrator.py"),
        "--task",
        task,
        "--config",
        str(cfg),
        "--run-dir",
        str(run_dir),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    with _jobs_lock:
        _active_jobs[run_id] = {
            "process": proc,
            "run_dir": str(run_dir),
            "task": task,
            "started_at": now_iso(),
        }
    return get_run_summary(run_dir, proc)


def cleanup_finished_jobs() -> None:
    with _jobs_lock:
        done = [job_id for job_id, job in _active_jobs.items() if job["process"].poll() is not None]
        for job_id in done:
            _active_jobs.pop(job_id, None)


def kill_job(job_id: str) -> dict:
    """Forcefully terminate a running job process."""
    with _jobs_lock:
        job = _active_jobs.get(job_id)
        if not job:
            return {"ok": False, "error": "Job not found or not running"}

        process = job["process"]
        if process.poll() is not None:
            return {"ok": False, "error": "Job already finished"}

        import signal
        try:
            # First try SIGTERM for graceful shutdown
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # If still running, force kill with SIGKILL
                process.kill()
                process.wait(timeout=2)

            # Update status file to indicate killed
            run_dir = Path(job["run_dir"])
            status_path = run_dir / "status.json"
            if status_path.exists():
                try:
                    status = json.loads(status_path.read_text(encoding="utf-8"))
                except Exception:
                    status = {}
                status["stage"] = "killed"
                status["error"] = "ユーザーによって強制終了されました"
                status["updated_at"] = now_iso()
                status_path.write_text(
                    json.dumps(status, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )

            # Remove from active jobs
            _active_jobs.pop(job_id, None)
            return {"ok": True, "message": "Job terminated"}
        except Exception as e:
            return {"ok": False, "error": f"Failed to kill process: {e}"}


class OrchestratorHandler(BaseHTTPRequestHandler):
    server_version = "OrchestratorHTTP/1.0"

    def add_cors_headers(self) -> None:
        if not CORS_ORIGIN:
            return
        origin = self.headers.get("Origin")
        if CORS_ORIGIN == "*" or (origin and origin == CORS_ORIGIN):
            self.send_header("Access-Control-Allow-Origin", origin or "*")
            self.send_header("Vary", "Origin")

    def require_token(self) -> bool:
        if not API_TOKEN:
            return True
        token = self.headers.get("X-Orchestrator-Token")
        return bool(token and token == API_TOKEN)

    def do_OPTIONS(self) -> None:
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/"):
            self.send_response(HTTPStatus.NO_CONTENT)
            self.add_cors_headers()
            self.end_headers()
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self.add_cors_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Orchestrator-Token")
        self.send_header("Access-Control-Max-Age", "3600")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self.serve_static(WEB_DIR / "index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self.serve_static(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self.serve_static(WEB_DIR / "styles.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/config.js":
            self.serve_static(WEB_DIR / "config.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/api/config":
            self.send_json(read_config())
            return
        if parsed.path == "/api/token-status":
            self.send_json(get_cli_token_status())
            return
        if parsed.path == "/api/jobs":
            cleanup_finished_jobs()
            self.send_json(list_runs())
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.split("/api/jobs/")[1].strip("/")
            if job_id.endswith("/final"):
                job_id = job_id.rsplit("/final", 1)[0].strip("/")
                self.send_final(job_id)
                return
            if job_id.endswith("/exchanges"):
                job_id = job_id.rsplit("/exchanges", 1)[0].strip("/")
                self.send_exchanges(job_id)
                return
            if "/exchanges/" in job_id:
                parts = job_id.split("/exchanges/")
                job_id = parts[0].strip("/")
                exchange_id = parts[1].strip("/")
                self.send_exchange(job_id, exchange_id)
                return
            if "/score" in job_id:
                job_id = job_id.rsplit("/score", 1)[0].strip("/")
                self.send_score(job_id)
                return
            if "/logs/" in job_id:
                parts = job_id.split("/logs/")
                job_id = parts[0].strip("/")
                filename = parts[1].strip("/") if len(parts) > 1 else ""
                self.send_log_file(job_id, filename)
                return
            if job_id.endswith("/logs"):
                job_id = job_id.rsplit("/logs", 1)[0].strip("/")
                self.send_logs_list(job_id)
                return
            self.send_job(job_id, parsed)
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/jobs/") and "/exchanges/" in parsed.path and parsed.path.endswith("/reply"):
            self.handle_exchange_reply(parsed)
            return
        if parsed.path.startswith("/api/jobs/") and parsed.path.endswith("/kill"):
            self.handle_job_kill(parsed)
            return
        if parsed.path == "/api/config":
            self.handle_config_update()
            return
        if parsed.path != "/api/jobs":
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        if not self.require_token():
            self.send_error(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        task = str(payload.get("task", "")).strip()
        if not task:
            self.send_error(HTTPStatus.BAD_REQUEST, "task is required")
            return
        cfg = payload.get("config")
        config_path = Path(cfg).expanduser().resolve() if cfg else None
        try:
            job = start_job(task, config_path)
            self.send_json(job, status=HTTPStatus.CREATED)
        except FileNotFoundError as exc:
            self.send_error(HTTPStatus.BAD_REQUEST, str(exc))

    def send_job(self, job_id: str, parsed) -> None:
        cleanup_finished_jobs()
        run_dir = RUNS_DIR / job_id
        if not run_dir.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return
        # Check if this job is active and get its process
        with _jobs_lock:
            job_info = _active_jobs.get(job_id)
            process = job_info["process"] if job_info else None
        status = get_run_summary(run_dir, process)
        query = parse_qs(parsed.query)
        include = query.get("include_output", ["0"])[0] == "1"
        if include:
            final_path = run_dir / "final.txt"
            if final_path.exists():
                status["final_text"] = final_path.read_text(encoding="utf-8")
        self.send_json(status)

    def send_final(self, job_id: str) -> None:
        run_dir = RUNS_DIR / job_id
        final_path = run_dir / "final.txt"
        if not final_path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "final.txt not found")
            return
        data = final_path.read_text(encoding="utf-8")
        self.send_response(HTTPStatus.OK)
        self.add_cors_headers()
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data.encode("utf-8"))))
        self.end_headers()
        self.wfile.write(data.encode("utf-8"))

    def send_score(self, job_id: str) -> None:
        run_dir = RUNS_DIR / job_id
        if not run_dir.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return
        score = get_score(run_dir)
        if score is None:
            self.send_error(HTTPStatus.NOT_FOUND, "score.json not found")
            return
        self.send_json(score)

    def send_logs_list(self, job_id: str) -> None:
        run_dir = RUNS_DIR / job_id
        if not run_dir.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return
        logs = list_logs(run_dir)
        self.send_json(logs)

    def send_exchanges(self, job_id: str) -> None:
        run_dir = RUNS_DIR / job_id
        if not run_dir.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return
        exchanges = list_exchanges(run_dir)
        self.send_json(exchanges)

    def send_exchange(self, job_id: str, exchange_id: str) -> None:
        run_dir = RUNS_DIR / job_id
        if not run_dir.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return
        data = read_exchange(run_dir, exchange_id)
        if data is None:
            self.send_error(HTTPStatus.NOT_FOUND, "exchange not found")
            return
        self.send_json(data)

    def handle_exchange_reply(self, parsed) -> None:
        if not self.require_token():
            self.send_error(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            return
        path = parsed.path
        try:
            _, after = path.split("/api/jobs/", 1)
            job_part, rest = after.split("/exchanges/", 1)
            exchange_id = rest.rsplit("/reply", 1)[0].strip("/")
            job_id = job_part.strip("/")
        except ValueError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid exchange path")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return
        decision = str(payload.get("decision", "")).strip().lower()
        choice = str(payload.get("choice", "")).strip()
        reply = str(payload.get("reply", "")).strip()
        approved_raw = payload.get("approved", None)
        approved = None

        if isinstance(approved_raw, bool):
            approved = approved_raw

        if decision:
            ok = decision in ("ok", "yes", "y", "true", "1", "承認")
            approved = ok
            reply = "OK" if ok else "NG"

        if choice:
            reply = choice
            if approved is None:
                approved = True

        if approved is None:
            approved = False

        updated = update_exchange_reply(RUNS_DIR / job_id, exchange_id, reply, approved, choice or None)
        if updated is None:
            self.send_error(HTTPStatus.NOT_FOUND, "exchange not found")
            return
        self.send_json({"ok": True})

    def handle_job_kill(self, parsed) -> None:
        """Handle POST /api/jobs/{id}/kill to forcefully terminate a job."""
        if not self.require_token():
            self.send_error(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            return

        # Extract job_id from path
        path = parsed.path
        try:
            job_id = path.split("/api/jobs/")[1].rsplit("/kill", 1)[0].strip("/")
        except (IndexError, ValueError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid job path")
            return

        result = kill_job(job_id)
        if result.get("ok"):
            self.send_json(result)
        else:
            self.send_error(HTTPStatus.BAD_REQUEST, result.get("error", "Failed to kill job"))

    def handle_config_update(self) -> None:
        """Handle POST /api/config to update orchestrator settings."""
        if not self.require_token():
            self.send_error(HTTPStatus.UNAUTHORIZED, "Unauthorized")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        body = self.rfile.read(length) if length else b""
        try:
            new_config = json.loads(body.decode("utf-8")) if body else {}
        except json.JSONDecodeError:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON")
            return

        if not isinstance(new_config, dict):
            self.send_error(HTTPStatus.BAD_REQUEST, "Config must be a JSON object")
            return

        # Validate required fields
        required_sections = ["rewriter", "concertmaster", "performer"]
        for section in required_sections:
            if section in new_config and not isinstance(new_config.get(section), dict):
                self.send_error(HTTPStatus.BAD_REQUEST, f"{section} must be an object")
                return

        # Validate token_management if present
        token_mgmt = new_config.get("token_management")
        if token_mgmt is not None:
            if not isinstance(token_mgmt, dict):
                self.send_error(HTTPStatus.BAD_REQUEST, "token_management must be an object")
                return
            # Validate threshold values
            for key in ["warning_threshold", "compact_threshold"]:
                if key in token_mgmt:
                    val = token_mgmt[key]
                    if not isinstance(val, (int, float)) or val < 0 or val > 1:
                        self.send_error(HTTPStatus.BAD_REQUEST, f"{key} must be between 0 and 1")
                        return
            # Validate integer values
            for key in ["max_tokens", "max_compact_attempts"]:
                if key in token_mgmt:
                    val = token_mgmt[key]
                    if not isinstance(val, int) or val < 0:
                        self.send_error(HTTPStatus.BAD_REQUEST, f"{key} must be a positive integer")
                        return

        try:
            write_config(new_config)
            self.send_json({"ok": True, "config": new_config})
        except Exception as e:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, f"Failed to write config: {e}")

    def send_log_file(self, job_id: str, filename: str) -> None:
        run_dir = RUNS_DIR / job_id
        if not run_dir.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Job not found")
            return
        content = read_log_file(run_dir, filename)
        if content is None:
            self.send_error(HTTPStatus.NOT_FOUND, "Log file not found")
            return
        data = content.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.add_cors_headers()
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def serve_static(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND, "Not Found")
            return
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.add_cors_headers()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.add_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_error(self, code: int, message: str | None = None, explain=None) -> None:
        payload = {"error": message or HTTPStatus(code).phrase}
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.add_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args) -> None:
        return


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OrchestratorのWeb UI")
    parser.add_argument("--host", default="127.0.0.1", help="バインドするホスト")
    parser.add_argument("--port", type=int, default=8088, help="ポート番号")
    parser.add_argument(
        "--cors-origin",
        default="",
        help="許可するOrigin（例: https://example.com、未指定なら無効）",
    )
    parser.add_argument(
        "--api-token",
        default="",
        help="POST時に必須のトークン（未指定なら不要）",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    global CORS_ORIGIN, API_TOKEN
    CORS_ORIGIN = args.cors_origin.strip() or None
    API_TOKEN = args.api_token.strip() or None
    server = ThreadingHTTPServer((args.host, args.port), OrchestratorHandler)
    print(f"Web UI: http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
