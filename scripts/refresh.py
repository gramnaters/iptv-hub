#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "catalogs", "schedule.json")
LOGFILE = os.path.join(ROOT, "logs", "refresh.log")

# name: (generator, playlist, max age in hours)
SOURCES = {
    "sony":    ("generate_sony.py",    "sonyliv.m3u", 1),
    "jiohotstar": ("generate_jiohotstar.py", "jiohotstar.m3u", 1),
    "vzy":     ("generate_vzy_selfmint.py", "vzy.m3u", 1),
    "zee5live":("generate_zee5_live.py", "zee5_live.m3u", 1),
    "fancode": ("generate_fancode.py", "fancode.m3u", 1),
    "sunnxt":  ("generate_sunnxt.py",  "sunnxt.m3u",  6),
    "free":    ("generate_free.py",    "free.m3u",    6),
    "jiotv":   ("generate_jiotv_public.py", "jiotv.m3u", 1),
}
MARGIN = 90 * 60
EXP_RE = re.compile(r"(?:exp|Expires)(?:=|%3D)(\d{10})")

# Generous per-source wall-clock caps. A hung generator used to abort the whole
# run (subprocess timeout at 1800 s), which also skipped merge/push and blocked
# every later source. Now a slow source only costs itself.
DEFAULT_TIMEOUT = 900
TIMEOUTS = {"zee5live": 1500, "jiohotstar": 1200, "vzy": 1200, "sony": 900}

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def log(msg):
    line = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    os.makedirs(os.path.dirname(LOGFILE), exist_ok=True)
    with open(LOGFILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def expiries(playlist):
    try:
        with open(os.path.join(ROOT, "playlists", playlist), encoding="utf-8") as f:
            return [int(x) for x in EXP_RE.findall(f.read())]
    except OSError:
        return []


def due(name, state, now):
    _, playlist, max_age = SOURCES[name]
    last = state.get(name, {}).get("last", 0)
    if now - last >= max_age * 3600 - 300:
        return "max age"
    exps = expiries(playlist)
    live = [e for e in exps if e > now]
    if exps and len(live) < len(exps) / 2:
        return "tokens expired"
    if live and min(live) - now < MARGIN:
        return "tokens expiring"
    return ""


def run(script, timeout=DEFAULT_TIMEOUT):
    try:
        p = subprocess.run([sys.executable, os.path.join("scripts", script)], cwd=ROOT,
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout)
        out, err, rc = p.stdout, p.stderr, p.returncode
    except subprocess.TimeoutExpired as e:
        log(f"    ! {script}: timed out after {timeout}s (skipping this source)")
        out = e.stdout or ""
        err = e.stderr or ""
        rc = 124
    for line in (out or "").strip().splitlines()[-20:]:
        log("    " + line)
    if rc:
        for line in (err or "").strip().splitlines()[-10:]:
            log("    ! " + line)
    return rc


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def push():
    git("add", "-A", "playlists", "Combined.m3u", "catalogs")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return 0
    git("commit", "-m", f"refresh {datetime.datetime.now(datetime.timezone.utc):%Y-%m-%d %H:%M} UTC")
    for i in range(3):
        if git("push", "origin", "HEAD:main").returncode == 0:
            return 0
        time.sleep(3 * (i + 1))
        git("pull", "--rebase", "--autostash", "origin", "main")
    return 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    only = {s for s in args.only.split(",") if s}
    state = json.load(open(STATE)) if os.path.exists(STATE) else {}
    now = time.time()
    ran, failed = [], []

    for name, (script, playlist, _) in SOURCES.items():
        if only and name not in only:
            continue
        why = "forced" if args.force or only else due(name, state, now)
        if not why:
            continue
        log(f"{name}: {why}")
        if run(script, TIMEOUTS.get(name, DEFAULT_TIMEOUT)):
            failed.append(name)
            continue
        ran.append(name)
        live = [e for e in expiries(playlist) if e > time.time()]
        state[name] = {
            "last": int(time.time()),
            "updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "expires": datetime.datetime.fromtimestamp(min(live), datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC") if live else None,
        }

    if ran or failed:
        if run("merge.py", 600):
            failed.append("merge")
        with open(STATE, "w") as f:
            json.dump(state, f, indent=1)
        if not args.no_push and push():
            failed.append("push")
    log(f"ran: {ran or '-'} failed: {failed or '-'}")
    # A failed source must not fail the job: the other sources refreshed and the
    # playlists were still merged and pushed. Export failures as a warning only.
    if "push" in failed:
        print("::warning::playlist push failed after retries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
