#!/usr/bin/env python3
"""
Free channels playlist generator.
"""
import json
import os
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
CATALOG_FILE = os.path.join(ROOT_DIR, "catalogs", "free_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "free.m3u")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def generate_playlist():
    with open(CATALOG_FILE, encoding="utf-8") as f:
        channels = json.load(f)

    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: free",
        f"# Total Channels: {len(channels)}",
        "",
    ]

    for ch in channels:
        name = ch.get("name", "").strip()
        url = ch.get("url", "").strip()
        group = ch.get("group", "Other").strip()
        logo = ch.get("logo", "").strip()
        tvg_id = ch.get("tvg_id", "").strip()
        category = ch.get("category", "").strip()

        if not name or not url:
            continue

        attrs = []
        if tvg_id:
            attrs.append(f'tvg-id="{tvg_id}"')
        attrs.append(f'tvg-name="{name}"')
        if logo:
            attrs.append(f'tvg-logo="{logo}"')
        if category:
            attrs.append(f'tvg-category="{category}"')
        attrs.append(f'group-title="{group}"')

        lines.append(f'#EXTINF:-1 {" ".join(attrs)},{name}')
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Generated {OUTPUT_M3U} ({len(channels)} free channels)")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate_playlist() else 1)
