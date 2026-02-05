#!/usr/bin/env python3
"""SSH Remote Server Support via sshfs / rsync.

Provides transparent access to remote filesystems by mounting them locally
with sshfs, falling back to rsync pull/push when sshfs is unavailable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def check_sshfs_available() -> bool:
    """Return True if sshfs is installed and on PATH."""
    try:
        proc = subprocess.run(
            ["sshfs", "--version"],
            capture_output=True,
            timeout=5,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def check_macfuse_available() -> bool:
    """Return True if macFUSE kernel extension is loaded (macOS only)."""
    if sys.platform != "darwin":
        return True  # Not relevant on Linux
    try:
        proc = subprocess.run(
            ["kextstat"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "macfuse" in proc.stdout.lower() or "osxfuse" in proc.stdout.lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def test_ssh_connection(
    host: str,
    user: str = "",
    port: int = 22,
    key_file: str = "",
) -> tuple[bool, str]:
    """Test SSH connectivity to the remote host.

    Returns:
        (ok, message) tuple.
    """
    target = f"{user}@{host}" if user else host
    cmd = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes", "-p", str(port)]
    if key_file:
        expanded = os.path.expanduser(key_file)
        if os.path.isfile(expanded):
            cmd.extend(["-i", expanded])
    cmd.extend([target, "echo ok"])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if proc.returncode == 0 and "ok" in proc.stdout:
            return True, f"SSH connection to {target}:{port} successful"
        return False, f"SSH connection failed: {proc.stderr.strip()}"
    except FileNotFoundError:
        return False, "ssh command not found"
    except subprocess.TimeoutExpired:
        return False, "SSH connection timed out"


def mount_sshfs(
    host: str,
    remote_path: str,
    local_mount: str,
    user: str = "",
    port: int = 22,
    key_file: str = "",
    mount_options: list[str] | None = None,
) -> tuple[bool, str]:
    """Mount a remote filesystem via sshfs.

    Returns:
        (ok, message) tuple.
    """
    local = Path(os.path.expanduser(local_mount))
    local.mkdir(parents=True, exist_ok=True)

    target = f"{user}@{host}:{remote_path}" if user else f"{host}:{remote_path}"
    cmd = ["sshfs", target, str(local), "-p", str(port)]

    if key_file:
        expanded = os.path.expanduser(key_file)
        if os.path.isfile(expanded):
            cmd.extend(["-o", f"IdentityFile={expanded}"])

    for opt in mount_options or ["reconnect", "ServerAliveInterval=15", "ServerAliveCountMax=3"]:
        cmd.extend(["-o", opt])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if proc.returncode == 0:
            return True, f"Mounted {target} at {local}"
        return False, f"sshfs mount failed: {proc.stderr.strip()}"
    except FileNotFoundError:
        return False, "sshfs command not found"
    except subprocess.TimeoutExpired:
        return False, "sshfs mount timed out"


def unmount_sshfs(local_mount: str) -> tuple[bool, str]:
    """Unmount a sshfs mount point.

    Returns:
        (ok, message) tuple.
    """
    local = Path(os.path.expanduser(local_mount))
    if not local.exists():
        return True, f"Mount point {local} does not exist"

    # Try umount (Linux) or diskutil unmount (macOS)
    if sys.platform == "darwin":
        cmd = ["diskutil", "unmount", str(local)]
    else:
        cmd = ["fusermount", "-u", str(local)]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if proc.returncode == 0:
            return True, f"Unmounted {local}"
        # Fallback to umount
        proc2 = subprocess.run(
            ["umount", str(local)], capture_output=True, text=True, timeout=10
        )
        if proc2.returncode == 0:
            return True, f"Unmounted {local}"
        return False, f"Unmount failed: {proc.stderr.strip()}"
    except FileNotFoundError:
        return False, "unmount command not found"
    except subprocess.TimeoutExpired:
        return False, "Unmount timed out"


def is_mounted(path: str) -> bool:
    """Check if a path is a mount point."""
    local = Path(os.path.expanduser(path))
    if not local.exists():
        return False
    try:
        proc = subprocess.run(
            ["mount"], capture_output=True, text=True, timeout=5
        )
        return str(local.resolve()) in proc.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def rsync_pull(
    host: str,
    remote_path: str,
    local_path: str,
    user: str = "",
    port: int = 22,
    key_file: str = "",
    exclude: list[str] | None = None,
) -> tuple[bool, str]:
    """Pull files from remote to local via rsync.

    Returns:
        (ok, message) tuple.
    """
    local = Path(os.path.expanduser(local_path))
    local.mkdir(parents=True, exist_ok=True)

    target = f"{user}@{host}:{remote_path}/" if user else f"{host}:{remote_path}/"
    cmd = ["rsync", "-az", "--delete"]

    ssh_cmd = f"ssh -p {port}"
    if key_file:
        expanded = os.path.expanduser(key_file)
        if os.path.isfile(expanded):
            ssh_cmd += f" -i {expanded}"
    cmd.extend(["-e", ssh_cmd])

    for pattern in exclude or [".git", "node_modules", "__pycache__"]:
        cmd.extend(["--exclude", pattern])

    cmd.extend([target, str(local) + "/"])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode == 0:
            return True, f"rsync pull from {target} to {local} completed"
        return False, f"rsync pull failed: {proc.stderr.strip()}"
    except FileNotFoundError:
        return False, "rsync command not found"
    except subprocess.TimeoutExpired:
        return False, "rsync pull timed out"


def rsync_push(
    host: str,
    remote_path: str,
    local_path: str,
    user: str = "",
    port: int = 22,
    key_file: str = "",
    exclude: list[str] | None = None,
) -> tuple[bool, str]:
    """Push files from local to remote via rsync.

    Returns:
        (ok, message) tuple.
    """
    local = Path(os.path.expanduser(local_path))
    if not local.exists():
        return False, f"Local path {local} does not exist"

    target = f"{user}@{host}:{remote_path}/" if user else f"{host}:{remote_path}/"
    cmd = ["rsync", "-az", "--delete"]

    ssh_cmd = f"ssh -p {port}"
    if key_file:
        expanded = os.path.expanduser(key_file)
        if os.path.isfile(expanded):
            ssh_cmd += f" -i {expanded}"
    cmd.extend(["-e", ssh_cmd])

    for pattern in exclude or [".git", "node_modules", "__pycache__"]:
        cmd.extend(["--exclude", pattern])

    cmd.extend([str(local) + "/", target])

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode == 0:
            return True, f"rsync push from {local} to {target} completed"
        return False, f"rsync push failed: {proc.stderr.strip()}"
    except FileNotFoundError:
        return False, "rsync command not found"
    except subprocess.TimeoutExpired:
        return False, "rsync push timed out"


def setup_remote(config: dict) -> tuple[bool, str, str]:
    """Set up remote filesystem access.

    Tries sshfs first, falls back to rsync pull.

    Args:
        config: Full orchestrator config dict (reads ``ssh_remote`` section).

    Returns:
        (ok, message, local_path) tuple.  *local_path* is the directory
        that Claude/Codex should work in.
    """
    ssh_cfg = config.get("ssh_remote") or {}
    if not ssh_cfg.get("enabled"):
        return True, "SSH remote disabled", ""

    host = ssh_cfg.get("host", "")
    user = ssh_cfg.get("user", "")
    port = int(ssh_cfg.get("port", 22))
    key_file = ssh_cfg.get("key_file", "")
    remote_path = ssh_cfg.get("remote_path", "")
    local_mount = ssh_cfg.get("local_mount", "~/mnt/remote_project")
    mount_options = ssh_cfg.get("mount_options")
    fallback_mode = ssh_cfg.get("fallback_mode", "rsync")
    rsync_opts = ssh_cfg.get("rsync_options") or {}

    if not host or not remote_path:
        return False, "ssh_remote.host and ssh_remote.remote_path are required", ""

    # Test SSH connection first
    ok, msg = test_ssh_connection(host, user, port, key_file)
    if not ok:
        return False, msg, ""

    local_path = os.path.expanduser(local_mount)

    # Already mounted?
    if is_mounted(local_path):
        return True, f"Already mounted at {local_path}", local_path

    # Try sshfs
    if check_sshfs_available():
        ok, msg = mount_sshfs(host, remote_path, local_mount, user, port, key_file, mount_options)
        if ok:
            return True, msg, local_path

    # Fallback to rsync
    if fallback_mode == "rsync":
        exclude = rsync_opts.get("exclude", [".git", "node_modules", "__pycache__"])
        if rsync_opts.get("sync_before", True):
            ok, msg = rsync_pull(host, remote_path, local_path, user, port, key_file, exclude)
            if ok:
                return True, f"rsync pull completed: {local_path}", local_path
            return False, msg, ""

        # If sync_before is False, just ensure the directory exists
        Path(local_path).mkdir(parents=True, exist_ok=True)
        return True, f"Local directory ready (no initial sync): {local_path}", local_path

    return False, "sshfs unavailable and fallback_mode is not rsync", ""


def teardown_remote(config: dict) -> tuple[bool, str]:
    """Clean up remote filesystem access.

    Unmounts sshfs or pushes changes back via rsync.

    Args:
        config: Full orchestrator config dict (reads ``ssh_remote`` section).

    Returns:
        (ok, message) tuple.
    """
    ssh_cfg = config.get("ssh_remote") or {}
    if not ssh_cfg.get("enabled"):
        return True, "SSH remote disabled"

    host = ssh_cfg.get("host", "")
    user = ssh_cfg.get("user", "")
    port = int(ssh_cfg.get("port", 22))
    key_file = ssh_cfg.get("key_file", "")
    remote_path = ssh_cfg.get("remote_path", "")
    local_mount = ssh_cfg.get("local_mount", "~/mnt/remote_project")
    rsync_opts = ssh_cfg.get("rsync_options") or {}

    local_path = os.path.expanduser(local_mount)

    # If mounted via sshfs, unmount
    if is_mounted(local_path):
        return unmount_sshfs(local_mount)

    # Otherwise, push changes back via rsync if configured
    if rsync_opts.get("sync_after", True) and Path(local_path).exists():
        exclude = rsync_opts.get("exclude", [".git", "node_modules", "__pycache__"])
        return rsync_push(host, remote_path, local_path, user, port, key_file, exclude)

    return True, "Nothing to tear down"
