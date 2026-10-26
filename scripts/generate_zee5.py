#!/usr/bin/env python3
"""
ZEE5 playlist generator.
Maintains playlists/zee5.m3u with live playback streams via our dedicated
Cloudflare Worker edge (zee.gramnaters.workers.dev) and official playback APIs.
"""
import json
import os
import sys
import uuid
from datetime import datetime, timezone
import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "zee5_catalog.json")
STATUS = os.path.join(ROOT, "catalogs", "zee5_status.json")
OUT = os.path.join(ROOT, "playlists", "zee5.m3u")

ZEE_WORKER_URL = "https://zee.gramnaters.workers.dev/playlist.m3u"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")


def main():
    # 1. First priority: sync full 118-channel playlist from our dedicated worker edge
    try:
        r = requests.get(ZEE_WORKER_URL, headers={"User-Agent": UA}, timeout=15)
        if r.status_code == 200 and "#EXTINF" in r.text:
            text = r.text.strip()
            ch_count = sum(1 for l in text.splitlines() if l.startswith("#EXTINF"))
            if ch_count >= 50:
                os.makedirs(os.path.dirname(OUT), exist_ok=True)
                with open(OUT, "w", encoding="utf-8") as f:
                    f.write(text + "\n")
                stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
                with open(STATUS, "w", encoding="utf-8") as f:
                    json.dump({"updated_at": stamp, "playable": ch_count, "source": ZEE_WORKER_URL}, f, indent=2)
                print(f"ZEE5: wrote {OUT} ({ch_count} channels from worker edge)")
                return 0
    except Exception as e:
        print(f"ZEE5 worker edge warning: {e}")

    # 2. Existing local playlist fallback
    if os.path.exists(OUT):
        with open(OUT, "r", encoding="utf-8") as f:
            lines = f.readlines()
        count = sum(1 for l in lines if l.startswith("#EXTINF"))
        if count >= 50:
            print(f"ZEE5: retaining current playlist ({count} channels)")
            return 0

    print("ZEE5: failed to generate playlist.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
