#!/usr/bin/env python3
"""SSH Remote Executor - Execute code blocks on a remote server via SSH.

Standalone CLI script that acts as a drop-in replacement for `codex exec`.
Reads concertmaster instruction text from stdin, extracts code blocks,
and executes them on the remote server via SSH.

Usage:
    echo 'instruction with ```bash\nls -la\n```' | python3 ssh_executor.py
    python3 ssh_executor.py < instruction.txt
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"

# Regex to extract fenced code blocks: ```lang\n...\n```
_CODE_BLOCK_RE = re.compile(
    r"```(bash|sh|python|python3)\s*\n(.*?)```",
    re.DOTALL,
)

# Fallback: lines starting with $ (shell commands)
_DOLLAR_LINE_RE = re.compile(r"^\$\s+(.+)$", re.MULTILINE)

# Known command prefixes for fallback extraction
_CMD_PREFIXES = (
    "ls", "cd", "cat", "grep", "find", "echo", "mkdir", "rm", "cp", "mv",
    "python", "python3", "root", "hadd", "rootls", "rootprint",
    "source", "export", "which", "pwd", "wc", "head", "tail", "sort",
    "awk", "sed", "tar", "gzip", "gunzip", "chmod", "chown",
)


def load_config() -> dict:
    """Load config.json and return ssh_remote section."""
    if not CONFIG_PATH.exists():
        print(f"Error: config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_ssh_config(config: dict) -> dict:
    """Extract and validate ssh_remote config."""
    ssh_cfg = config.get("ssh_remote") or {}
    if not ssh_cfg.get("host"):
        print("Error: ssh_remote.host is not configured", file=sys.stderr)
        sys.exit(1)
    return ssh_cfg


def build_ssh_base(ssh_cfg: dict) -> list[str]:
    """Build base SSH command with connection options."""
    host = ssh_cfg["host"]
    user = ssh_cfg.get("user", "")
    port = int(ssh_cfg.get("port", 22))
    key_file = ssh_cfg.get("key_file", "")

    target = f"{user}@{host}" if user else host
    cmd = [
        "ssh",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-p", str(port),
    ]

    if key_file:
        expanded = os.path.expanduser(key_file)
        if os.path.isfile(expanded):
            cmd.extend(["-i", expanded])

    cmd.append(target)
    return cmd


def build_scp_base(ssh_cfg: dict) -> list[str]:
    """Build base SCP command for file transfer."""
    port = int(ssh_cfg.get("port", 22))
    key_file = ssh_cfg.get("key_file", "")

    cmd = [
        "scp",
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=10",
        "-P", str(port),
    ]

    if key_file:
        expanded = os.path.expanduser(key_file)
        if os.path.isfile(expanded):
            cmd.extend(["-i", expanded])

    return cmd


def scp_target(ssh_cfg: dict, remote_file: str) -> str:
    """Build SCP target string like user@host:/path/file."""
    host = ssh_cfg["host"]
    user = ssh_cfg.get("user", "")
    target = f"{user}@{host}" if user else host
    return f"{target}:{remote_file}"


def extract_code_blocks(text: str) -> list[tuple[str, str]]:
    """Extract (language, code) tuples from fenced code blocks.

    Returns list of (lang, code) where lang is 'bash', 'sh', 'python', or 'python3'.
    """
    blocks = []
    for match in _CODE_BLOCK_RE.finditer(text):
        lang = match.group(1).strip().lower()
        code = match.group(2).strip()
        if code:
            blocks.append((lang, code))
    return blocks


def extract_fallback_commands(text: str) -> list[tuple[str, str]]:
    """Fallback: extract commands from $ lines or known-prefix lines."""
    blocks = []

    # Try $ prefix lines
    dollar_matches = _DOLLAR_LINE_RE.findall(text)
    if dollar_matches:
        combined = "\n".join(dollar_matches)
        return [("bash", combined)]

    # Try lines starting with known command prefixes
    cmds = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        first_word = stripped.split()[0] if stripped.split() else ""
        if first_word in _CMD_PREFIXES:
            cmds.append(stripped)
    if cmds:
        combined = "\n".join(cmds)
        blocks.append(("bash", combined))

    return blocks


def execute_bash_remote(
    code: str,
    ssh_base: list[str],
    remote_path: str,
    timeout: int = 300,
) -> tuple[int, str, str]:
    """Execute bash commands on remote server via SSH."""
    # Wrap in cd + bash -e for proper error handling
    if remote_path:
        wrapped = f"cd {remote_path} && {code}"
    else:
        wrapped = code

    cmd = ssh_base + [wrapped]

    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def execute_python_remote(
    code: str,
    ssh_base: list[str],
    ssh_cfg: dict,
    remote_path: str,
    timeout: int = 300,
) -> tuple[int, str, str]:
    """Execute Python code on remote server.

    Short scripts use python3 -c, longer ones use scp + execute.
    """
    # Threshold: use -c for short scripts, scp for long ones
    if len(code) < 500 and "\n" not in code.strip():
        # Single-line or short: use python3 -c
        escaped = code.replace("'", "'\"'\"'")
        if remote_path:
            wrapped = f"cd {remote_path} && python3 -c '{escaped}'"
        else:
            wrapped = f"python3 -c '{escaped}'"

        cmd = ssh_base + [wrapped]
        try:
            proc = subprocess.run(
                cmd, text=True, capture_output=True, timeout=timeout,
            )
            return proc.returncode, proc.stdout or "", proc.stderr or ""
        except subprocess.TimeoutExpired:
            return 124, "", f"Command timed out after {timeout}s"
        except Exception as e:
            return 1, "", str(e)

    # Long script: scp to remote, execute, clean up
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, prefix="ssh_exec_"
    ) as tmp:
        tmp.write(code)
        tmp_path = tmp.name
        tmp_name = os.path.basename(tmp_path)

    try:
        # Determine remote temp location
        remote_tmp = f"/tmp/{tmp_name}"

        # SCP the script to remote
        scp_cmd = build_scp_base(ssh_cfg) + [tmp_path, scp_target(ssh_cfg, remote_tmp)]
        scp_proc = subprocess.run(
            scp_cmd, text=True, capture_output=True, timeout=30,
        )
        if scp_proc.returncode != 0:
            return scp_proc.returncode, "", f"SCP failed: {scp_proc.stderr}"

        # Execute on remote
        if remote_path:
            run_cmd = f"cd {remote_path} && python3 {remote_tmp}; rm -f {remote_tmp}"
        else:
            run_cmd = f"python3 {remote_tmp}; rm -f {remote_tmp}"

        cmd = ssh_base + [run_cmd]
        proc = subprocess.run(
            cmd, text=True, capture_output=True, timeout=timeout,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return 1, "", str(e)
    finally:
        os.unlink(tmp_path)


def main() -> int:
    """Main entry point. Reads instruction from stdin, executes code blocks remotely."""
    # Read instruction from stdin
    instruction = sys.stdin.read()
    if not instruction.strip():
        print("Error: no instruction received on stdin", file=sys.stderr)
        return 1

    # Load config
    config = load_config()
    ssh_cfg = get_ssh_config(config)
    remote_path = ssh_cfg.get("remote_path", "")

    # Build SSH command base
    ssh_base = build_ssh_base(ssh_cfg)

    # Extract code blocks
    blocks = extract_code_blocks(instruction)
    if not blocks:
        blocks = extract_fallback_commands(instruction)

    if not blocks:
        # No executable code found - pass instruction as-is to bash
        print(
            "Warning: no code blocks found in instruction, "
            "attempting to execute as shell command",
            file=sys.stderr,
        )
        # Try to execute the whole instruction as a bash command
        stripped = instruction.strip()
        if stripped:
            blocks = [("bash", stripped)]
        else:
            print("Error: no executable content found", file=sys.stderr)
            return 1

    # Execute each block
    all_stdout = []
    all_stderr = []
    final_rc = 0

    for i, (lang, code) in enumerate(blocks):
        if lang in ("bash", "sh"):
            rc, stdout, stderr = execute_bash_remote(
                code, ssh_base, remote_path,
            )
        elif lang in ("python", "python3"):
            rc, stdout, stderr = execute_python_remote(
                code, ssh_base, ssh_cfg, remote_path,
            )
        else:
            stderr = f"Unsupported language: {lang}"
            rc = 1
            stdout = ""

        if stdout:
            all_stdout.append(stdout)
        if stderr:
            all_stderr.append(stderr)

        if rc != 0:
            final_rc = rc
            # Print error immediately but continue with remaining blocks
            print(f"[Block {i+1}/{len(blocks)} ({lang})] exit code: {rc}", file=sys.stderr)
            if stderr:
                print(stderr, file=sys.stderr)

    # Output combined stdout
    combined_out = "\n".join(all_stdout)
    if combined_out:
        print(combined_out)

    # Output combined stderr
    combined_err = "\n".join(all_stderr)
    if combined_err:
        print(combined_err, file=sys.stderr)

    return final_rc


if __name__ == "__main__":
    raise SystemExit(main())
