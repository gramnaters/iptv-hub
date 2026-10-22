#!/usr/bin/env python3
import os
import sys
import time
import json
import requests
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG_FILE = os.path.join(ROOT_DIR, "catalogs", "sonyliv_catalog.json")
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sonyliv.m3u")

CDN = "https://dishmt.slivcdn.com/hls/live"
WORKER = os.environ.get("SONYLIV_WORKER", "https://sonyliv-worker.gramnaters.workers.dev")

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
GROUP = "Sony LIV"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png"

MIN_CHANNELS = 5


def fetch_token():
    r = requests.get(f"{WORKER}/token.json", headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    data = r.json()
    token = data.get("token") or ""
    exp = data.get("exp") or 0
    if not token.startswith("hdnea="):
        return ""
    if exp and exp - time.time() < 600:
        return ""
    return token


def probe(url, timeout=15):
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        return r.status_code == 200 and r.text.lstrip().startswith("#EXTM3U")
    except Exception:
        return False


def generate_sony_playlist(verify=True):
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    with open(CATALOG_FILE, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    try:
        token = fetch_token()
    except Exception as e:
        print(f"❌ Token fetch failed: {e} — keeping existing playlist")
        return False
    if not token:
        print("❌ No valid token — keeping existing playlist")
        return False

    channels = [
        {**ch, "url": f"{CDN}/{ch['path']}/master.m3u8?{token}"}
        for ch in catalog
    ]

    if verify:
        ok = sum(1 for ch in channels if probe(ch["url"]))
        if ok < MIN_CHANNELS:
            print(f"⚠️ Only {ok}/{len(channels)} verified here (datacenter IP may be refused); publishing full catalog")

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: sonyliv",
        f"# Total Channels: {len(channels)}",
        "",
    ]

    for ch in channels:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch["id"]}" tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}" '
            f'tvg-category="{ch["group"]}" tvg-language="{ch["language"]}" '
            f'group-title="{GROUP}" group-logo="{GROUP_LOGO}",{ch["name"]}'
        )
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(ch["url"])
        lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ Generated {OUTPUT_M3U} ({len(channels)} SonyLIV channels)")
    return True


if __name__ == "__main__":
    verify = "--no-verify" not in sys.argv
    sys.exit(0 if generate_sony_playlist(verify=verify) else 1)
