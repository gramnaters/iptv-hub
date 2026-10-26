#!/usr/bin/env python3
"""
ZEE5 Live TV Playlist Generator & Sync.
Produces:
1. ZEE5 India: 32 pure, high-stability CloudFront DASH channels with W3C ClearKeys.
2. ZEE5 Worldwide: 112 international & regional channels with live session tokens.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "zee5_catalog.json")
STATUS = os.path.join(ROOT, "catalogs", "zee5_status.json")
OUT = os.path.join(ROOT, "playlists", "zee5.m3u")

UPSTREAM_FEED = "https://plugxvipplaylist.lovable.app/api/playlist"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg"
UA = "plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7"


def fetch_worldwide_channels():
    print(f"ZEE5: Fetching active ZEE5 Worldwide channels from feed...")
    try:
        req = urllib.request.Request(UPSTREAM_FEED, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8")
            blocks = re.findall(r'(#EXTINF:[^\n]+\n(?:[^\n]+\n)*?https?://[^\n]+)', text)
            ww_blocks = [b.strip() for b in blocks if 'group-title="ZEE5 Worldwide"' in b]
            print(f"ZEE5: Loaded {len(ww_blocks)} active ZEE5 Worldwide channels")
            return ww_blocks
    except Exception as e:
        print(f"ZEE5: Failed to fetch Worldwide channels ({e})")
        return []


def main():
    if not os.path.exists(CATALOG):
        print(f"Missing ZEE5 catalog: {CATALOG}")
        return 1

    with open(CATALOG, "r", encoding="utf-8") as f:
        india_channels = json.load(f)

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        "# Source: ZEE5 CloudFront DASH & Worldwide Edge",
        "",
    ]

    # 1. ZEE5 India (Clean DASH ClearKey streams)
    for ch in india_channels:
        cid = ch.get("id", "")
        name = ch.get("name", "")
        logo = ch.get("logo", GROUP_LOGO)
        cat = ch.get("cat", "Entertainment")
        url = ch.get("url", "")
        key = ch.get("key", "")

        is_dash = ".mpd" in url.lower()
        type_attr = ' type="dash"' if is_dash else ""

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{cat}" group-title="ZEE5 India" group-logo="{GROUP_LOGO}"{type_attr},{name}'
        )

        if is_dash and key:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")

        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    # 2. ZEE5 Worldwide
    ww_blocks = fetch_worldwide_channels()
    for block in ww_blocks:
        lines.append(block)
        lines.append("")

    total_count = len(india_channels) + len(ww_blocks)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": stamp,
            "total": total_count,
            "zee5_india": len(india_channels),
            "zee5_worldwide": len(ww_blocks)
        }, f, indent=2)

    print(f"ZEE5: Wrote {OUT} ({total_count} channels: {len(india_channels)} ZEE5 India, {len(ww_blocks)} ZEE5 Worldwide)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
