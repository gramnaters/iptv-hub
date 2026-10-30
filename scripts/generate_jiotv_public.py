#!/usr/bin/env python3
"""
JioTV playlist built directly from the premiumplugx shoebpl.php feed.

Each record already carries everything: name/group/logo, mpd_url, the per-channel
__hdnea__ cookie, and the ClearKey. No third-party cookie host (allinonereborn),
no Geoplus catalog, no sports feed — one source.
"""
import os
import re
import sys
import time

import requests

REF_URL = "https://premiumplugx.com/gibt/shoebpl.php"
DEFAULT_UA = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "playlists", "jiotv.m3u")

KEY_RE = re.compile(r"(?:[0-9a-fA-F]{32}:[0-9a-fA-F]{32})(?:,[0-9a-fA-F]{32}:[0-9a-fA-F]{32})*")


def get_json(url, retries=3):
    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, headers={"Cache-Control": "no-cache"}, timeout=40)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries - 1:
                time.sleep(2)
    raise last


def quote(v):
    return str(v or "").replace('"', "'")


def main():
    data = get_json(REF_URL)
    if not isinstance(data, list) or not data:
        sys.exit("shoebpl feed empty")

    now = time.time()
    lines = ["#EXTM3U"]
    fresh = stale = 0
    dash = hls = 0

    for item in data:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("id") or "").strip()
        mpd = str(item.get("mpd_url") or "").strip()
        cookie = str((item.get("headers") or {}).get("cookie") or "").strip()
        key = str(item.get("clearkey") or "").strip()
        ua = str(item.get("user_agent") or DEFAULT_UA).strip() or DEFAULT_UA
        name = quote(item.get("name") or "JioTV")
        logo = quote(item.get("logo") or "")
        grp = quote(f"JioTV | {item.get('group') or 'Other'}")

        if not cid or not mpd:
            continue

        # url: prefer the explicit cookie header; fall back to any embedded query
        if cookie:
            url = mpd.split("?")[0] + "?" + cookie
        else:
            url = mpd

        exp = re.search(r"exp=(\d+)", cookie or url)
        if exp and int(exp.group(1)) <= now:
            stale += 1
        else:
            fresh += 1

        is_mpd = ".mpd" in url.lower()
        lines.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" group-title="{grp}",{name}')
        if is_mpd:
            dash += 1
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if KEY_RE.fullmatch(key):
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")
        else:
            hls += 1
        lines.append(f"#EXTVLCOPT:http-user-agent={ua}")
        lines.append(url)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{dash + hls} channels ({dash} dash / {hls} hls), {fresh} fresh / {stale} stale -> {OUT}")


if __name__ == "__main__":
    main()
