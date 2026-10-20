#!/usr/bin/env python3
import os
import sys
import re
import json
import time
import requests
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "jiotv.m3u")

# Cookie source: allinonereborn (the hub that mints the __hdnea__ token)
COOKIE_ENDPOINTS = [
    "https://allinonereborn2.online/jstrweb2/cookies.json",
]

# Channels catalog sources
CHANNELS_CATALOG = [
    "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/Geoplus.json"
]

USER_AGENT = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"
ORIGIN = "https://www.jiotv.com/"
REFERER = "https://www.jiotv.com/"

def get_ist_time():
    return datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")


def _expiry_hours(cookie):
    m = re.search(r"~exp=(\d+)~", cookie or "")
    if not m:
        return -1.0
    return (int(m.group(1)) - int(time.time())) / 3600.0


def fetch_live_cookie():
    """Directly fetch the live __hdnea__ cookie from the endpoint."""
    print("🔑 Fetching live JioTV cookie...")
    for url in COOKIE_ENDPOINTS:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for item in data:
                    c = (item or {}).get("cookie", "")
                    if c.startswith("__hdnea__="):
                        print(f"✅ Fetched cookie successfully from {url}")
                        return c.strip()
        except Exception as e:
            print(f"❌ Error fetching from {url}: {e}")
    return ""

def fetch_channels_catalog():
    print("📡 Fetching JioTV channel catalog...")
    for src in CHANNELS_CATALOG:
        try:
            r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                print(f"  ✅ Loaded {len(data)} channels from catalog")
                return data
        except Exception as e:
            print(f"  ⚠️ Error loading {src}: {e}")
    return []

def extract_drm_keys(channel):
    key_id = channel.get("keyId") or ""
    key = channel.get("key") or ""
    if not key_id and isinstance(channel.get("clearkey"), dict) and channel.get("clearkey"):
        try:
            key_id, key = next(iter(channel["clearkey"].items()))
        except StopIteration:
            pass
    return key_id, key

def generate_jiotv_playlist():
    cookie = fetch_live_cookie()
    channels = fetch_channels_catalog()

    if not channels:
        print("❌ Could not load the JioTV channel catalog - keeping the existing playlist")
        return False

    if not cookie:
        print("❌ No live __hdnea__ token - refusing to publish a tokenless JioTV playlist")
        if os.path.exists(OUTPUT_M3U):
            os.remove(OUTPUT_M3U)
            print("🗑️  Removed stale playlists/jiotv.m3u so merge.py falls back to the public feed")
        return False

    now_ist = get_ist_time()
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        f"# Category: jiotv",
        f"# Total Channels: {len(channels)}",
        ""
    ]

    for ch in channels:
        cid = str(ch.get("id") or "")
        name = ch.get("name") or "JioTV Channel"
        cat = ch.get("group") or ch.get("category") or "General"
        logo = ch.get("logo") or ""
        url = ch.get("url") or ""
        key_id, key = extract_drm_keys(ch)

        # Standard group-title format
        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="Jio TV+ | {cat}",{name}'
        )

        is_dash = ".mpd" in url.lower()
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key_id and key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}")

        # Kodi & VLC headers
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")

        header_dict = {
            "User-Agent": USER_AGENT,
            "Origin": ORIGIN,
            "Referer": REFERER
        }
        if cookie:
            header_dict["Cookie"] = cookie
            lines.append(f"#EXTVLCOPT:http-cookie={cookie}")

        lines.append(f"#EXTHTTP:{json.dumps(header_dict, ensure_ascii=False)}")
        lines.append(url)
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n🎉 Successfully generated {OUTPUT_M3U} with {len(channels)} channels.")
    print(f"🔒 Cookie injected: {cookie[:40]}... ({_expiry_hours(cookie):.2f} h left)")
    return True

if __name__ == "__main__":
    sys.exit(0 if generate_jiotv_playlist() else 1)
