#!/usr/bin/env python3
"""
Independent JioTV Master Playlist & Cookie Refresh Engine

Cookie source (single, deliberate):
    1. https://allinonereborn2.online/jstrweb2/cookies.json

The __hdnea__ Akamai token cannot be derived from any cookie or algorithm -
it is minted by a JioTV hub that holds a real Jio login. This script
therefore harvests the token from ONE upstream (allinonereborn) instead of
scraping a chain of mirrors, and caches it so an outage degrades instead of
breaking the build.

- Loads the 1,200+ JioTV channels catalog with Widevine ClearKeys
- Injects live cookies into Kodi (#KODIPROP), VLC (#EXTVLCOPT), and HTTP headers (#EXTHTTP)
- Outputs:
    - playlists/jiotv.m3u
    - channels/jiotv_catalog.json  (channel catalog cache - committed, changes slowly)
    - channels/jiotv_cookie.json   (token cache - GIT-IGNORED, ~6 h TTL, never committed)
"""

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
CATALOG_CACHE_FILE = os.path.join(ROOT_DIR, "channels", "jiotv_catalog.json")
COOKIE_CACHE_FILE = os.path.join(ROOT_DIR, "channels", "jiotv_cookie.json")

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

def _cache_cookie(cookie, source):
    """Write the harvested token to the (git-ignored) runtime cache."""
    try:
        os.makedirs(os.path.dirname(COOKIE_CACHE_FILE), exist_ok=True)
        with open(COOKIE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({"updated_at": get_ist_time(), "source": source, "cookie": cookie}, f, indent=2)
    except Exception:
        pass


def _expiry_hours(cookie):
    m = re.search(r"~exp=(\d+)~", cookie or "")
    if not m:
        return -1.0
    return (int(m.group(1)) - int(time.time())) / 3600.0


def fetch_live_cookie():
    """Extracts the freshest active __hdnea__ cookie from the one hub we trust."""
    print("🔑 Searching for active JioTV Akamai cookie...")
    for url in COOKIE_ENDPOINTS:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code != 200:
                continue
            # 1. Regex search for the __hdnea__ parameter
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~"\r\n]+~hmac=[a-f0-9]+)', r.text)
            if not m:
                # 2. Try the JSON schema
                try:
                    for item in r.json():
                        c = (item or {}).get("cookie", "")
                        if c.startswith("__hdnea__="):
                            m = re.match(r"(__hdnea__=.*)", c.strip())
                            break
                except Exception:
                    pass
            if m:
                cookie = m.group(1).strip()
                left = _expiry_hours(cookie)
                if left <= 0:
                    print(f"  ⚠️ {url} returned an already-expired token - skipping")
                    continue
                print(f"  ✅ Harvested active cookie from: {url} ({left:.2f} h left)")
                _cache_cookie(cookie, url)
                return cookie
        except Exception as e:
            print(f"  ⚠️ Warning for {url}: {e}")

    # Fallback: a locally cached token, but ONLY while it is still valid.
    # The cron runs every 24h while a token lives ~6h, so a committed cache
    # is always dead by the next run - never inject one blindly.
    if os.path.exists(COOKIE_CACHE_FILE):
        try:
            with open(COOKIE_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            cookie = cached.get("cookie", "")
            left = _expiry_hours(cookie)
            if left > 0.25:
                print(f"  🔄 Using cached cookie from {cached.get('updated_at')} ({left:.2f} h left)")
                return cookie
            print(f"  ⚠️ Cached cookie is expired ({left:.2f} h) - ignoring it")
        except Exception:
            pass

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
                os.makedirs(os.path.dirname(CATALOG_CACHE_FILE), exist_ok=True)
                with open(CATALOG_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                return data
        except Exception as e:
            print(f"  ⚠️ Error loading {src}: {e}")

    # Fallback to the baked catalog cache
    if os.path.exists(CATALOG_CACHE_FILE):
        try:
            with open(CATALOG_CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  🔄 Using cached channel catalog ({len(data)} channels)")
            return data
        except Exception:
            pass
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
        print("❌ Could not load channel catalog. Aborting.")
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
            f'group-title="JioTV - {cat}",{name}'
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
