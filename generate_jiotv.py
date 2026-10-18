#!/usr/bin/env python3
"""
Full JioTV Live Playlist & JSON Generator
Generates:
  - data/jiotv.json (Channels metadata, DRM ClearKeys, group categories, logos)
  - data/jiotv.m3u  (Full player-compatible M3U playlist with Kodi/Tivimate/VLC tags)

Features:
- Dynamically fetches active __hdnea__ Akamai stream cookies
- Maps ClearKeys (keyId:key) for Widevine/ClearKey DASH playback
- Sets proper Android ExoPlayer headers and origins
- Outputs structured data ready for local playback or Cloudflare hosting
"""

import os
import sys
import re
import json
import time
import requests
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

# ----------------- Configuration -----------------
AUTHOR_NAME = "DOCTOR STRANGE"
TELEGRAM_LINK = "https://t.me/jitendraunatti_github"
OUTPUT_DIR = "data"
OUTPUT_JSON = os.path.join(OUTPUT_DIR, "jiotv.json")
OUTPUT_M3U = os.path.join(OUTPUT_DIR, "jiotv.m3u")

CHANNELS_SOURCES = [
    "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/Geoplus.json"
]

COOKIE_SOURCES = [
    "https://raw.githubusercontent.com/purupc00-dev/Gmax-JioTV/refs/heads/main/Playlists/JioTV_S10.m3u",
    "https://allinonereborn2.online/jstrweb2/cookies.json"
]

USER_AGENT = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"
ORIGIN = "https://www.jiotv.com/"
REFERER = "https://www.jiotv.com/"

def get_current_ist_str():
    now = datetime.now(IST)
    return now.strftime("%d-%m-%Y %H:%M:%S IST")

def fetch_cookie():
    for src in COOKIE_SOURCES:
        try:
            r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            if r.status_code == 200:
                # 1. Search for M3U / text regex pattern
                match = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~"\r\n]+~hmac=[a-f0-9]+)', r.text)
                if match:
                    return match.group(1)
                
                # 2. Try JSON format
                try:
                    data = r.json()
                    if isinstance(data, list):
                        for item in data:
                            if "cookie" in item:
                                c = item["cookie"]
                                if c.startswith("__hdnea__="):
                                    return c
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ Error fetching cookie from {src}: {e}")
    return ""

def fetch_channels():
    for src in CHANNELS_SOURCES:
        try:
            print(f"📥 Fetching channels catalog from {src}...")
            r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return data
        except Exception as e:
            print(f"⚠️ Failed to fetch channels from {src}: {e}")
    return []

def extract_keys(channel):
    key_id = channel.get("keyId") or ""
    key = channel.get("key") or ""
    if not key_id and isinstance(channel.get("clearkey"), dict) and channel.get("clearkey"):
        try:
            key_id, key = next(iter(channel["clearkey"].items()))
        except StopIteration:
            pass
    return key_id, key

def build_jiotv_json(channels, cookie):
    result = {
        "Author": AUTHOR_NAME,
        "Telegram": TELEGRAM_LINK,
        "name": "JioTV Live Channels API",
        "last_updated": get_current_ist_str(),
        "total_channels": len(channels),
        "cookie": cookie,
        "app_settings": {
            "PROXY": "OFF",
            "MULTI_CDN": "ON",
            "USER_AGENT": USER_AGENT,
            "PLAYER": "ExoPlayer / Shaka / Kodi"
        },
        "channels": []
    }

    for ch in channels:
        key_id, key = extract_keys(ch)
        cid = str(ch.get("id") or "")
        name = ch.get("name") or ""
        group = ch.get("group") or ch.get("category") or "General"
        logo = ch.get("logo") or ""
        url = ch.get("url") or ""

        result["channels"].append({
            "id": cid,
            "name": name,
            "group": group,
            "logo": logo,
            "url": url,
            "keyId": key_id,
            "key": key
        })

    return result

def build_jiotv_m3u(jiotv_json):
    cookie = jiotv_json.get("cookie", "")
    lines = [
        "#EXTM3U",
        f"#DATE:- {jiotv_json['last_updated']}",
        f"# Written and Directed by ✨ D O C T O R - S T R A N G E ✨",
        f"# Total Channels: {jiotv_json['total_channels']}"
    ]

    for ch in jiotv_json.get("channels", []):
        cid = ch["id"]
        name = ch["name"]
        group = ch["group"]
        logo = ch["logo"]
        stream_url = ch["url"]
        key_id = ch["keyId"]
        key = ch["key"]

        lines.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}')

        # Add ClearKey DRM properties for DASH manifests
        is_dash = ".mpd" in stream_url.lower()
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key_id and key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}")

        # Add player stream headers
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
        lines.append(stream_url)

    return "\n".join(lines) + "\n"

def main():
    print("🚀 Running JioTV Playlist & JSON Generator...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("🔑 Fetching active JioTV / Akamai stream cookie...")
    cookie = fetch_cookie()
    if cookie:
        print(f"✅ Found active cookie: {cookie[:50]}...")
    else:
        print("⚠️ No cookie retrieved; requests might require authentication on live streams.")

    channels = fetch_channels()
    print(f"✅ Loaded {len(channels)} channels.")

    # Write JSON
    jiotv_json = build_jiotv_json(channels, cookie)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(jiotv_json, f, indent=2, ensure_ascii=False)
    print(f"✅ Wrote JSON to {OUTPUT_JSON} ({os.path.getsize(OUTPUT_JSON)} bytes)")

    # Write M3U
    jiotv_m3u = build_jiotv_m3u(jiotv_json)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(jiotv_m3u)
    print(f"✅ Wrote M3U to {OUTPUT_M3U} ({os.path.getsize(OUTPUT_M3U)} bytes)")

if __name__ == "__main__":
    main()
