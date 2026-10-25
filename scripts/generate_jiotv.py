#!/usr/bin/env python3
"""
generate_jiotv.py — 100% Independent JioTV Playlist Generator.
Mints live Akamai token via personal credentials (jio_auth), or syncs from
our own Cloudflare Worker edge (https://jtv.gramnaters.workers.dev/playlist.m3u)
and local catalogs/jiotv_cookie.json.
Generates playlists/jiotv.m3u using self-hosted catalogs/jiotv_catalog.json.
Zero third-party scraper dependencies.
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
CATALOG_FILE = os.path.join(ROOT_DIR, "catalogs", "jiotv_catalog.json")
COOKIE_FILE = os.path.join(ROOT_DIR, "catalogs", "jiotv_cookie.json")

# Our own dedicated Cloudflare Worker edge
WORKER_EDGE_URL = "https://jtv.gramnaters.workers.dev/playlist.m3u"

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
    """Fetch live __hdnea__ wildcard token using official APIs and self-hosted edge."""
    print("🔑 Fetching live JioTV token...")

    # 1. PRIORITY 1: Direct Self-Minting via Personal JioTV Login
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import jio_auth
        creds = None
        if os.environ.get("JIOTV_CREDS"):
            try:
                creds = json.loads(os.environ["JIOTV_CREDS"])
            except Exception:
                pass
        if not creds:
            for cpath in [
                os.path.join(ROOT_DIR, "jiotv_creds.json"),
                os.path.join(ROOT_DIR, "..", "jiotv_creds.json")
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
            print("  ⚠️ Personal JioTV self-mint unavailable, rolling forward...")
    except Exception as e:
        print(f"  ⚠️ Error in personal self-mint check: {e}")

    # 2. PRIORITY 2: Check our own Cloudflare Worker Edge
    try:
        print("  Checking JTV Cloudflare Worker Edge...")
        with requests.get(WORKER_EDGE_URL, headers={"User-Agent": "Mozilla/5.0"}, stream=True, timeout=8) as r:
            if r.status_code == 200:
                for idx, line in enumerate(r.iter_lines()):
                    if idx > 80:
                        break
                    if not line:
                        continue
                    decoded = line.decode("utf-8", errors="ignore")
                    m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=/\*~hmac=[a-f0-9]+)', decoded)
                    if m:
                        cookie = m.group(1)
                        hrs = _expiry_hours(cookie)
                        if hrs > 0.5:
                            print(f"  ✅ Got valid token from JTV Cloudflare Worker Edge ({hrs:.1f}h remaining)")
                            return cookie
    except Exception as e:
        print(f"  ⚠️ Worker edge check warning: {e}")

    # 3. PRIORITY 3: Check local saved cookie file
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookie = data.get("cookie", "")
            hrs = _expiry_hours(cookie)
            if hrs > 0.5:
                print(f"  🔄 Using local active token ({hrs:.1f}h remaining)")
                return cookie
        except Exception:
            pass

    # 4. PRIORITY 4: Check existing local playlist
    if os.path.exists(OUTPUT_M3U):
        try:
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

def load_channels_catalog():
    print("📡 Loading JioTV channel catalog from self-hosted storage...")
    if os.path.exists(CATALOG_FILE):
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  ✅ Loaded {len(data)} channels from {CATALOG_FILE}")
            return data
        except Exception as e:
            print(f"  ❌ Error reading {CATALOG_FILE}: {e}")
    return []

def extract_drm_keys(channel):
    key_id = channel.get("key_id") or channel.get("kid") or ""
    key = channel.get("key") or ""
    if not key_id and not key:
        lic = channel.get("license_key") or ""
        if ":" in lic:
            parts = lic.split(":", 1)
            key_id = parts[0].strip()
            key = parts[1].strip()
    return key_id, key

def generate_jiotv_playlist():
    channels = load_channels_catalog()
    if not channels:
        print("❌ No channels loaded. Aborting.")
        return False

    cookie = fetch_live_cookie()
    if not cookie:
        print("❌ No valid __hdnea__ token found. Aborting.")
        return False

    now_ist = get_ist_time()
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: jiotv",
        f"# Total Channels: {len(channels)}",
        f"# Cookie: {cookie}",
        ""
    ]

    for ch in channels:
        cid = str(ch.get("id") or ch.get("tvg-id") or "")
        name = ch.get("name") or ch.get("channel-name") or "JioTV Channel"
        cat = ch.get("group") or ch.get("group-title") or ch.get("category") or "General"
        logo = ch.get("logo") or ch.get("tvg-logo") or ""
        url = ch.get("url") or ch.get("mpd_url") or ""
        key_id, key = extract_drm_keys(ch)

        base_url = url.split("?")[0] if "?" in url else url

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="JioTV - {cat}",${name}'
        )

        is_dash = ".mpd" in base_url.lower()
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key_id and key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key_id}:{key}")

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
        lines.append(f"{base_url}?{cookie}")
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    # Save to cookie cache
    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
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
