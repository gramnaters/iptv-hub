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
PLAYLISTS_DIR = os.path.join(ROOT_DIR, "playlists")
COMBINED_M3U = os.path.join(ROOT_DIR, "Combined.m3u")
EPG_URL = "https://avkb.short.gy/jioepg.xml.gz"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

# User's dedicated independent JioHotstar worker
USER_JIOHOTSTAR_URL = "https://jhs.gramnaters.workers.dev/"

PUBLIC_PLUG_API = "https://plugxvipplaylist.lovable.app/api/playlist"
LOCAL_PLUG_BACKUP = os.path.join(os.path.dirname(ROOT_DIR), "premiumplug_full.m3u")

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


LANG_KEYWORDS = {
    "Tamil": ["tamil", "vijay", "ktv", "sun tv", "sun music", "sun life", "sun news", "thirai", "chutti", "polimer", "jaya ", "makkal", "kalaignar", "captain", "thalapathy"],
    "Telugu": ["telugu", " maa", "gemini", "cinemalu", "kushi", "adithya", " etv", "tv5", "ntv ", "sakshi", "vanitha"],
    "Kannada": ["kannada", "udaya", "suvarna", "kasthuri", "public tv"],
    "Malayalam": ["malayalam", "asianet", "surya", "kairali", "flowers", "mazhavil", "keralam", "kochu", "chintu", "manorama", "mathrubhumi", "amrita", "24 news"],
    "Bengali": ["bangla", "bengali", "jalsha", "aath", "sarthak", "sonar", "biskope", "ghanta", "akash"],
    "Marathi": ["marathi", "pravah", "lokmat", "talkies", "taas", "saam", "pudhari", "yuva"],
    "Gujarati": ["gujarati", "kalak", "sandesh", "girnar", "alwan"],
    "Punjabi": ["punjabi", "ptc", "sanjha"],
    "Odia": ["odia", "tarang", "otv", "kalinga", "odisha"],
    "Assamese": ["assam", "assamese", "northeast", "north east", "dy365"],
    "English": ["english", "espn", "cnn", "cnbc", "wion", "national geographic", "nat geo", "fox", "tsn", "great!", "tiny pop", "pop up", "bbc earth"],
    "Bhojpuri": ["bhojpuri", "mahuaa"],
    "International": ["french", "german", "arabic", "aflam", "bioskop", "indonesian", "one "],
}

CATEGORY_MAP = {
    "Entertainment": "Entertainment",
    "Movies": "Movies",
    "Kids": "Kids",
    "News": "News",
    "Sports": "Sports",
    "Music": "Music",
    "Devotional": "Devotional",
    "Knowledge": "Infotainment",
    "Infotainment": "Infotainment",
    "Business": "Business News",
    "Business News": "Business News",
    "Lifestyle": "Lifestyle",
    "Other": "Other",
    "Unknown": "Unknown",
    "SunNXT": "Entertainment",
}

BIG_BOSS_RE = re.compile(r"(?i)bigboss|big boss")

def normalize_name(name):
    return re.sub(r"[^a-z0-9]+", "", name.lower())

def get_block_name(block):
    for line in block:
        if line.startswith("#EXTINF"):
            return line.rsplit(",", 1)[-1].strip()
    return ""

def get_block_category(block):
    for line in block:
        if line.startswith("#EXTINF"):
            m = re.search(r'tvg-category="([^"]*)"', line)
            if m and m.group(1):
                return m.group(1)
    return get_block_group(block)

def detect_language(name):
    n = " " + name.lower() + " "
    if "awaaz" in n:  # CNBC Awaaz is Hindi, not English
        return "Hindi"
    for lang, kws in LANG_KEYWORDS.items():
        for kw in kws:
            if kw in n:
                return lang
    return "Hindi"

def merge_group(name, category):
    if BIG_BOSS_RE.search(name):
        return "Big Boss"
    lang = detect_language(name)
    if lang == "Hindi":
        return "Jio TV+ | " + CATEGORY_MAP.get(category, category or "Other")
    if lang == "International":
        return "Jio TV+ | Other"
    return "Jio TV+ | " + lang

def set_block_group(block, group):
    new = []
    for line in block:
        if line.startswith("#EXTINF"):
            if 'group-title=' in line:
                line = re.sub(r'group-title="[^"]*"', f'group-title="{group}"', line)
            else:
                line = line.replace('#EXTINF:-1 ', f'#EXTINF:-1 group-title="{group}" ')
        new.append(line)
    return new

def classify_into(blocks, out, direct_names):
    for b in blocks:
        name = get_block_name(b)
        grp = merge_group(name, get_block_category(b))
        out.setdefault(grp, []).append(set_block_group(b, grp))
        direct_names.add(normalize_name(name))

def classify_sonyliv(blocks, out):
    for b in blocks:
        name = get_block_name(b)
        cat = CATEGORY_MAP.get(get_block_category(b), "Entertainment")
        grp = f"SonyLIV | {cat}"
        out.setdefault(grp, []).append(set_block_group(b, grp))

def classify_jiohotstar(blocks, out, direct_names):
    for b in blocks:
        name = get_block_name(b)
        if BIG_BOSS_RE.search(name):
            out.setdefault("JioHotstar", []).append(set_block_group(b, "JioHotstar"))
        else:
            grp = merge_group(name, get_block_category(b))
            out.setdefault(grp, []).append(set_block_group(b, grp))
            direct_names.add(normalize_name(name))


def main():
    print("=" * 60)
    print(f"🚀 Master IPTV Auto-Updater starting at {get_current_ist()}")
    print("=" * 60)
    os.makedirs(PLAYLISTS_DIR, exist_ok=True)

    all_channels_by_group = {}
    direct_names = set()
    jiotv_blocks = []

    print(f"\n⭐ Fetching independent JioHotstar from {USER_JIOHOTSTAR_URL}...")
    jhs_text = fetch_content(USER_JIOHOTSTAR_URL)
    jhs_blocks = []
    if jhs_text:
        jhs_blocks = [clean_watermarks_from_block(b) for b in extract_channel_blocks(jhs_text)]
        classify_jiohotstar(jhs_blocks, all_channels_by_group, direct_names)
        print(f"✅ Loaded {len(jhs_blocks)} independent JioHotstar channels")
    else:
        print("⚠️ Could not load independent JioHotstar, check worker status")

    skip_from_plug = {"jiohotstar", "zee5 india"}

    print("\n🔒 Loading independent local sources...")
    for src in LOCAL_OVERRIDES:
        blocks = load_local_playlist(src["file"], src["min_channels"])
        if not blocks:
            print(f"⚠️ {src['name']}: local playlist unavailable -> falling back to public feed")
            continue
        name = src["name"]
        if name.startswith("SonyLIV"):
            classify_sonyliv(blocks, all_channels_by_group)
        elif name.startswith("SunNXT"):
            classify_into(blocks, all_channels_by_group, direct_names)
        elif src["group"]:
            all_channels_by_group.setdefault(src["group"], []).extend(blocks)
        for g in src["plug_groups"]:
            skip_from_plug.add(g.lower())
        print(f"✅ {src['name']}: {len(blocks)} channels loaded from {os.path.basename(src['file'])}")

    print(f"\n📡 Fetching comprehensive catalog from {PUBLIC_PLUG_API}...")
    plug_text = fetch_content(PUBLIC_PLUG_API)
    if not plug_text and os.path.exists(LOCAL_PLUG_BACKUP):
        print("⚠️ Live API timed out, loading from local backup cache...")
        with open(LOCAL_PLUG_BACKUP, "r", encoding="utf-8") as f:
            plug_text = f.read()

    plug_blocks = extract_channel_blocks(plug_text) if plug_text else []
    print(f"✅ Loaded {len(plug_blocks)} total public channel items")

    skipped_groups = set()
    for b in plug_blocks:
        grp = get_block_group(b)
        gl = grp.lower()
        if gl in skip_from_plug:
            skipped_groups.add(grp)
            continue
        cleaned_b = clean_watermarks_from_block(b)
        if grp.startswith(JIOTV_GROUP_PREFIX):
            jiotv_blocks.append(cleaned_b)
        elif grp == "ZEE5 Worldwide":
            classify_into([cleaned_b], all_channels_by_group, direct_names)
        else:
            all_channels_by_group.setdefault(grp, []).append(cleaned_b)
    if skipped_groups:
        print(f"⏭️  Skipped {len(skipped_groups)} public-feed group(s) (local copy wins or category disabled): {', '.join(sorted(skipped_groups))}")

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

    jiotv_kept = 0
    jiotv_dropped = 0
    for b in jiotv_blocks:
        name = get_block_name(b)
        if normalize_name(name) in direct_names:
            jiotv_dropped += 1
            continue
        grp = merge_group(name, get_block_category(b))
        all_channels_by_group.setdefault(grp, []).append(set_block_group(b, grp))
        jiotv_kept += 1
    print(f"\n🔗 JioTV dedup: kept {jiotv_kept}, dropped {jiotv_dropped} (already covered by a direct source)")

    individual_categories = {
        "willow": ["Willow"],
        "prime": ["Prime Video"],
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

    print("\n📦 Generating Master Combined.m3u...")

    PRIORITY_GROUPS = [
        "Jio TV+ | Entertainment",
        "Jio TV+ | Infotainment",
        "Jio TV+ | Movies",
        "Jio TV+ | Lifestyle",
        "Jio TV+ | Kids",
        "Jio TV+ | News",
        "Jio TV+ | Devotional",
        "Jio TV+ | Music",
        "Jio TV+ | Business",
        "Jio TV+ | Business News",
        "Jio TV+ | Sports",
        "Jio TV+ | Education",
        "Jio TV+ | Educational",
        "Jio TV+ | Other",
        "Jio TV+ | Specials",
        "Jio TV+ | Shopping",
        "Jio TV+ | English",
        "Jio TV+ | Tamil",
        "Jio TV+ | Telugu",
        "Jio TV+ | Kannada",
        "Jio TV+ | Malayalam",
        "Jio TV+ | Bengali",
        "Jio TV+ | Marathi",
        "Jio TV+ | Gujarati",
        "Jio TV+ | Punjabi",
        "Jio TV+ | Odia",
        "Jio TV+ | Assamese",
        "Jio TV+ | Urdu",
        "Jio TV+ | Bhojpuri",
        "Jio TV+ | Nepali",
        "Jio TV+ | French",
        "Jio TV+ | Unknown",
        "Jio TV+ | Malyalam",
        "24/7 kids+Goldmines pack",
        "WOW KIDZ",
        "SonyLIV | Entertainment",
        "SonyLIV | Movies",
        "SonyLIV | Kids",
        "SonyLIV | Sports",
        "SonyLIV | Infotainment",
        "JioHotstar",
        "VZY",
        "FanCode",
        "Willow",
        "Prime Video",
        "Sonyliv events",
        "Dangal Play",
    ]

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

    with open(COMBINED_M3U, "w", encoding="utf-8") as f:
        f.write(combined_content)
    print(f"✅ Saved root Combined.m3u: {len(combined_content)} bytes ({total_combined_channels} channels)")

    playlists_combined = os.path.join(PLAYLISTS_DIR, "Combined.m3u")
    with open(playlists_combined, "w", encoding="utf-8") as f:
        f.write(combined_content)
    print(f"✅ Saved playlists/Combined.m3u")

    print("\n" + "=" * 60)
    print(f"🎉 MASTER PLAYLIST GENERATED: {total_combined_channels} CHANNELS!")
    print("=" * 60)

if __name__ == "__main__":
    main()
