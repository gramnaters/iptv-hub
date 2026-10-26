#!/usr/bin/env python3
"""
VZY Live TV Playlist Generator.
Fetches fresh ClearKey DRM keys dynamically from https://vzyweb.42web.io/api.php
by solving the AES-128-CBC challenge, updates catalogs/vzy_catalog.json, and writes
playlists/vzy.m3u with W3C ClearKeys (org.w3.clearkey).
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
    from Crypto.Cipher import AES
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "vzy_catalog.json")
STATUS = os.path.join(ROOT, "catalogs", "vzy_status.json")
OUT = os.path.join(ROOT, "playlists", "vzy.m3u")

BASE_URL = "https://vzyweb.42web.io"
API_URL = f"{BASE_URL}/api.php"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
GROUP_LOGO = (
    "https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/"
    "entry_id/bab798478e714be3a5ae861fc04606f0/version/0"
)


def solve_challenge():
    """Solve the AES-128-CBC JS challenge on vzyweb to obtain valid session cookie."""
    if not HAS_DEPS:
        return None
    session = requests.Session()
    session.headers["User-Agent"] = UA
    try:
        resp = session.get(API_URL, timeout=15)
        nums = re.findall(r'toNumbers\("([0-9a-fA-F]+)"\)', resp.text)
        if len(nums) < 3:
            return None
        key, iv, ct = (bytes.fromhex(x) for x in nums[:3])
        cookie_val = AES.new(key, AES.MODE_CBC, iv).decrypt(ct).hex()
        session.headers["Cookie"] = f"__test={cookie_val}"
        api_resp = session.get(f"{API_URL}?i=1", timeout=15)
        if api_resp.status_code == 200:
            data = api_resp.json()
            if isinstance(data, list) and len(data) >= 10:
                return data
    except Exception as e:
        print(f"VZY live fetch warning: {e}")
    return None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    channels = []
    source = "cached"

    # 1. Attempt dynamic live fetch
    live_data = solve_challenge()
    if live_data:
        source = "live (https://vzyweb.42web.io/api.php)"
        channels = []
        for i, item in enumerate(live_data):
            name = item.get("name") or "VZY Channel"
            grp = item.get("group") or "Entertainment"
            logo = item.get("logo") or GROUP_LOGO
            url = item.get("url") or ""
            kid = item.get("kid") or ""
            key = item.get("key") or ""
            cid = item.get("id") or slug(name) or str(i + 1)
            full_key = f"{kid}:{key}" if kid and key else ""

            channels.append({
                "id": str(cid),
                "name": name,
                "group": grp,
                "logo": logo,
                "url": url,
                "key": full_key,
            })

        # Persist updated catalog
        os.makedirs(os.path.dirname(CATALOG), exist_ok=True)
        with open(CATALOG, "w", encoding="utf-8") as f:
            json.dump(channels, f, indent=2, ensure_ascii=False)
        print(f"VZY: Fetched {len(channels)} channels from live API and refreshed catalog.")
    else:
        # Fallback to existing catalog
        if os.path.exists(CATALOG):
            with open(CATALOG, "r", encoding="utf-8") as f:
                channels = json.load(f)
            print(f"VZY: Using cached catalog ({len(channels)} channels).")
        else:
            print(f"VZY Error: Missing catalog {CATALOG} and live fetch failed.")
            return 1

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(channels)}",
        f"# Source: {source}",
        "",
    ]

    dash_count = 0
    for ch in channels:
        cid = str(ch.get("id") or "")
        name = ch.get("name") or "VZY Channel"
        grp = ch.get("group") or "VZY"
        logo = ch.get("logo") or GROUP_LOGO
        url = ch.get("url") or ""
        key = ch.get("key") or ""

        is_dash = ".mpd" in url.lower()
        type_attr = ' type="dash"' if is_dash else ""

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{grp}" group-title="VZY" group-logo="{GROUP_LOGO}"{type_attr},{name}'
        )

        if is_dash and key:
            dash_count += 1
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")

        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": stamp,
            "total": len(channels),
            "dash": dash_count,
            "hls": len(channels) - dash_count,
            "source": source
        }, f, indent=2)

    print(f"VZY: Wrote {OUT} ({len(channels)} channels, {dash_count} DASH ClearKey, {len(channels)-dash_count} HLS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
