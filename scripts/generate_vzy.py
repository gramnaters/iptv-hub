#!/usr/bin/env python3
import os
import re
import sys
import json
from datetime import datetime, timezone, timedelta

import requests
from Crypto.Cipher import AES

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_FILE = os.path.join(ROOT_DIR, "catalogs", "vzy_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "vzy.m3u")

GROUP_LOGO = "https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/entry_id/bab798478e714be3a5ae861fc04606f0/version/0"

# Live VZY key source: a PHP endpoint that serves the fresh ClearKey `kid:key`
# for every DASH channel behind a slowAES AES-128-CBC JS challenge.
KEY_API = "https://vzyweb.42web.io/api.php"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def solve_challenge(session):
    """Solve the AES-128-CBC JS challenge and return the __test cookie value."""
    r = session.get(KEY_API, timeout=25)
    nums = re.findall(r'toNumbers\("([0-9a-fA-F]+)"\)', r.text)
    if len(nums) < 3:
        raise RuntimeError("could not parse AES challenge")
    key, iv, ct = (bytes.fromhex(x) for x in nums[:3])
    return AES.new(key, AES.MODE_CBC, iv).decrypt(ct).hex()


def fetch_live_keys():
    """Return {url: "kid:key"} for the DASH channels from the live VZY source."""
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    s.headers["Cookie"] = "__test=" + solve_challenge(s)
    r = s.get(KEY_API + "?i=1", timeout=25)
    r.raise_for_status()
    out = {}
    for ch in r.json():
        if ch.get("type") == "dash" and ch.get("key") and ch.get("kid"):
            out[ch["url"]] = f'{ch["kid"]}:{ch["key"]}'
    return out


def generate_vzy_playlist():
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    source = "catalogs/vzy_catalog.json (cached)"
    try:
        live = fetch_live_keys()
        if len(live) < 5:
            print(f"⚠️ Live source returned only {len(live)} keys; keeping cached catalog")
        else:
            source = f"{KEY_API} (live)"
            updated = 0
            for ch in channels:
                if ".mpd" in ch.get("url", ""):
                    new_key = live.get(ch["url"])
                    if new_key and ch.get("key") != new_key:
                        ch["key"] = new_key
                        updated += 1
            print(f"🔑 Refreshed {updated} DASH keys from live source")
            with open(CATALOG_FILE, "w", encoding="utf-8") as f:
                json.dump(channels, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Live key fetch failed ({e}); using cached catalog keys")

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: vzy",
        f"# Total Channels: {len(channels)}",
        f"# Source: {source}",
        "",
    ]

    for ch in channels:
        cid = ch.get("id", "")
        name = ch.get("name", "")
        logo = ch.get("logo", "")
        genre = ch.get("group", "VZY")
        key = ch.get("key")
        url = ch.get("url", "")

        is_dash = ".mpd" in url.lower()
        type_tag = ' type="dash"' if is_dash else ''

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{genre}" group-title="VZY" group-logo="{GROUP_LOGO}"{type_tag},{name}'
        )

        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")

        lines.append(url)
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    dash = sum(1 for c in channels if ".mpd" in c.get("url", ""))
    print(f"✅ Generated {OUTPUT_M3U} ({len(channels)} VZY channels)")
    print(f"   DASH+ClearKey {dash} | FTA HLS {len(channels) - dash}")


if __name__ == "__main__":
    generate_vzy_playlist()
