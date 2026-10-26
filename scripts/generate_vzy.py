#!/usr/bin/env python3
"""
VZY live TV playlist generator.
Produces playlists/vzy.m3u from catalogs/vzy_catalog.json with ClearKeys for DASH channels.
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
CATALOG = os.path.join(ROOT, "catalogs", "vzy_catalog.json")
STATUS = os.path.join(ROOT, "catalogs", "vzy_status.json")
OUT = os.path.join(ROOT, "playlists", "vzy.m3u")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
GROUP_LOGO = "https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/entry_id/bab798478e714be3a5ae861fc04606f0/version/0"


def main():
    if not os.path.exists(CATALOG):
        print(f"Missing catalog: {CATALOG}")
        return 1

    with open(CATALOG, "r", encoding="utf-8") as f:
        channels = json.load(f)

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(channels)}",
        "",
    ]

    for ch in channels:
        cid = str(ch.get("id") or "")
        name = ch.get("name") or "VZY Channel"
        grp = ch.get("group") or "VZY"
        logo = ch.get("logo") or GROUP_LOGO
        url = ch.get("url") or ""
        key = ch.get("key") or ""

        is_dash = ".mpd" in url.lower()
        type_attr = ' type="dash"' if is_dash else ''

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{grp}" group-title="VZY" group-logo="{GROUP_LOGO}"{type_attr},{name}'
        )

        if is_dash and key:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")

        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({"updated_at": stamp, "total": len(channels)}, f, indent=2)

    print(f"VZY: wrote {OUT} ({len(channels)} channels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
