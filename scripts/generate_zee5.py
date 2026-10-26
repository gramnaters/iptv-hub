#!/usr/bin/env python3
"""
ZEE5 Live TV Playlist Generator.
Generates playlists/zee5.m3u from catalogs/zee5_catalog.json containing pure,
verified Zee network channels with official logos and CloudFront DASH ClearKeys.
"""
import json
import os
import sys
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

UA = "plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg"


def main():
    if not os.path.exists(CATALOG):
        print(f"Missing ZEE5 catalog: {CATALOG}")
        return 1

    with open(CATALOG, "r", encoding="utf-8") as f:
        channels = json.load(f)

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(channels)}",
        "# Category: ZEE5",
        "",
    ]

    for ch in channels:
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
            f'tvg-category="{cat}" group-title="ZEE5" group-logo="{GROUP_LOGO}"{type_attr},{name}'
        )

        if is_dash and key:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")

        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({"updated_at": stamp, "total": len(channels)}, f, indent=2)

    print(f"ZEE5: wrote {OUT} ({len(channels)} pure Zee channels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
