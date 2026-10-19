#!/usr/bin/env python3
"""
SonyLIV Playlist Generator (own catalog)

The channel list is OURS: channels/sony_catalog.json (22 channels, baked).
This replaces the three third-party SONY_CATALOG_SOURCES that used to be
scraped at runtime:

    doctor-8trange/zyphora/data/sony.json          -> event catalog, 1 stream
    sportlive18/Sonyliv-Playlist-Autoupdate/...     -> event catalog, 2 streams
    sm-monirulislam/SonyLiv_Event_Playlist/...      -> event catalog, 15 matches

Those three are EVENT lists, not channel lists - between them they carry a
single playable URL, so they can never produce the 22 SonyLIV channels.
The 22 real channels are baked here instead.

Auth: NOT ours. All 22 streams are served by the sliv.tgaadi Cloudflare
worker, which mints the Akamai `hdntl` token and rewrites the master
playlist so the variant URIs are bare `hdntl=exp=..~hmac=..` strings.
That token is minted server-side and cannot be derived here, so SonyLIV
stays a third-party-auth category - like JioTV and FanCode.

NOTE: the allinonereborn cookies.json is a **JioTV** token (`acl=/*`). It
was previously appended to Sony URLs as `?hdnea=`; it does nothing there.
Verified: Sony's CDN returns 403 with AND without it. That code is gone.

Reads:  channels/sony_catalog.json
Writes: playlists/sonyliv.m3u   (deleted on total failure so merge.py can
                                 fall back to the public feed)
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
CATALOG_FILE = os.path.join(ROOT_DIR, "channels", "sony_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sonyliv.m3u")

MIN_CHANNELS = 5

DEFAULT_UA = "plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7"
DEFAULT_GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png"
GROUP = "Sony LIV"


def probe(url, ua, timeout=12):
    """True if the worker still returns a real HLS master playlist."""
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": ua or DEFAULT_UA}, timeout=timeout)
        return r.status_code == 200 and r.text.lstrip().startswith("#EXTM3U")
    except Exception:
        return False


def generate_sony_playlist(verify=True):
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    if not os.path.exists(CATALOG_FILE):
        print(f"❌ Catalog file {CATALOG_FILE} not found!")
        return False

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    live = []
    dead = []
    for ch in catalog:
        url = ch.get("url", "")
        if not url:
            continue
        ua = ch.get("ua") or DEFAULT_UA
        if verify and not probe(url, ua):
            dead.append(ch.get("name", url))
            continue
        live.append(ch)

    if len(live) < MIN_CHANNELS:
        print(f"❌ Only {len(live)}/{len(catalog)} SonyLIV channels responded "
              f"(need >= {MIN_CHANNELS}) - not writing the playlist")
        if os.path.exists(OUTPUT_M3U):
            os.remove(OUTPUT_M3U)
            print("🗑️  Removed stale playlists/sonyliv.m3u so merge.py falls back to the public feed")
        return False

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: sonyliv",
        f"# Total Channels: {len(live)}",
        "# Source: channels/sony_catalog.json (own catalog; auth minted by the stream worker)",
        ""
    ]

    for ch in live:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch.get("id","")}" tvg-name="{ch.get("name","")}" '
            f'tvg-logo="{ch.get("logo","")}" tvg-category="{ch.get("category","")}" '
            f'tvg-language="{ch.get("language","")}" group-title="{ch.get("group") or GROUP}" '
            f'group-logo="{ch.get("group_logo") or DEFAULT_GROUP_LOGO}",{ch.get("name","")}'
        )
        lines.append(f'#EXTVLCOPT:http-user-agent={ch.get("ua") or DEFAULT_UA}')
        lines.append(ch["url"])
        lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ Generated {OUTPUT_M3U} ({len(live)} SonyLIV channels)")
    if dead:
        print(f"   ⚠️ dropped {len(dead)} dead: {', '.join(dead[:6])}{'...' if len(dead) > 6 else ''}")
    return True


if __name__ == "__main__":
    verify = "--no-verify" not in sys.argv
    sys.exit(0 if generate_sony_playlist(verify=verify) else 1)
