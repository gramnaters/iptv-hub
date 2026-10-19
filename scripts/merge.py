#!/usr/bin/env python3
"""
IPTV Auto-Updater & Master Aggregator
Generates a comprehensive IPTV master playlist. Every category is assembled
from the most independent source available:

  - JioHotstar    -> user's own Cloudflare worker (self-minted, own cookie)
  - VZY           -> channels/vzy_catalog.json   (static ClearKey, NO token/cookie)
  - FanCode       -> doctor-8trange feed         (per-match hdntl token)
  - Jio TV+       -> channels/jiotv_cookie.json  (allinonereborn minted __hdnea__)
  - ZEE5 / SunNXT / SonyLIV / Dangal / Kids / Willow / Prime -> public feed

Locally generated playlists (scripts/generate_*.py -> playlists/*.m3u) take
precedence over the public feed for the categories they cover, so a dead
third-party feed can no longer take a category offline.

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
CATALOGS_DIR = os.path.join(ROOT_DIR, "catalogs")
COMBINED_M3U = os.path.join(ROOT_DIR, "Combined.m3u")
EPG_URL = "https://avkb.short.gy/jioepg.xml.gz"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# User's dedicated independent JioHotstar worker
USER_JIOHOTSTAR_URL = "https://jhs.gramnaters.workers.dev/"

# Upstream public feeds
PUBLIC_PLUG_API = "https://plugxvipplaylist.lovable.app/api/playlist"
LOCAL_PLUG_BACKUP = os.path.join(os.path.dirname(ROOT_DIR), "premiumplug_full.m3u")

# Independent local sources: scripts/generate_*.py -> playlists/*.m3u
# When one of these loads, its group is skipped in the public feed so the
# independent copy wins and there are no duplicates.
LOCAL_OVERRIDES = [
    {
        "name": "VZY",
        "file": os.path.join(PLAYLISTS_DIR, "vzy.m3u"),
        "min_channels": 10,
        "plug_groups": ["VZY"],
        "group": "VZY",
    },
    {
        "name": "FanCode",
        "file": os.path.join(PLAYLISTS_DIR, "fancode.m3u"),
        "min_channels": 1,
        "plug_groups": ["FanCode"],
        "group": "FanCode",
    },
    {
        "name": "SonyLIV (own catalog)",
        "file": os.path.join(PLAYLISTS_DIR, "sonyliv.m3u"),
        "min_channels": 5,
        "plug_groups": ["Sony LIV", "Sonyliv events"],
        "group": None,  # keep the group-title carried by the file itself
    },
    {
        "name": "SunNXT (health-checked catalog)",
        "file": os.path.join(PLAYLISTS_DIR, "sunnxt.m3u"),
        "min_channels": 10,
        "plug_groups": ["Sun NXT", "SunNXT"],
        "group": "SunNXT",
    },
    {
        "name": "JioTV (allinonereborn cookie)",
        "file": os.path.join(PLAYLISTS_DIR, "jiotv.m3u"),
        "min_channels": 100,
        "plug_groups": None,  # None => skip every group starting with "Jio TV+"
        "group": None,
    },
]

JIOTV_GROUP_PREFIX = "Jio TV+"

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

def load_local_playlist(path, min_channels=1):
    """Load blocks from a locally generated playlist (scripts/generate_*.py -> playlists/*.m3u)."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"⚠️ Could not read {path}: {e}")
        return []
    blocks = extract_channel_blocks(text)
    if len(blocks) < min_channels:
        print(f"⚠️ {os.path.basename(path)} has only {len(blocks)} channels (needs >= {min_channels}), ignoring")
        return []
    return [clean_watermarks_from_block(b) for b in blocks]


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
    # 2. Independent local sources (channels/*.json -> playlists/*.m3u)
    # -------------------------------------------------------------
    skip_from_plug = {"jiohotstar"}   # exact group names to take from local instead
    # ZEE5 India is dropped on purpose: its streams hang (measured 31/33 dead),
    # while ZEE5 Worldwide plays. Keep only the working half off the public feed.
    skip_from_plug.add("zee5 india")
    skip_jiotv_from_plug = False      # "Jio TV+ *" groups

    print("\n🔒 Loading independent local sources...")
    for src in LOCAL_OVERRIDES:
        blocks = load_local_playlist(src["file"], src["min_channels"])
        if not blocks:
            print(f"⚠️ {src['name']}: local playlist unavailable -> falling back to public feed")
            continue
        if src["group"]:
            all_channels_by_group.setdefault(src["group"], []).extend(blocks)
        else:
            # e.g. JioTV: keep each "JioTV - <category>" group intact
            for b in blocks:
                all_channels_by_group.setdefault(get_block_group(b), []).append(b)
        if src["plug_groups"] is None:
            skip_jiotv_from_plug = True
        else:
            for g in src["plug_groups"]:
                skip_from_plug.add(g.lower())
        print(f"✅ {src['name']}: {len(blocks)} channels loaded from {os.path.basename(src['file'])}")

    # -------------------------------------------------------------
    # 3. Fetch Public Feeds (ZEE5, SunNXT, Dangal, Kids, SonyLIV, ...)
    # -------------------------------------------------------------
    print(f"\n📡 Fetching comprehensive catalog from {PUBLIC_PLUG_API}...")
    plug_text = fetch_content(PUBLIC_PLUG_API)
    if not plug_text and os.path.exists(LOCAL_PLUG_BACKUP):
        print("⚠️ Live API timed out, loading from local backup cache...")
        with open(LOCAL_PLUG_BACKUP, "r", encoding="utf-8") as f:
            plug_text = f.read()

    plug_blocks = extract_channel_blocks(plug_text) if plug_text else []
    print(f"✅ Loaded {len(plug_blocks)} total public channel items")

    # Accumulate public-feed channels, skipping any category we already have
    # from an independent local source (no duplicates).
    skipped_groups = set()
    for b in plug_blocks:
        grp = get_block_group(b)
        gl = grp.lower()
        if gl in skip_from_plug:
            skipped_groups.add(grp)
            continue
        if skip_jiotv_from_plug and grp.startswith(JIOTV_GROUP_PREFIX):
            skipped_groups.add(grp)
            continue
        cleaned_b = clean_watermarks_from_block(b)
        all_channels_by_group.setdefault(grp, []).append(cleaned_b)
    if skipped_groups:
        print(f"⏭️  Skipped {len(skipped_groups)} public-feed group(s) (local copy wins or category disabled): {', '.join(sorted(skipped_groups))}")

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
    # Mapping for clean individual playlists.
    # NOTE: vzy / fancode / jiotv are deliberately absent - those files are
    # produced by their own independent generators (scripts/generate_*.py)
    # and must not be overwritten here.
    individual_categories = {
        "jiohotstar": ["JioHotstar"],
        "willow": ["Willow"],
        "prime": ["Prime Video"],
        "sunnxt": ["SunNXT"],
        "zee5": ["ZEE5 Worldwide"],
        "dangal": ["Dangal Play"],
        "kids": ["24/7 kids+Goldmines pack", "WOW KIDZ"],
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
        "Jio TV+ | Other",
        # Independent JioTV (channels/jiotv_cookie.json -> playlists/jiotv.m3u)
        "JioTV - Sports",
        "JioTV - News",
        "JioTV - English",
        "JioTV - Tamil",
        "JioTV - Telugu",
        "JioTV - Kannada",
        "JioTV - Malayalam",
        "JioTV - Bengali",
        "JioTV - Marathi",
        "JioTV - Gujarati",
        "JioTV - Punjabi",
        "JioTV - Odia",
        "JioTV - Assamese",
        "JioTV - Urdu",
        "JioTV - Bhojpuri",
        "JioTV - Nepali",
        "JioTV - French",
        "JioTV - Entertainment",
        "JioTV - Movies",
        "JioTV - Kids",
        "JioTV - Music",
        "JioTV - Devotional",
        "JioTV - Infotainment",
        "JioTV - Lifestyle",
        "JioTV - Educational",
        "JioTV - Business News",
        "JioTV - Unknown"
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
