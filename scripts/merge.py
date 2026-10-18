#!/usr/bin/env python3
"""
IPTV Auto-Updater & Aggregator
Updates and merges playlists for:
  - JioTV
  - JioHotstar
  - FanCode
  - VZY
  - Willow
  - SonyLIV
  - Prime Video

Outputs:
  - playlists/Combined.m3u (Merged categorized master playlist)
  - playlists/jiotv.m3u
  - playlists/jiohotstar.m3u
  - playlists/fancode.m3u
  - playlists/vzy.m3u
  - playlists/willow.m3u
  - playlists/sonyliv.m3u
  - playlists/prime.m3u
  - playlists/all_channels.json
"""

import os
import sys
import re
import json
import time
import requests
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output on Windows / Linux consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYLISTS_DIR = os.path.join(ROOT_DIR, "playlists")
COMBINED_M3U = os.path.join(ROOT_DIR, "Combined.m3u")
EPG_URL = "https://www.tsepg.cf/epg.xml.gz"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
JIOTV_USER_AGENT = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"

# Upstream feeds
SOURCES = {
    "JioHotstar": {
        "url": "https://jhs.gramnaters.workers.dev/",
        "group": "JioHotstar",
        "icon": "⭐"
    },
    "JioTV": {
        "url": "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/Geoplus.json",
        "cookie_source": "https://raw.githubusercontent.com/purupc00-dev/Gmax-JioTV/refs/heads/main/Playlists/JioTV_S10.m3u",
        "is_json": True,
        "group": "JioTV",
        "icon": "📡"
    },
    "FanCode": {
        "url": "https://raw.githubusercontent.com/doctor-8trange/zyphx8/refs/heads/main/data/fancode.m3u",
        "group": "FanCode",
        "icon": "🏏"
    },
    "VZY": {
        "url": "https://premiumplugx.me/vzy/playlist.php",
        "group": "VZY",
        "icon": "🎬"
    },
    "Willow": {
        "url": "https://raw.githubusercontent.com/srhady/willow-event/refs/heads/main/live_sports.m3u",
        "group": "Willow",
        "icon": "🏏"
    },
    "SonyLIV": {
        "url": "https://raw.githubusercontent.com/drmlive/sliv-live-events/refs/heads/main/sonyliv.m3u",
        "fallback_url": "https://sportlink-jtv.pages.dev/sony.json",
        "group": "SonyLIV",
        "icon": "📺"
    },
    "Prime Video": {
        "url": "https://raw.githubusercontent.com/srhady/willow-event/refs/heads/main/primevideo_sports.m3u",
        "group": "Prime Video",
        "icon": "🎥"
    }
}

CATEGORY_ORDER = [
    "Live Events",
    "Sports",
    "Cricket",
    "Football",
    "JioHotstar",
    "SonyLIV",
    "FanCode",
    "Willow",
    "Prime Video",
    "JioTV",
    "Entertainment",
    "Movies",
    "News",
    "Kids",
    "Music",
    "Infotainment",
    "Devotional",
    "Regional"
]

def get_current_ist():
    now = datetime.now(IST)
    return now.strftime("%d-%m-%Y %H:%M:%S IST")

def fetch_content(url, timeout=20):
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return ""

def fetch_jiotv_cookie():
    src = SOURCES["JioTV"]["cookie_source"]
    try:
        text = fetch_content(src, timeout=15)
        m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~"\r\n]+~hmac=[a-f0-9]+)', text)
        if m:
            return m.group(1)
    except Exception as e:
        print(f"⚠️ Failed to extract JioTV cookie: {e}")
    return ""

def extract_channel_blocks(raw_text):
    blocks = []
    current_block = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            if current_block:
                blocks.append(current_block)
            current_block = [line]
        elif current_block:
            current_block.append(line)
    if current_block:
        blocks.append(current_block)
    return blocks

def generate_jiotv_blocks(channels_json_str, cookie):
    try:
        channels = json.loads(channels_json_str)
    except Exception:
        return []

    blocks = []
    for ch in channels:
        cid = str(ch.get("id") or "")
        name = ch.get("name") or ""
        group = ch.get("group") or ch.get("category") or "JioTV"
        logo = ch.get("logo") or ""
        url = ch.get("url") or ""
        key_id = ch.get("keyId") or ""
        key = ch.get("key") or ""

        block = [f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" group-title="JioTV - {group}",{name}']

        if ".mpd" in url.lower():
            block.append("#KODIPROP:inputstream=inputstream.adaptive")
            block.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key_id and key:
                block.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                block.append(f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}")

        block.append(f"#EXTVLCOPT:http-user-agent={JIOTV_USER_AGENT}")
        if cookie:
            block.append(f"#EXTVLCOPT:http-cookie={cookie}")
            header_json = json.dumps({
                "User-Agent": JIOTV_USER_AGENT,
                "Origin": "https://www.jiotv.com/",
                "Referer": "https://www.jiotv.com/",
                "Cookie": cookie
            })
            block.append(f"#EXTHTTP:{header_json}")

        block.append(url)
        blocks.append(block)
    return blocks

def clean_and_normalize_block(block, source_name):
    normalized = []
    title = ""
    group = source_name

    for line in block:
        if line.startswith("#EXTINF"):
            # Extract channel title
            if "," in line:
                title = line.rsplit(",", 1)[1].strip()

            # Normalize or assign group-title
            m = re.search(r'group-title="([^"]*)"', line)
            if m and m.group(1).strip():
                existing_group = m.group(1).strip()
                # If existing group doesn't specify source, prepend or format it
                if source_name.lower() in existing_group.lower():
                    group = existing_group
                else:
                    group = f"{source_name} - {existing_group}"
                line = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', line)
            else:
                group = source_name
                line = line.replace("#EXTINF:-1 ", f'#EXTINF:-1 group-title="{group}" ')
            normalized.append(line)
        else:
            normalized.append(line)

    return group, normalized

def main():
    print("=" * 60)
    print(f"🚀 Master IPTV Auto-Updater starting at {get_current_ist()}")
    print("=" * 60)
    os.makedirs(PLAYLISTS_DIR, exist_ok=True)

    grouped_channels = {}
    total_channels = 0

    # 1. Process each source
    for source_name, config in SOURCES.items():
        print(f"\n📡 Processing {config['icon']} {source_name}...")
        raw_text = fetch_content(config["url"])
        if not raw_text:
            print(f"❌ Failed to fetch {source_name}")
            continue

        if config.get("is_json"):
            cookie = fetch_jiotv_cookie()
            blocks = generate_jiotv_blocks(raw_text, cookie)
        else:
            blocks = extract_channel_blocks(raw_text)

        # If live event feed is empty (e.g. no match broadcasting right now) and fallback exists
        if not blocks and config.get("fallback_url"):
            fb_text = fetch_content(config["fallback_url"])
            if fb_text.strip().startswith("["):
                try:
                    fb_channels = json.loads(fb_text)
                    for ch in fb_channels:
                        name = ch.get("name", "")
                        url = ch.get("streamUrl", "")
                        logo = ch.get("logo", "")
                        key_id = ch.get("keyId", "")
                        key = ch.get("key", "")
                        b = [f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" group-title="SonyLIV",{name}']
                        if key_id and key:
                            b.append("#KODIPROP:inputstream=inputstream.adaptive")
                            b.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
                            b.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                            b.append(f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}")
                        b.append(url)
                        blocks.append(b)
                except Exception:
                    pass

        print(f"✅ Loaded {len(blocks)} channels from {source_name}")

        # Save individual source M3U
        safe_name = source_name.lower().replace(" ", "")
        individual_file = os.path.join(PLAYLISTS_DIR, f"{safe_name}.m3u")
        with open(individual_file, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#DATE:- {get_current_ist()}\n")
            f.write(f"# Source: {source_name}\n\n")
            for b in blocks:
                f.write("\n".join(b) + "\n\n")

        # Accumulate into master category groups
        for b in blocks:
            cat, normalized_b = clean_and_normalize_block(b, source_name)
            grouped_channels.setdefault(cat, []).append(normalized_b)
            total_channels += 1

    # 2. Build Master Combined.m3u
    print("\n📦 Generating Master Combined Playlist...")
    master_lines = [
        f'#EXTM3U x-tvg-url="{EPG_URL}"',
        f'#DATE:- {get_current_ist()}',
        f'# Total Channels: {total_channels}',
        f'# Written and Maintained by GitHub Actions ⚡',
        ""
    ]

    # Sort categories according to priority order
    all_categories = list(grouped_channels.keys())
    ordered_cats = []
    for cat_prefix in CATEGORY_ORDER:
        matches = [c for c in all_categories if c.lower().startswith(cat_prefix.lower()) and c not in ordered_cats]
        ordered_cats.extend(matches)
    for c in sorted(all_categories):
        if c not in ordered_cats:
            ordered_cats.append(c)

    for cat in ordered_cats:
        channel_list = grouped_channels[cat]
        master_lines.append(f"# ===== {cat} ({len(channel_list)} Channels) =====")
        for block in channel_list:
            master_lines.extend(block)
            master_lines.append("")

    with open(COMBINED_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(master_lines))
    print(f"✅ Created {COMBINED_M3U} with {total_channels} channels ({os.path.getsize(COMBINED_M3U)} bytes)")

    print("\n" + "=" * 60)
    print("🎉 All playlists updated successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
