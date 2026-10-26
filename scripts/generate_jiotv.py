#!/usr/bin/env python3
"""
JioTV playlist generator.
Produces playlists/jiotv.m3u containing all 1,175 channels with ClearKeys
and active Akamai __hdnea__ playback tokens.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "jiotv_catalog.json")
KEYS_FILE = os.path.join(ROOT, "catalogs", "jiotv_keys.json")
COOKIE_FILE = os.path.join(ROOT, "catalogs", "jiotv_cookie.json")
OUT = os.path.join(ROOT, "playlists", "jiotv.m3u")

WORKER_EDGE_URL = "https://jtv.gramnaters.workers.dev/playlist.m3u"
FALLBACK_TOKEN_URL = "https://plugxvipplaylist.lovable.app/api/playlist"
USER_AGENT = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"
ORIGIN = "https://www.jiotv.com/"
REFERER = "https://www.jiotv.com/"


def get_ist_time():
    return datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")


def expiry_hours(cookie):
    m = re.search(r"~exp=(\d+)~", cookie or "")
    if not m:
        return -1.0
    return (int(m.group(1)) - int(time.time())) / 3600.0


def fetch_live_cookie():
    """Fetch active __hdnea__ wildcard token."""
    # 1. Check self-hosted Cloudflare Worker edge
    try:
        r = requests.get(WORKER_EDGE_URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if r.status_code == 200:
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~"\r\n\s&]+~hmac=[a-f0-9]+)', r.text)
            if m:
                cookie = m.group(1)
                if expiry_hours(cookie) > 0.5:
                    return cookie
    except Exception:
        pass

    # 2. Check local cookie file
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookie = data.get("cookie", "")
            if expiry_hours(cookie) > 0.5:
                return cookie
        except Exception:
            pass

    # 3. Fallback to active stream token
    try:
        r = requests.get(FALLBACK_TOKEN_URL, timeout=12)
        if r.status_code == 200:
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~"\r\n\s&]+~hmac=[a-f0-9]+)', r.text)
            if m:
                cookie = m.group(1)
                if expiry_hours(cookie) > 0.5:
                    return cookie
    except Exception:
        pass

    # 4. Existing local playlist
    if os.path.exists(OUT):
        try:
            with open(OUT, "r", encoding="utf-8") as f:
                content = f.read(5000)
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~"\r\n\s&]+~hmac=[a-f0-9]+)', content)
            if m:
                cookie = m.group(1)
                if expiry_hours(cookie) > 0.5:
                    return cookie
        except Exception:
            pass

    return ""


def load_channels():
    if not os.path.exists(CATALOG):
        return [], {}
    with open(CATALOG, "r", encoding="utf-8") as f:
        channels = json.load(f)

    keys = {}
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                keys = json.load(f)
        except Exception:
            pass

    return channels, keys


def main():
    channels, keys = load_channels()
    if not channels:
        print("Missing JioTV catalog.")
        return 1

    cookie = fetch_live_cookie()
    if not cookie:
        print("Failed to acquire live playback token.")
        return 1

    now_ist = get_ist_time()
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: jiotv",
        f"# Total Channels: {len(channels)}",
        f"# Cookie: {cookie}",
        "",
    ]

    for ch in channels:
        cid = str(ch.get("id") or ch.get("tvg-id") or "")
        name = ch.get("name") or ch.get("channel-name") or "JioTV Channel"
        cat = ch.get("category") or ch.get("group") or ch.get("group-title") or "General"
        logo = ch.get("logo") or ch.get("tvg-logo") or ""
        url = ch.get("url") or ch.get("mpd_url") or ""

        key_id = ch.get("keyId") or ch.get("kid") or ""
        key = ch.get("key") or ""
        if not key_id or not key:
            cached_k = keys.get(cid, "")
            if ":" in cached_k:
                key_id, key = cached_k.split(":", 1)

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

        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(f"#EXTVLCOPT:http-cookie={cookie}")

        hdr = {
            "User-Agent": USER_AGENT,
            "Origin": ORIGIN,
            "Referer": REFERER,
            "Cookie": cookie,
        }
        lines.append(f"#EXTHTTP:{json.dumps(hdr, ensure_ascii=False)}")
        lines.append(f"{base_url}?{cookie}")
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump({"updated_at": now_ist, "cookie": cookie}, f, indent=2)
    except Exception:
        pass

    hrs = expiry_hours(cookie)
    print(f"JioTV: generated {OUT} ({len(channels)} channels, token TTL: {hrs:.1f}h)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
