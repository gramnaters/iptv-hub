#!/usr/bin/env python3
"""
ZEE5 playlist generator.
Generates playlists/zee5.m3u from catalogs/zee5_catalog.json with ClearKeys
for premium entertainment channels and active streams for free/news channels.
"""
import json
import os
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
PLAYER_UA = "plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7"

PLATFORM_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJwbGF0Zm9ybV9jb2RlIjoiV2ViQCQhdDM4NzEyIiwiaXNzdWVkQXQiOiIyMDI1LTEwLTIyVDAzOjQ4OjA1LjAyOVoiLCJwcm9kdWN0X2NvZGUiOiJ6ZWU1QDk3NSIsInR0bCI6ODY0MDAwMDAsImlhdCI6MTc2MTEwNDg4NX0."
    "8HnOYX7GmvGGWWiPfYPlvJk55Bzmjd1qEQIx6ueOnCs"
)


def refresh_free_channel(cid):
    """Fetch live stream token for free ZEE5 channels."""
    guest = str(uuid.uuid4())
    params = {
        "channel_id": cid,
        "device_id": guest,
        "platform_name": "desktop_web",
        "translation": "en",
        "user_language": "en,hi",
        "country": "IN",
        "app_version": "4.24.0",
        "user_type": "guest",
        "check_parental_control": "false",
    }
    body = {"x-access-token": PLATFORM_TOKEN, "X-Z5-Guest-Token": guest}
    try:
        r = requests.post(API, params=params, json=body,
                          headers={"User-Agent": UA, "Content-Type": "application/json",
                                   "Origin": "https://www.zee5.com", "Referer": "https://www.zee5.com/"},
                          timeout=10)
        d = r.json()
        return d.get("keyOsDetails", {}).get("video_token")
    except Exception:
        return None


def resolve_channel(ch):
    cid = str(ch.get("id") or "")
    url = ch.get("url") or ""
    is_dash = ch.get("is_dash", False) or ".mpd" in url.lower()

    if not is_dash and cid.startswith("0-9-"):
        fresh = refresh_free_channel(cid)
        if fresh:
            ch = dict(ch)
            ch["url"] = fresh
    return ch


def main():
    if not os.path.exists(CATALOG):
        print(f"Missing ZEE5 catalog: {CATALOG}")
        return 1

    with open(CATALOG, "r", encoding="utf-8") as f:
        channels = json.load(f)

    # Resolve free channels concurrently
    resolved = []
    with ThreadPoolExecutor(max_workers=10) as ex:
        resolved = list(ex.map(resolve_channel, channels))

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(resolved)}",
        "",
    ]

    for ch in resolved:
        cid = str(ch.get("id") or "")
        name = ch.get("name") or "ZEE5 Channel"
        cat = ch.get("genre") or ch.get("category") or "Entertainment"
        logo = ch.get("logo") or ""
        url = ch.get("url") or ""
        key = ch.get("key") or ""
        is_dash = ch.get("is_dash", False) or ".mpd" in url.lower()

        type_attr = ' type="dash"' if is_dash else ''
        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{cat}" group-title="ZEE5 India" group-logo="https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg"{type_attr},{name}'
        )

        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")
            lines.append(f"#EXTVLCOPT:http-user-agent={PLAYER_UA}")
        else:
            lines.append(f"#EXTVLCOPT:http-user-agent={UA}")

        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({"updated_at": stamp, "playable": len(resolved)}, f, indent=2)

    print(f"ZEE5: generated {OUT} ({len(resolved)} channels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
