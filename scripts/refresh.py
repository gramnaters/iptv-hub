#!/usr/bin/env python3
"""
IPTV playlist refresh runner.
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGDIR = os.path.join(ROOT, "logs")
LOGFILE = os.path.join(LOGDIR, "refresh.log")

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GENERATORS = [
    "generate_jiotv.py",
    "generate_zee5.py",
    "generate_vzy.py",
    "generate_sony.py",
    "generate_fancode.py"
]


def log(msg):
    msg = msg.encode("ascii", "replace").decode("ascii")
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    os.makedirs(LOGDIR, exist_ok=True)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(cmd, timeout=1800):
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    for line in (p.stdout or "").strip().splitlines():
        log("    " + line)
    if p.returncode != 0:
        for line in (p.stderr or "").strip().splitlines()[-15:]:
            log("    ! " + line)
    return p.returncode


def git(*args, check=False):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p


def push_playlist():
    git("add", "-A", "playlists", "Combined.m3u", "catalogs")
    if git("diff", "--cached", "--quiet").returncode == 0:
        log("no playlist changes to commit")
        return 0
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    git("commit", "-m", f"refresh: live tokens {stamp}", check=True)
    for attempt in range(3):
        p = git("push", "origin", "HEAD:main")
        if p.returncode == 0:
            log("pushed to origin/main")
            return 0
        log(f"push rejected (attempt {attempt + 1}), rebasing")
        time.sleep(3 * (attempt + 1))
        git("pull", "--rebase", "--autostash", "origin", "main")
        git("push", "origin", "HEAD:main")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--only", default="", help="comma list, e.g. jiotv,zee5")
    args = ap.parse_args()

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    started = time.time()
    log("=== refresh start ===")
    failures = []

    for name in GENERATORS:
        if only and not any(o in name for o in only):
            continue
        log(f"running {name}")
        if run([sys.executable, os.path.join("scripts", name)]) != 0:
            failures.append(name)

    log("running merge.py")
    if run([sys.executable, os.path.join("scripts", "merge.py")]) != 0:
        failures.append("merge.py")

    if not args.no_push:
        if push_playlist() != 0:
            failures.append("git push")

    log(f"=== refresh done in {time.time() - started:.0f}s, failures: {failures or 'none'} ===")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
