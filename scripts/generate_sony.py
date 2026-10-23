#!/usr/bin/env python3
import os
import re
import sys
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sonyliv.m3u")

# Self-hosted SonyLIV worker (sliv): mints the Akamai `hdnea` token via Browser
# Rendering on a 5h cron and serves each channel at /<slug>.m3u8 (302 -> CDN).
# No third-party token source.
SLIV_PLAYLIST = "https://sliv.gramnaters.workers.dev/playlist.m3u"

GROUP = "Sony LIV"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png"

MIN_CHANNELS = 5


def generate_playlist():
    print(f"📡 Fetching SonyLIV playlist from {SLIV_PLAYLIST}...")
    try:
        import requests
        r = requests.get(SLIV_PLAYLIST, timeout=20)
        r.raise_for_status()
        text = r.text
    except Exception as e:
        print(f"  ⚠️ Error fetching from sliv worker: {e}")
        return False

    count = text.count("#EXTINF")
    if count < MIN_CHANNELS:
        print(f"  ❌ sliv worker returned only {count} channels (< {MIN_CHANNELS}); keeping existing file")
        return False

    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    body = []
    for line in text.splitlines():
        if line.startswith("#EXTM3U") or line.startswith("# SonyLIV"):
            continue
        if line.startswith("#EXTINF"):
            # Collapse the worker's "SonyLIV <category>" into a single group and
            # add the group logo.
            line = re.sub(
                r'group-title="[^"]*"',
                f'group-title="{GROUP}" group-logo="{GROUP_LOGO}"',
                line,
            )
        body.append(line)

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: sonyliv",
        f"# Total Channels: {count}",
        f"# Source: {SLIV_PLAYLIST} (self-hosted sliv worker)",
        "",
    ] + body

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    print(f"✅ Generated {OUTPUT_M3U} ({count} SonyLIV channels)")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate_playlist() else 1)
