#!/usr/bin/env python3
"""
generate_vzy.py — 100% Independent VZY Playlist Generator.
Generates playlists/vzy.m3u directly from self-hosted catalogs/vzy_catalog.json
with verified ClearKeys and CloudFront Kaltura CDN streams.
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
CATALOG_FILE = os.path.join(ROOT_DIR, "catalogs", "vzy_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "vzy.m3u")

GROUP_LOGO = "https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/entry_id/bab798478e714be3a5ae861fc04606f0/version/0"


def generate_vzy_playlist():
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    if not os.path.exists(CATALOG_FILE):
        print(f"❌ Catalog file {CATALOG_FILE} not found!")
        return

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: VZY Live",
        f"# Total Channels: {len(channels)}",
        "# Source: CloudFront Kaltura CDN with direct ClearKeys",
        ""
    ]

    for ch in channels:
        cid = ch.get("id", "")
        name = ch.get("name", "")
        logo = ch.get("logo", "")
        genre = ch.get("group", "VZY")
        key = ch.get("key")
        url = ch.get("url", "")

        is_dash = ".mpd" in url.lower()
        type_tag = ' type="dash"' if is_dash else ''

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{genre}" group-title="VZY" group-logo="{GROUP_LOGO}"{type_tag},{name}'
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

    dash = sum(1 for c in channels if c.get("url", "").lower().endswith(".mpd"))
    print(f"✅ Generated {OUTPUT_M3U} ({len(channels)} VZY channels)")
    print(f"   DASH+ClearKey {dash} | FTA HLS {len(channels) - dash}")


if __name__ == "__main__":
    generate_vzy_playlist()
