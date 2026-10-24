#!/usr/bin/env python3
import os
import sys
import json
import re
import urllib.request
import ssl
from datetime import datetime, timezone, timedelta

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

# Upstream playlist mirrors that publish auto-refreshed VZY ClearKeys
KEY_UPSTREAM_URLS = [
    "https://premiumplugx.me/vzy/playlist.php",
    "https://premiumplugx.com/vzy/playlist.php"
]


def fetch_live_vzy_keys():
    """Fetch live rotated ClearKeys from upstream CDM key source."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*"
    }

    for url in KEY_UPSTREAM_URLS:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
                if r.status == 200:
                    text = r.read().decode("utf-8", errors="ignore")
                    extracted = {}
                    entries = text.split("#EXTINF:-1 ")
                    for entry in entries[1:]:
                        lines = entry.strip().splitlines()
                        cid_m = re.search(r'tvg-id="([^"]+)"', lines[0])
                        key_m = re.search(r'license_key=([0-9a-fA-F:]+)', entry)
                        if cid_m and key_m:
                            extracted[cid_m.group(1)] = key_m.group(1).strip()
                    if extracted:
                        print(f"✅ Fetched {len(extracted)} live ClearKeys from {url}")
                        return extracted
        except Exception as e:
            print(f"⚠️ Failed to fetch keys from {url}: {e}")

    return {}


def generate_vzy_playlist():
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    if not os.path.exists(CATALOG_FILE):
        print(f"❌ Catalog file {CATALOG_FILE} not found!")
        return

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        channels = json.load(f)

    # 1. Fetch live updated keys
    live_keys = fetch_live_vzy_keys()

    # 2. Update catalog with fresh keys if found
    updated_count = 0
    if live_keys:
        for ch in channels:
            cid = str(ch.get("id", ""))
            if cid in live_keys:
                new_key = live_keys[cid]
                if ch.get("key") != new_key:
                    ch["key"] = new_key
                    updated_count += 1

        if updated_count > 0:
            with open(CATALOG_FILE, "w", encoding="utf-8") as f:
                json.dump(channels, f, indent=2, ensure_ascii=False)
            print(f"🔄 Updated {updated_count} rotated ClearKeys in {CATALOG_FILE}")

    # 3. Generate M3U playlist
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: VZY Live",
        f"# Total Channels: {len(channels)}",
        "# Source: CloudFront Kaltura CDN with auto-synced ClearKeys",
        ""
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

    dash = sum(1 for c in channels if c.get("url", "").lower().endswith(".mpd"))
    print(f"✅ Generated {OUTPUT_M3U} ({len(channels)} VZY channels)")
    print(f"   DASH+ClearKey {dash} | FTA HLS {len(channels) - dash}")


if __name__ == "__main__":
    generate_vzy_playlist()
