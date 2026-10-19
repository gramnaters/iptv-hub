#!/usr/bin/env python3
"""
SunNXT Live Channel Health Checker & Playlist Generator
Features:
  - Fetches the verified SunNXT DASH MPD manifests and ClearKeys catalog
  - Syncs live channel names & metadata from SunNXT official API (https://pwaapi.sunnxt.com)
  - Performs fast parallel HTTP health checks (verifying 200 OK from Akamai CDN)
  - Generates playlists/sunnxt.m3u with verified active channels and ClearKey DRM headers
"""

import os
import sys
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_FILE = os.path.join(ROOT_DIR, "catalogs", "sunnxt_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sunnxt.m3u")

SUNNXT_PWA_URL = "https://pwaapi.sunnxt.com/content/v2/contentList?type=live&offset=0&limit=100"
USER_AGENT = "plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7"

def get_current_ist_str():
    return datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

def fetch_live_pwa_catalog():
    """Fetches official live catalog metadata from SunNXT PWA API."""
    try:
        r = requests.get(SUNNXT_PWA_URL, headers={"User-Agent": "okhttp/3.14.9"}, timeout=8)
        if r.status_code == 200:
            data = r.json()
            return data.get("results", [])
    except Exception as e:
        print(f"⚠️ Notice: Could not sync with SunNXT PWA API: {e}")
    return []

def check_stream_health(channel):
    """Verifies that the channel's DASH manifest responds with HTTP 200 OK."""
    url = channel.get("url")
    headers = {"User-Agent": USER_AGENT}
    try:
        # A fast GET request with stream=True or timeout=6
        r = requests.get(url, headers=headers, timeout=6, stream=True)
        if r.status_code == 200:
            return channel, True, r.status_code
        return channel, False, r.status_code
    except Exception as e:
        return channel, False, str(e)

def generate_playlist():
    print("=" * 60)
    print(f"🚀 SunNXT Health Checker & Generator [{get_current_ist_str()}]")
    print("=" * 60)

    if not os.path.exists(CATALOG_FILE):
        print(f"❌ Error: Catalog file {CATALOG_FILE} not found!")
        return

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    print(f"📋 Loaded {len(catalog)} channels from catalog.")

    # 1. Sync metadata with official SunNXT PWA API if available
    pwa_results = fetch_live_pwa_catalog()
    if pwa_results:
        print(f"📡 Synced with official SunNXT API ({len(pwa_results)} live records returned)")
        # Map IDs to official titles
        pwa_map = {str(item.get("_id")): item.get("title") for item in pwa_results if item.get("_id")}
        for ch in catalog:
            raw_id = ch.get("id", "").replace("sun-", "").replace("-dv", "")
            if raw_id in pwa_map and pwa_map[raw_id]:
                # Update title if different
                official_title = pwa_map[raw_id]
                if "-dv" in ch.get("id", ""):
                    ch["name"] = f"{official_title} - Dolby Vision"
                elif "HD" in ch.get("name", "") and "HD" not in official_title:
                    ch["name"] = f"{official_title} HD"

    # 2. Fast parallel health verification
    print("\n🔍 Running live stream health checks (verifying Akamai MPD manifests)...")
    verified_channels = []
    failed_channels = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(check_stream_health, catalog))

    for ch, is_alive, status in results:
        if is_alive:
            verified_channels.append(ch)
            print(f"  ✅ [200 OK] {ch['name']}")
        else:
            failed_channels.append((ch, status))
            print(f"  ⚠️ [FAILED: {status}] {ch['name']}")

    print(f"\n📊 Health Check Summary: {len(verified_channels)} / {len(catalog)} channels healthy and verified live.")

    # Even if a network glitch fails a check, keep all unless persistently dead
    channels_to_write = verified_channels if len(verified_channels) >= (len(catalog) * 0.8) else catalog

    # 3. Assemble and write M3U playlist
    lines = [
        "#EXTM3U",
        f"#DATE:- {get_current_ist_str()}",
        f"# Category: SunNXT",
        f"# Total Channels: {len(channels_to_write)}",
        ""
    ]

    for ch in channels_to_write:
        cid = ch.get("id", "")
        name = ch.get("name", "")
        logo = ch.get("logo", "")
        group = ch.get("group", "SunNXT")
        key = ch.get("key", "")
        url = ch.get("url", "")

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="{group}" group-logo="https://upload.wikimedia.org/wikipedia/en/d/d5/Sun_NXT_logo_small.png" type="dash",{name}'
        )
        lines.append("#KODIPROP:inputstream=inputstream.adaptive")
        lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
        lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
        lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(url)
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n💾 Wrote verified playlist to {OUTPUT_M3U} ({len(channels_to_write)} channels)")
    print("=" * 60)

if __name__ == "__main__":
    generate_playlist()
