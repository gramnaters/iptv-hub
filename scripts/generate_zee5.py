#!/usr/bin/env python3
"""
Independent ZEE5 Playlist Generator
Generates full ZEE5 catalog (India & Worldwide: 145+ channels).
- ZEE5 India: Direct DASH MPD streams with ClearKeys
- ZEE5 Worldwide: International HLS feeds
Independent of external playlist down-times.
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_FILE = os.path.join(ROOT_DIR, "channels", "zee5_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "zee5.m3u")

def generate_zee5_playlist():
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    if not os.path.exists(CATALOG_FILE):
        print(f"❌ Catalog file {CATALOG_FILE} not found!")
        return

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        f"# Category: zee5",
        f"# Total Channels: {len(channels)}",
        ""
    ]

    for ch in channels:
        cid = ch.get("id", "")
        name = ch.get("name", "")
        logo = ch.get("logo", "")
        group = ch.get("group", "ZEE5")
        key = ch.get("key")
        url = ch.get("url", "")

        is_dash = ".mpd" in url.lower()
        type_tag = ' type="dash"' if is_dash else ''

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}"'
            f' group-logo="https://yt3.googleusercontent.com/lyA_tGOMIiCHSVvdjC8ExJE3BsXMjyjipa1vL5g736p7Gu1mAkTDqLbMttOYMVdgvEs0NYEtZw=s900-c-k-c0x00ffffff-no-rj"{type_tag},{name}'
        )
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")
        lines.append(url)
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Generated {OUTPUT_M3U} ({len(channels)} ZEE5 channels)")

if __name__ == "__main__":
    generate_zee5_playlist()
