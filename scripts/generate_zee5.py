#!/usr/bin/env python3
"""
ZEE5 playlist generator.
"""
import json
import os
import re
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "zee5_catalog.json")
STATUS = os.path.join(ROOT, "catalogs", "zee5_status.json")
OUT = os.path.join(ROOT, "playlists", "zee5.m3u")

API = "https://spapi.zee5.com/singlePlayback/getDetails/secure"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")

# Web platform token
PLATFORM_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJwbGF0Zm9ybV9jb2RlIjoiV2ViQCQhdDM4NzEyIiwiaXNzdWVkQXQiOiIyMDI1LTEwLTIyVDAzOjQ4OjA1LjAyOVoiLCJwcm9kdWN0X2NvZGUiOiJ6ZWU1QDk3NSIsInR0bCI6ODY0MDAwMDAsImlhdCI6MTc2MTEwNDg4NX0."
    "8HnOYX7GmvGGWWiPfYPlvJk55Bzmjd1qEQIx6ueOnCs"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Origin": "https://www.zee5.com",
    "Referer": "https://www.zee5.com/",
}


def _platform_token():
    """Return a platform token, refreshing it from the site when possible."""
    try:
        r = requests.get(
            "https://www.zee5.com/live-tv",
            headers={"User-Agent": UA, "Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"},
            timeout=15,
        )
        if r.status_code == 200:
            m = re.search(r'"gwapiPlatformToken"\s*:\s*"([^"]+)"', r.text)
            if m and m.group(1).count(".") == 2:
                return m.group(1)
    except Exception:
        pass
    return PLATFORM_TOKEN


def details(cid, token):
    guest = str(uuid.uuid4())
    params = {
        "channel_id": cid,
        "device_id": guest,
        "platform_name": "desktop_web",
        "translation": "en",
        "user_language": "en,hi",
        "country": "IN",
        "state": "",
        "app_version": "4.24.0",
        "user_type": "guest",
        "check_parental_control": "false",
    }
    body = {"x-access-token": token, "X-Z5-Guest-Token": guest}
    try:
        r = requests.post(API, params=params, json=body, headers=HEADERS, timeout=25)
        return r.json()
    except Exception:
        return {}


def resolve(ch, token):
    d = details(ch["id"], token)
    if not d:
        return ch, None, "unreachable"

    osd = d.get("keyOsDetails") or {}
    url = osd.get("video_token")
    if url:
        return ch, url, osd.get("drm") or "clear"

    code = str(d.get("error_code") or "")
    if code == "3804":
        return ch, None, "premium"
    if code == "607":
        return ch, None, "geo"
    return ch, None, code or "unknown"


def main():
    if not os.path.exists(CATALOG):
        print(f"missing catalog: {CATALOG}")
        return 1
    with open(CATALOG, encoding="utf-8") as f:
        channels = json.load(f)

    token = _platform_token()
    print(f"ZEE5: {len(channels)} channels, minting playback tokens")

    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for ch, url, state in ex.map(lambda c: resolve(c, token), channels):
            results.append((ch, url, state))

    playable = [(c, u) for c, u, _ in results if u]
    states = {}
    for _, _, s in results:
        states[s] = states.get(s, 0) + 1
    print(f"  playable: {len(playable)}/{len(channels)}  " + ", ".join(f"{k}={v}" for k, v in sorted(states.items())))

    if len(playable) < 10:
        print("  too few channels, keeping previous playlist")
        return 1

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(playable)}",
        "",
    ]
    for ch, url in playable:
        name = ch.get("name", "")
        cid = ch.get("id", "")
        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{ch.get("logo","")}" '
            f'tvg-category="{ch.get("genre","Entertainment")}" group-title="{ch.get("group","ZEE5 India")}" '
            f'group-logo="https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg",{name}'
        )
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": stamp,
            "playable": len(playable),
            "states": states,
            "premium": [c["name"] for c, u, s in results if s == "premium"],
        }, f, indent=2, ensure_ascii=False)

    print(f"  wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
