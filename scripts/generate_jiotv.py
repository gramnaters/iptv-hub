#!/usr/bin/env python3
"""
generate_jiotv.py — JioTV Playlist Generator.
Fetches active Akamai token, parses channel catalog, and generates playlists/jiotv.m3u.
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
CATALOG_CACHE_FILE = os.path.join(ROOT_DIR, "catalogs", "jiotv_catalog.json")

# Token sources: priority ordered (Direct self-mint, Cloudflare worker edge, and live mirrors)
TOKEN_SOURCES = [
    {
        "name": "JTV Cloudflare Worker Edge",
        "url": "https://jtv.gramnaters.workers.dev/playlist.m3u",
        "type": "streaming_lines",
        "timeout": 8
    },
    {
        "name": "Live Cookie Mirror",
        "url": "https://raw.githubusercontent.com/sportlive18/Sportlink-wtf/refs/heads/main/cookie.json",
        "type": "json_flexible",
        "timeout": 8
    },
    {
        "name": "Live Stream Edge",
        "url": "https://raw.githubusercontent.com/qwerty180506/Geo/refs/heads/main/jiotv_cf.m3u",
        "type": "streaming_lines",
        "timeout": 8
    },
    {
        "name": "Reborn Edge Hub",
        "url": "https://allinonereborn2.online/jstrweb2/cookies.json",
        "type": "json_flexible",
        "timeout": 8
    }
]

# Channel catalog sources
CHANNELS_CATALOG = [
    "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/Geoplus.json",
    "https://jjtvxweb.pages.dev/jstr4web.json"
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
    """Fetch a live __hdnea__ wildcard token with validation."""
    print("🔑 Fetching live JioTV token...")

    # 1. PRIORITY 1: Direct Self-Minting via Personal JioTV Login
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import jio_auth
        creds = None
        # Check environment variable (e.g. GitHub Secrets)
        if os.environ.get("JIOTV_CREDS"):
            try:
                creds = json.loads(os.environ["JIOTV_CREDS"])
            except Exception:
                pass
        # Check local credentials files
        if not creds:
            for cpath in [
                os.path.join(ROOT_DIR, "jiotv_creds.json"),
                r"E:\JioTV\JIOTVServer-main\JIOTVServer-main\tokenData.jiotv"
            ]:
                if os.path.exists(cpath):
                    try:
                        with open(cpath, "r", encoding="utf-8") as f:
                            creds = json.load(f)
                            break
                    except Exception:
                        pass
        if creds and creds.get("authToken"):
            print("  🔑 [Priority 1] Attempting self-mint using personal JioTV account...")
            minted = jio_auth.self_mint_token(creds)
            if minted:
                hrs = _expiry_hours(minted)
                if hrs > 0.5:
                    print(f"  🎉 [Priority 1] Successfully self-minted wildcard token ({hrs:.1f}h remaining)")
                    return minted
            print("  ⚠️ Personal JioTV self-mint unavailable (needs fresh login), rolling forward to fallback pool...")
    except Exception as e:
        print(f"  ⚠️ Error in personal self-mint check: {e}")

    # 2. PRIORITY 2: Multi-Source Fallback Pool
    for src in TOKEN_SOURCES:
        try:
            print(f"  Checking {src['name']}...")
            cookie = ""

            if src["type"] == "streaming_lines":
                # Ultra-fast line-by-line stream read (0.2s without downloading 2.5MB)
                with requests.get(src["url"], headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=src["timeout"]) as r:
                    if r.status_code == 200:
                        for idx, line in enumerate(r.iter_lines()):
                            if idx > 80:  # Token is always in first ~20 lines
                                break
                            if not line:
                                continue
                            decoded = line.decode("utf-8", errors="ignore")
                            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=/\*~hmac=[a-f0-9]+)', decoded)
                            if m:
                                cookie = m.group(1)
                                break

            elif src["type"] == "json_flexible":
                r = requests.get(src["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=src["timeout"])
                if r.status_code == 200:
                    data = r.json()
                    # Handle both list and dict formats
                    items = data if isinstance(data, list) else [data]
                    for it in items:
                        if isinstance(it, dict):
                            c = it.get("cookie", "") or it.get("jioToken", "")
                            if c.startswith("__hdnea__="):
                                cookie = c.strip()
                                break

            if cookie:
                hrs = _expiry_hours(cookie)
                if hrs > 0.5:
                    print(f"  ✅ Got valid token from {src['name']} ({hrs:.1f}h remaining)")
                    return cookie
                else:
                    print(f"  ⚠️ Token from {src['name']} expired or expiring soon ({hrs:.1f}h)")
        except Exception as e:
            print(f"  ⚠️ Error from {src['name']}: {e}")

    # Fallback to existing playlist token if still valid
    if os.path.exists(OUTPUT_M3U):
        try:
            print("  Checking existing local playlist for active token...")
            with open(OUTPUT_M3U, "r", encoding="utf-8") as f:
                content = f.read(5000)
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=/\*~hmac=[a-f0-9]+)', content)
            if m:
                cookie = m.group(1)
                hrs = _expiry_hours(cookie)
                if hrs > 0.5:
                    print(f"  🔄 Retaining current local token ({hrs:.1f}h remaining)")
                    return cookie
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
                print(f"  ✅ Loaded {len(data)} channels from {src.split('/')[-1]}")
                os.makedirs(os.path.dirname(CATALOG_CACHE_FILE), exist_ok=True)
                with open(CATALOG_CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)
                return data
        except Exception as e:
            print(f"  ⚠️ Error loading {src}: {e}")

    # Fallback to cached catalog
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
        print("❌ No valid __hdnea__ token found. Aborting.")
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

        # Base stream URL without old query params
        base_url = url.split("?")[0] if "?" in url else url

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="JioTV - {cat}",{name}'
        )

        is_dash = ".mpd" in base_url.lower()
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key_id and key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}")

        # Kodi & VLC headers
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(f"#EXTVLCOPT:http-cookie={cookie}")

        header_dict = {
            "User-Agent": USER_AGENT,
            "Origin": ORIGIN,
            "Referer": REFERER,
            "Cookie": cookie
        }
        lines.append(f"#EXTHTTP:{json.dumps(header_dict, ensure_ascii=False)}")

        # Inject fresh cookie into stream URL query params as well
        stream_url = f"{base_url}?{cookie}"
        lines.append(stream_url)
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    # Save to jiotv_cookie.json
    cookie_file = os.path.join(ROOT_DIR, "catalogs", "jiotv_cookie.json")
    try:
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump({
                "updated_at": get_ist_time(),
                "source": "https://jtv.gramnaters.workers.dev",
                "cookie": cookie
            }, f, indent=2)
    except Exception:
        pass

    print(f"\n🎉 Successfully generated {OUTPUT_M3U} with {len(channels)} channels.")
    print(f"🔒 Cookie injected: {cookie[:40]}... ({_expiry_hours(cookie):.2f} h left)")
    return True

if __name__ == "__main__":
    sys.exit(0 if generate_jiotv_playlist() else 1)
