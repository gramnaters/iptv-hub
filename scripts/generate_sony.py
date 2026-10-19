#!/usr/bin/env python3
"""
SonyLIV Playlist Generator — minted from the allinonereborn Sony API

Catalog source (ours now, not three scraped repos):
    https://allinonereborn2.online/sony/sliv3.json

The hub exposes three Sony catalogs; only sliv3 is live:
    sliv.json   - 22 ch, inline hdnea tokens  -> EXPIRED (exp 1766493005)
    sliv2.json  - 22 ch, inline hdnea tokens  -> EXPIRED (exp 1771914784)
    sliv3.json  - 22 ch, hub playlist paths   -> LIVE  (mints a fresh hdntl each fetch)

sliv3 entries point at the hub's own playlist, e.g.
    https://allinonereborn2.online/sony-new/playlists/sony_hd.m3u8
which resolves to the real Sony CDN with a freshly minted token:
    https://dishmt.slivcdn.com/hls/live/2011671/SETHD/hdntl=exp=..~hmac=..  /master_108.m3u8

Because the playlist holds a POINTER (not a token), nothing goes stale: the hub
mints a new ~11 h hdntl every time the playlist is fetched. The only thing that
needs refreshing is the channel LIST, which is what this script mints.

Playback notes:
  - the hub playlist needs a Referer (403 without, 200 with any Referer) -> emitted
    as #EXTVLCOPT:http-referrer and inside #EXTHTTP
  - the slivcdn variant/segment URLs play bare (no token, no headers needed)

Reads:  https://allinonereborn2.online/sony/sliv3.json
Writes: playlists/sonyliv.m3u
        channels/sony_catalog.json   (cache of the minted catalog)
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
CATALOG_CACHE_FILE = os.path.join(ROOT_DIR, "channels", "sony_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sonyliv.m3u")

# Sony catalog on the same hub that mints the JioTV token
SONY_API = "https://allinonereborn2.online/sony/sliv3.json"

HUB = "https://allinonereborn2.online"
REFERER = HUB + "/"
ORIGIN = HUB

USER_AGENT = "plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7"
GROUP = "Sony LIV"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png"

MIN_CHANNELS = 5


def fetch_sony_catalog():
    """Mint the catalog from the hub; fall back to the cached copy."""
    print(f"📡 Minting SonyLIV catalog from {SONY_API}...")
    try:
        import requests
        r = requests.get(SONY_API, headers={"User-Agent": USER_AGENT}, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data:
            catalog = []
            for key, ch in data.items():
                url = (ch or {}).get("m3u8") or (ch or {}).get("url") or ""
                if not url:
                    continue
                catalog.append({
                    "id": ch.get("id") or key,
                    "name": ch.get("title") or key,
                    "logo": ch.get("logo") or "",
                    "category": ch.get("genre") or "Entertainment",
                    "language": ch.get("language") or "",
                    "group": GROUP,
                    "url": url,
                })
            if catalog:
                print(f"  ✅ Minted {len(catalog)} channels")
                os.makedirs(os.path.dirname(CATALOG_CACHE_FILE), exist_ok=True)
                with open(CATALOG_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(catalog, f, indent=2, ensure_ascii=False)
                return catalog
            print("  ⚠️ API returned an empty catalog")
    except Exception as e:
        print(f"  ⚠️ Error minting from the hub: {e}")

    if os.path.exists(CATALOG_CACHE_FILE):
        try:
            with open(CATALOG_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            print(f"  🔄 Using cached SonyLIV catalog ({len(cached)} channels)")
            return cached
        except Exception:
            pass
    return []


def probe(url, timeout=12):
    """(ok, detail) - the hub playlist needs a Referer."""
    try:
        import requests
        r = requests.get(url, headers={
            "User-Agent": USER_AGENT,
            "Referer": REFERER,
            "Origin": ORIGIN,
        }, timeout=timeout)
        if r.status_code == 200 and r.text.lstrip().startswith("#EXTM3U"):
            return True, "200"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, type(e).__name__


def generate_sony_playlist(verify=True):
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    catalog = fetch_sony_catalog()
    if not catalog:
        print("❌ No SonyLIV catalog available (hub + cache both empty)")
        return False

    live, dead, why = [], [], []
    if verify:
        for ch in catalog:
            ok, detail = probe(ch["url"])
            if ok:
                live.append(ch)
            else:
                dead.append(ch["name"])
                why.append(detail)

    if verify and len(live) < MIN_CHANNELS:
        # Not enough signal to prune. This is the environment, not the channels:
        # a datacenter IP can be refused even when a real ISP client streams fine.
        # Publishing the full minted catalog beats pruning good channels.
        print(f"⚠️ Only {len(live)}/{len(catalog)} responded ({', '.join(sorted(set(why))[:4]) or 'n/a'})")
        print("⚠️ Treating this as 'verification unavailable here', NOT as dead channels")
        live = list(catalog)
        dead = []

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: sonyliv",
        f"# Total Channels: {len(live)}",
        f"# Source: {SONY_API} (allinonereborn mints the hdntl token)",
        ""
    ]

    for ch in live:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch.get("id","")}" tvg-name="{ch.get("name","")}" '
            f'tvg-logo="{ch.get("logo","")}" tvg-category="{ch.get("category","")}" '
            f'tvg-language="{ch.get("language","")}" group-title="{ch.get("group") or GROUP}" '
            f'group-logo="{GROUP_LOGO}",{ch.get("name","")}'
        )
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(f'#EXTHTTP:{json.dumps({"User-Agent": USER_AGENT, "Referer": REFERER, "Origin": ORIGIN}, ensure_ascii=False)}')
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
