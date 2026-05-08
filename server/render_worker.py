import argparse
import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["current", "batch"], required=True)
    parser.add_argument("--count", type=int, default=5)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    capcut = root / "capcut_ui.py"

    if args.mode == "current":
        cmd = [sys.executable, "-u", str(capcut), "--studio-headless-current"]
    else:
        cmd = [sys.executable, "-u", str(capcut), "--studio-headless-batch", "--count", str(int(args.count))]

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.run(cmd, cwd=str(root), env=env)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
