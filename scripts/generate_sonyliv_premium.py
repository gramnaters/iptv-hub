#!/usr/bin/env python3
import os
import json
import sys
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_FILE = os.path.join(ROOT_DIR, "catalogs", "sonyliv_premium.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sonyliv_premium.m3u")

WORKER = "https://sonyliv.joker-verse.workers.dev/master.m3u8"
UID = "8004188626"
PASS = "61498d15"
GROUP = "SonyLIV Premium"


def generate():
    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    lines = ["#EXTM3U", f"#DATE:- {now_ist}", "# Category: sonyliv-premium", ""]

    for ch in channels:
        url = f"{WORKER}?id={ch['id']}&uid={UID}&pass={PASS}"
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" '
            f'group-title="{GROUP}",{ch["name"]}'
        )
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"✅ Generated {OUTPUT_M3U} ({len(channels)} SonyLIV Premium channels)")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate() else 1)
