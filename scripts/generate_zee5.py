#!/usr/bin/env python3
"""
ZEE5 Live TV Playlist Generator & Sync.
Fetches both Indian & Worldwide channels from self-hosted Cloudflare Worker
(zee.gramnaters.workers.dev) with automatic fallback to local catalog.
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

WORKER_URL = "https://zee.gramnaters.workers.dev/playlist.m3u"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"


def fetch_from_worker():
    print(f"ZEE5: Fetching live channels from {WORKER_URL}...")
    try:
        req = urllib.request.Request(WORKER_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status == 200:
                content = resp.read().decode("utf-8")
                return content
    except Exception as e:
        print(f"ZEE5: Worker fetch failed ({e}), falling back to local catalog")
    return None


def parse_worker_m3u(m3u_text):
    channels = []
    lines = [line.strip() for line in m3u_text.splitlines() if line.strip()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF:"):
            inf = line
            url_line = None
            j = i + 1
            while j < len(lines):
                if lines[j].startswith("http://") or lines[j].startswith("https://"):
                    url_line = lines[j]
                    break
                j += 1

            cid_m = re.search(r'tvg-id="([^"]+)"', inf)
            name_m = re.search(r'tvg-name="([^"]+)"', inf)
            logo_m = re.search(r'tvg-logo="([^"]+)"', inf)
            cat_m = re.search(r'tvg-category="([^"]+)"', inf)
            grp_m = re.search(r'group-title="([^"]+)"', inf)

            raw_name = inf.split(",")[-1].strip()
            ch_name = name_m.group(1) if name_m else raw_name
            cid = cid_m.group(1) if cid_m else raw_name.lower().replace(" ", "-")
            logo = logo_m.group(1) if logo_m else GROUP_LOGO
            cat = cat_m.group(1) if cat_m else "Entertainment"
            
            # Determine group: Worldwide vs India
            is_worldwide = any(k in ch_name.lower() for k in ["usa", "uk", "me", "apac", "global", "africa", "middle east"])
            group = "ZEE5 Worldwide" if is_worldwide else "ZEE5 India"

            if url_line:
                channels.append({
                    "id": cid,
                    "name": ch_name,
                    "logo": logo,
                    "cat": cat,
                    "group": group,
                    "url": url_line,
                    "key": ""
                })
            i = j
        i += 1
    return channels


def generate_playlist(channels):
    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(channels)}",
        "# Source: ZEE5 Cloudflare Edge & Direct Streams",
        "",
    ]

    for ch in channels:
        cid = ch.get("id", "")
        name = ch.get("name", "")
        logo = ch.get("logo", GROUP_LOGO)
        cat = ch.get("cat", "Entertainment")
        group = ch.get("group", "ZEE5 India")
        url = ch.get("url", "")
        key = ch.get("key", "")

        is_dash = ".mpd" in url.lower()
        type_attr = ' type="dash"' if is_dash else ""

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{cat}" group-title="{group}" group-logo="{GROUP_LOGO}"{type_attr},{name}'
        )

        if is_dash and key:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")

        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(f"#EXTVLCOPT:http-referrer=https://www.zee5.com/")
        lines.append(f'#EXTHTTP:{{"User-Agent":"{UA}","Referrer":"https://www.zee5.com/","Origin":"https://www.zee5.com"}}')
        lines.append(url)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n", stamp


def main():
    channels = []
    worker_m3u = fetch_from_worker()
    if worker_m3u:
        parsed = parse_worker_m3u(worker_m3u)
        if len(parsed) >= 50:
            channels = parsed
            print(f"ZEE5: Successfully fetched and parsed {len(channels)} channels from Cloudflare worker")

    if not channels and os.path.exists(CATALOG):
        print(f"ZEE5: Using static catalog from {CATALOG}")
        with open(CATALOG, "r", encoding="utf-8") as f:
            channels = json.load(f)

    if not channels:
        print("ZEE5: Error - no channels available from worker or catalog")
        return 1

    content, stamp = generate_playlist(channels)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(content)

    os.makedirs(os.path.dirname(CATALOG), exist_ok=True)
    with open(CATALOG, "w", encoding="utf-8") as f:
        json.dump(channels, f, indent=2, ensure_ascii=False)

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": stamp,
            "total": len(channels),
            "source": "zee.gramnaters.workers.dev" if worker_m3u else "static_fallback",
            "groups": list(set(c.get("group", "ZEE5 India") for c in channels))
        }, f, indent=2)

    india_count = len([c for c in channels if c.get('group') == 'ZEE5 India'])
    world_count = len([c for c in channels if c.get('group') == 'ZEE5 Worldwide'])
    print(f"ZEE5: Wrote {OUT} ({len(channels)} channels: {india_count} ZEE5 India, {world_count} ZEE5 Worldwide)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
