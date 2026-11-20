#!/usr/bin/env python3
"""
JioHotstar playlist built from the PlugX login API (fresh hdntl tokens).

The historic sources are dead:
  * premiumplugx.com/htt/hot.php            -> 404
  * plugxvipplaylist.lovable.app/api/playlist -> blocked
  * self-mint from Hotstar BFF              -> 403 from datacenter/CI

The PlugX API (same one used by generate_jiotv_public.py) returns 146 JioHotstar
channels each carrying a fresh wildcard `hdntl` cookie (acl=%2f*, ~24h TTL) plus
the exact User-Agent/Referer/Origin the linear CDN requires. We mint from it.

Output format matches the old jiohotstar.m3u exactly: EXTVLCOPT + EXTHTTP header
directives (TiViMate honours these) and the `|cookie=...` URL form.
"""
import json
import os
import re
import sys
import time
import urllib.request

API = "https://plugxaura.app/Plugxlive/api.php"
CREDS = {
    "action": "login",
    "name": os.environ.get("PLUGX_NAME", "PLUGX"),
    "username": os.environ.get("PLUGX_USER", "PLUGX"),
    "password": os.environ.get("PLUGX_PASS", "PLUGX2211"),
    "device_id": os.environ.get("PLUGX_DEVID", "0a0f3889-8839-4845-8cb3-044b44b17889"),
    "device_name": "PlugX-Worker",
    "version_code": 16,
}
UA = "Premium Plugx"
PLAYLIST_ID = 1  # JioHotstar
GROUP = "JioHotstar"
MIN_CHANNELS = 10
EXP_RE = re.compile(r"exp=(\d+)")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "playlists", "jiohotstar.m3u")


def login():
    body = json.dumps(CREDS).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        j = json.load(r)
    if not j.get("ok"):
        raise RuntimeError(f"PlugX login failed: {j.get('error')}")
    return j["data"]


def quote(v):
    return str(v or "").replace('"', "'").replace("\r", " ").replace("\n", " ").strip()


def main():
    data = login()
    now = time.time()
    lines = ["#EXTM3U", f"#DATE:- {time.strftime('%d-%m-%Y %H:%M:%S')}"]
    fresh = stale = 0
    for c in data.get("channels", []):
        if c.get("playlist_id") != PLAYLIST_ID:
            continue
        headers = c.get("headers") or {}
        cookie = str(headers.get("Cookie") or "").strip()
        if not cookie:
            continue
        exp = EXP_RE.search(cookie)
        if exp and int(exp.group(1)) <= now:
            stale += 1
            continue
        fresh += 1
        name = quote(c.get("name") or "JioHotstar")
        logo = quote(c.get("logo") or "")
        # The API URL can carry a malformed "|cookie=...&referer=...&origin=..."
        # suffix; rebuild it as the canonical form the old playlist used.
        base = str(c.get("stream_url") or "").split("|cookie=")[0].rstrip("?&")
        suffix = (f"|cookie={cookie}"
                  f"&referer={headers.get('Referer','https://www.hotstar.com/')}"
                  f"&origin={headers.get('Origin','https://www.hotstar.com')}"
                  f"&user-agent={headers.get('User-Agent', UA)}")
        lines.append(
            f'#EXTINF:-1 tvg-id="{c.get("id") or ""}" tvg-name="{name}" '
            f'tvg-logo="{logo}" group-title="{GROUP}",{name}'
        )
        # DASH channels are ClearKey-protected. Without the #KODIPROP license
        # directives the player sees the tracks but cannot decrypt them ->
        # "None of the video tracks are playable by this device".
        is_dash = ".mpd" in base.lower() or (c.get("manifest_type") or "").lower() in ("mpd", "dash")
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.stream_headers="
                         f"User-Agent={headers.get('User-Agent', UA)}"
                         f"&Referer={headers.get('Referer','https://www.hotstar.com/')}"
                         f"&Origin={headers.get('Origin','https://www.hotstar.com')}"
                         f"&Cookie={cookie}")
            ltype = str(c.get("license_type") or "").strip().lower()
            lkey = str(c.get("license_key") or "").strip()
            if ltype == "clearkey" and lkey:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={lkey}")
        lines.append(f"#EXTVLCOPT:http-user-agent={headers.get('User-Agent', UA)}")
        lines.append(f"#EXTVLCOPT:http-referrer={headers.get('Referer','https://www.hotstar.com/')}")
        lines.append(f"#EXTVLCOPT:http-extra-headers=Origin: {headers.get('Origin','https://www.hotstar.com')}")
        lines.append(f"#EXTVLCOPT:http-cookie={cookie}")
        lines.append("#EXTHTTP:" + json.dumps({
            "Origin": headers.get("Origin", "https://www.hotstar.com"),
            "Referer": headers.get("Referer", "https://www.hotstar.com/"),
            "Cookie": cookie,
        }))
        lines.append(base + suffix)

    count = fresh
    if count < MIN_CHANNELS:
        print(f"JioHotstar: only {count} fresh channels -> refusing to write", file=sys.stderr)
        sys.exit(1)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"JioHotstar: {count} channels ({fresh} fresh / {stale} stale dropped) -> {OUT}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"JioHotstar generation failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
