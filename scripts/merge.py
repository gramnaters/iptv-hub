#!/usr/bin/env python3
"""
IPTV Auto-Updater & Master Aggregator
Generates comprehensive IPTV master playlist matching and exceeding PremiumPlug/sportslink:
  - JioHotstar (User's Independent Worker - https://jhs.gramnaters.workers.dev/)
  - Jio TV+ Categories (News, Entertainment, Devotional, Movies, Kids, Music, Sports, Education, Infotainment, Lifestyle, Specials, Shopping, etc.)
  - ZEE5 Worldwide (112 channels)
  - ZEE5 India (33 channels)
  - 24/7 kids + Goldmines pack (14 channels)
  - WOW KIDZ (3 channels)
  - Dangal Play (4 channels)
  - VZY (48 channels)
  - FanCode (Live & Upcoming Sports)
  - SonyLIV / Sonyliv events
  - SunNXT (33 channels)
  - Willow (Cricket)
  - Prime Video (Sports)

Outputs:
  - Combined.m3u (Master playlist in root directory)
  - playlists/Combined.m3u
  - playlists/<source>.m3u
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
PLAYLISTS_DIR = os.path.join(ROOT_DIR, "playlists")
COMBINED_M3U = os.path.join(ROOT_DIR, "Combined.m3u")
EPG_URL = "https://avkb.short.gy/jioepg.xml.gz"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# User's dedicated independent JioHotstar worker
USER_JIOHOTSTAR_URL = "https://jhs.gramnaters.workers.dev/"

# Upstream public feeds
PUBLIC_PLUG_API = "https://plugxvipplaylist.lovable.app/api/playlist"
LOCAL_PLUG_BACKUP = os.path.join(os.path.dirname(ROOT_DIR), "premiumplug_full.m3u")

EXTRA_FEEDS = {
    "Willow": {
        "url": "https://raw.githubusercontent.com/srhady/willow-event/refs/heads/main/live_sports.m3u",
        "group": "Willow",
        "icon": "🏏"
    },
    "Prime Video": {
        "url": "https://raw.githubusercontent.com/srhady/willow-event/refs/heads/main/primevideo_sports.m3u",
        "group": "Prime Video",
        "icon": "🎥"
    }
}

def get_current_ist():
    now = datetime.now(IST)
    return now.strftime("%d-%m-%Y %H:%M:%S IST")

def fetch_content(url, timeout=25):
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return ""

def extract_channel_blocks(raw_text):
    blocks = []
    current_block = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#EXTM3U") or line.startswith("# Generated") or line.startswith("#DATE"):
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

def clean_watermarks_from_block(block):
    """Purge unwanted watermarks or promotional metadata from blocks."""
    cleaned = []
    watermark_patterns = [
        r'DOCTOR\s*STRANGE',
        r'jitendraunatti',
        r'virat10',
        r't\.me/[^\s\"\'\)]+'
    ]
    for line in block:
        for pat in watermark_patterns:
            line = re.sub(pat, '', line, flags=re.IGNORECASE)
        cleaned.append(line.strip())
    return [l for l in cleaned if l]

def get_block_group(block):
    for line in block:
        if line.startswith("#EXTINF"):
            m = re.search(r'group-title="([^"]*)"', line)
            if m:
                return m.group(1).strip()
    return "Other"

def main():
    print("=" * 60)
    print(f"🚀 Master IPTV Auto-Updater starting at {get_current_ist()}")
    print("=" * 60)
    os.makedirs(PLAYLISTS_DIR, exist_ok=True)

    all_channels_by_group = {}

    # -------------------------------------------------------------
    # 1. Fetch User's Independent JioHotstar Feed
    # -------------------------------------------------------------
    print(f"\n⭐ Fetching independent JioHotstar from {USER_JIOHOTSTAR_URL}...")
    jhs_text = fetch_content(USER_JIOHOTSTAR_URL)
    jhs_blocks = []
    if jhs_text:
        raw_jhs_blocks = extract_channel_blocks(jhs_text)
        for b in raw_jhs_blocks:
            # Force group-title="JioHotstar"
            norm_b = []
            for l in b:
                if l.startswith("#EXTINF"):
                    if 'group-title=' in l:
                        l = re.sub(r'group-title="[^"]*"', 'group-title="JioHotstar"', l)
                    else:
                        l = l.replace('#EXTINF:-1 ', '#EXTINF:-1 group-title="JioHotstar" ')
                norm_b.append(l)
            jhs_blocks.append(clean_watermarks_from_block(norm_b))
        print(f"✅ Loaded {len(jhs_blocks)} independent JioHotstar channels")
    else:
        print("⚠️ Could not load independent JioHotstar, check worker status")

    if jhs_blocks:
        all_channels_by_group["JioHotstar"] = jhs_blocks

    # -------------------------------------------------------------
    # 2. Fetch Public Feeds (ZEE5, FanCode, VZY, SunNXT, Kids, Dangal, Jio TV+ Packs)
    # -------------------------------------------------------------
    print(f"\n📡 Fetching comprehensive catalog from {PUBLIC_PLUG_API}...")
    plug_text = fetch_content(PUBLIC_PLUG_API)
    if not plug_text and os.path.exists(LOCAL_PLUG_BACKUP):
        print("⚠️ Live API timed out, loading from local backup cache...")
        with open(LOCAL_PLUG_BACKUP, "r", encoding="utf-8") as f:
            plug_text = f.read()

    plug_blocks = extract_channel_blocks(plug_text) if plug_text else []
    print(f"✅ Loaded {len(plug_blocks)} total public channel items")

    # Accumulate non-JioHotstar channels from the public catalog
    for b in plug_blocks:
        grp = get_block_group(b)
        # Skip JioHotstar from public feed because user has their own independent worker!
        if grp.lower() == "jiohotstar":
            continue
        cleaned_b = clean_watermarks_from_block(b)
        all_channels_by_group.setdefault(grp, []).append(cleaned_b)

    # -------------------------------------------------------------
    # 3. Add Extra Feeds (Willow, Prime Video)
    # -------------------------------------------------------------
    for name, cfg in EXTRA_FEEDS.items():
        print(f"\n{cfg['icon']} Fetching {name} from {cfg['url']}...")
        extra_text = fetch_content(cfg["url"])
        if extra_text:
            eblocks = extract_channel_blocks(extra_text)
            norm_eblocks = []
            for b in eblocks:
                norm_b = []
                for l in b:
                    if l.startswith("#EXTINF"):
                        if 'group-title=' in l:
                            norm_b.append(re.sub(r'group-title="[^"]*"', f'group-title="{cfg["group"]}"', l))
                        else:
                            norm_b.append(l.replace('#EXTINF:-1 ', f'#EXTINF:-1 group-title="{cfg["group"]}" '))
                    else:
                        norm_b.append(l)
                norm_eblocks.append(clean_watermarks_from_block(norm_b))
            print(f"✅ Loaded {len(norm_eblocks)} channels from {name}")
            all_channels_by_group.setdefault(cfg["group"], []).extend(norm_eblocks)

    # -------------------------------------------------------------
    # 4. Save Individual Category/Service M3U Files in playlists/
    # -------------------------------------------------------------
    # Mapping for clean individual playlists
    individual_categories = {
        "jiohotstar": ["JioHotstar"],
        "fancode": ["FanCode"],
        "vzy": ["VZY"],
        "willow": ["Willow"],
        "prime": ["Prime Video"],
        "sonyliv": ["Sony LIV", "Sonyliv events"],
        "sunnxt": ["SunNXT"],
        "zee5": ["ZEE5 India", "ZEE5 Worldwide"],
        "dangal": ["Dangal Play"],
        "kids": ["24/7 kids+Goldmines pack", "WOW KIDZ", "Jio TV+ | Kids"],
        "jiotv": [g for g in all_channels_by_group.keys() if g.startswith("Jio TV+")]
    }

    print("\n💾 Writing individual playlists to playlists/...")
    for filename, group_names in individual_categories.items():
        cat_blocks = []
        for g in group_names:
            cat_blocks.extend(all_channels_by_group.get(g, []))
        out_path = os.path.join(PLAYLISTS_DIR, f"{filename}.m3u")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("#EXTM3U\n")
            f.write(f"#DATE:- {get_current_ist()}\n")
            f.write(f"# Category: {filename}\n")
            f.write(f"# Total Channels: {len(cat_blocks)}\n\n")
            for b in cat_blocks:
                f.write("\n".join(b) + "\n\n")
        print(f"  📁 {filename}.m3u ({len(cat_blocks)} channels)")

    # -------------------------------------------------------------
    # 5. Assemble Master Combined.m3u
    # -------------------------------------------------------------
    print("\n📦 Generating Master Combined.m3u...")

    # Canonical order of groups
    PRIORITY_GROUPS = [
        "JioHotstar",
        "FanCode",
        "Willow",
        "Sony LIV",
        "Sonyliv events",
        "Prime Video",
        "SunNXT",
        "VZY",
        "ZEE5 India",
        "ZEE5 Worldwide",
        "Dangal Play",
        "24/7 kids+Goldmines pack",
        "WOW KIDZ",
        "Jio TV+ | Sports",
        "Jio TV+ | News",
        "Jio TV+ | Entertainment",
        "Jio TV+ | Movies",
        "Jio TV+ | Kids",
        "Jio TV+ | Music",
        "Jio TV+ | Devotional",
        "Jio TV+ | Infotainment",
        "Jio TV+ | Lifestyle",
        "Jio TV+ | Education",
        "Jio TV+ | Business",
        "Jio TV+ | Specials",
        "Jio TV+ | Shopping",
        "Jio TV+ | Other"
    ]

    # Include any groups that may not be explicitly listed
    all_known_groups = []
    for g in PRIORITY_GROUPS:
        if g in all_channels_by_group and g not in all_known_groups:
            all_known_groups.append(g)
    for g in sorted(all_channels_by_group.keys()):
        if g not in all_known_groups:
            all_known_groups.append(g)

    total_combined_channels = sum(len(all_channels_by_group[g]) for g in all_known_groups)

    master_lines = [
        f'#EXTM3U x-tvg-url="{EPG_URL}" url-tvg="{EPG_URL}" refresh="86400"',
        f'#DATE:- {get_current_ist()}',
        f'# Total Channels: {total_combined_channels}',
        ""
    ]

    for g in all_known_groups:
        blocks = all_channels_by_group[g]
        master_lines.append(f"# ===== {g} ({len(blocks)} Channels) =====")
        for b in blocks:
            master_lines.extend(b)
            master_lines.append("")

    combined_content = "\n".join(master_lines)

    # Write root Combined.m3u
    with open(COMBINED_M3U, "w", encoding="utf-8") as f:
        f.write(combined_content)
    print(f"✅ Saved root Combined.m3u: {len(combined_content)} bytes ({total_combined_channels} channels)")

    # Also write playlists/Combined.m3u for backwards compatibility
    playlists_combined = os.path.join(PLAYLISTS_DIR, "Combined.m3u")
    with open(playlists_combined, "w", encoding="utf-8") as f:
        f.write(combined_content)
    print(f"✅ Saved playlists/Combined.m3u")

    print("\n" + "=" * 60)
    print(f"🎉 MASTER PLAYLIST GENERATED: {total_combined_channels} CHANNELS!")
    print("=" * 60)

if __name__ == "__main__":
    main()
