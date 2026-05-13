#!/usr/bin/env python3
"""Refresh platform's local copy of silver-canonical.yaml from the kernel repo.

docs/data-layer.md §5.3, §11.1: kernel owns the schema; platform sync-copies
it. Run after pulling kernel changes.

Usage:
    KERNEL_REPO=/path/to/YunWei-AI-Kernel scripts/sync-silver-canonical.py
    scripts/sync-silver-canonical.py --kernel-path /path/to/kernel
"""
from __future__ import annotations
import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEST = REPO_ROOT / "services" / "platform-api" / "platform_app" / "data_layer" / "silver-canonical.yaml"
REL_SRC = Path("kernel/lakehouse/silver-canonical.yaml")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel-path", help="Path to YunWei-AI-Kernel checkout (or set KERNEL_REPO)")
    args = ap.parse_args()

    kernel_root = args.kernel_path or os.environ.get("KERNEL_REPO")
    if not kernel_root:
        print("error: pass --kernel-path or set KERNEL_REPO", file=sys.stderr)
        return 2

    src = Path(kernel_root).expanduser() / REL_SRC
    if not src.is_file():
        print(f"error: source not found: {src}", file=sys.stderr)
        return 1

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, DEST)
    print(f"synced {src} -> {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
