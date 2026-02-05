#!/usr/bin/env python3
"""CLI wrapper for SSH remote operations (used by ctl.sh)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ssh_remote import (
    check_macfuse_available,
    check_sshfs_available,
    is_mounted,
    setup_remote,
    teardown_remote,
    test_ssh_connection,
)

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}


def cmd_mount(args: argparse.Namespace) -> int:
    config = load_config()
    ok, msg, local_path = setup_remote(config)
    if ok:
        print(f"✅ {msg}")
        if local_path:
            print(f"   Local path: {local_path}")
        return 0
    print(f"❌ {msg}", file=sys.stderr)
    return 1


def cmd_unmount(args: argparse.Namespace) -> int:
    config = load_config()
    ok, msg = teardown_remote(config)
    if ok:
        print(f"✅ {msg}")
        return 0
    print(f"❌ {msg}", file=sys.stderr)
    return 1


def cmd_status(args: argparse.Namespace) -> int:
    config = load_config()
    ssh_cfg = config.get("ssh_remote") or {}

    print("📊 SSH Remote Status")
    print("━" * 40)

    if not ssh_cfg.get("enabled"):
        print("   Status:  Disabled")
        print("   Enable in config.json -> ssh_remote.enabled")
        return 0

    host = ssh_cfg.get("host", "(not set)")
    user = ssh_cfg.get("user", "")
    port = ssh_cfg.get("port", 22)
    remote_path = ssh_cfg.get("remote_path", "(not set)")
    local_mount = ssh_cfg.get("local_mount", "~/mnt/remote_project")

    target = f"{user}@{host}" if user else host
    print(f"   Remote:  {target}:{port}")
    print(f"   Path:    {remote_path}")
    print(f"   Mount:   {local_mount}")

    # Check sshfs
    sshfs_ok = check_sshfs_available()
    print(f"   sshfs:   {'✅ Available' if sshfs_ok else '❌ Not found'}")

    if sys.platform == "darwin":
        fuse_ok = check_macfuse_available()
        print(f"   macFUSE: {'✅ Loaded' if fuse_ok else '❌ Not loaded'}")

    # Check mount status
    import os
    local_path = os.path.expanduser(local_mount)
    mounted = is_mounted(local_path)
    print(f"   Mounted: {'✅ Yes' if mounted else '⭕ No'}")

    # Test SSH connection
    if ssh_cfg.get("host"):
        ok, msg = test_ssh_connection(
            ssh_cfg["host"],
            ssh_cfg.get("user", ""),
            int(ssh_cfg.get("port", 22)),
            ssh_cfg.get("key_file", ""),
        )
        print(f"   SSH:     {'✅' if ok else '❌'} {msg}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSH Remote CLI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("mount", help="Mount remote filesystem")
    sub.add_parser("unmount", help="Unmount remote filesystem")
    sub.add_parser("status", help="Show SSH remote status")

    args = parser.parse_args(argv)
    if args.command == "mount":
        return cmd_mount(args)
    if args.command == "unmount":
        return cmd_unmount(args)
    if args.command == "status":
        return cmd_status(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
