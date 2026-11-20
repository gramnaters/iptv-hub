#!/usr/bin/env python3
"""
JioTV playlists built directly from the PlugX login API.

The old source (premiumplugx.com/gibt/shoebpl.php) went dead (404), leaving every
token in jiotv.m3u expired. The PlugX API returns a fresh per-channel __hdnea__
token on every login, so we mint from it directly -- no third-party proxy.

Outputs:
  playlists/jiotv.m3u        JIO+ playlist  (jiotvmblive / ...MOB...  = MOBILE)
  playlists/jiotv_mobile.m3u JIOSTB+ playlist (jiotvpllive / ...BTS... = STB)

Despite its misleading filename, jiotv_mobile.m3u is the STB (BTS) feed; that is
kept for backwards compatibility with merge.py / existing setups.
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
UA = "Premium Plugx"  # required: without a UA the API returns 403

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# playlist id -> (output file, group label)
# Only the STB (BTS) feed is published now. The MOBILE feed (playlist 2,
# jiotvmblive/...MOB...) was dropped at the user's request.
OUTPUTS = {
    8: ("jiotv_mobile.m3u", "JioTV STB"),    # JIOSTB+ -> BTS/STB
}

KEY_RE = re.compile(r"(?:[0-9a-fA-F]{32}:[0-9a-fA-F]{32})(?:,[0-9a-fA-F]{32}:[0-9a-fA-F]{32})*")
EXP_RE = re.compile(r"exp=(\d+)")


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


def build(data, playlist_id, group_label):
    cats = {c["id"]: c["name"] for c in data.get("categories", [])}
    now = time.time()
    lines = ["#EXTM3U"]
    fresh = stale = dash = hls = 0
    for item in data.get("channels", []):
        if item.get("playlist_id") != playlist_id:
            continue
        url = str(item.get("stream_url") or "").strip()
        if not url:
            continue

        # Token: prefer the explicit header cookie, fold it into the URL as a
        # query param (the form all our other playlists and TiViMate use).
        headers = item.get("headers") or {}
        cookie = str(headers.get("cookie") or headers.get("Cookie") or "").strip()
        if cookie:
            url = url.split("?")[0] + "?" + cookie.lstrip("?")
        ua = str(headers.get("user-agent") or headers.get("User-Agent") or UA).strip() or UA

        exp = EXP_RE.search(cookie or url)
        if exp and int(exp.group(1)) <= now:
            # Skip rows whose token already expired. The catalog returns duplicate
            # channels where stale rows still carry an old token; dropping them
            # here prevents dead entries from reaching the merged playlist.
            stale += 1
            continue
        if exp:
            fresh += 1

        name = quote(item.get("name") or "JioTV")
        logo = quote(item.get("logo") or "")
        grp = quote(group_label + " | " + (cats.get(item.get("category_id")) or "Other"))
        lines.append(
            f'#EXTINF:-1 tvg-id="{item.get("id") or ""}" tvg-name="{name}" '
            f'tvg-logo="{logo}" group-title="{grp}",{name}'
        )
        if ".mpd" in url.lower():
            dash += 1
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            key = str(item.get("license_key") or "").strip()
            if KEY_RE.fullmatch(key):
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")
        else:
            hls += 1
        lines.append(f"#EXTVLCOPT:http-user-agent={ua}")
        lines.append(url)
    return lines, (dash, hls, fresh, stale)


def main():
    data = login()
    os.makedirs(os.path.join(ROOT, "playlists"), exist_ok=True)
    for pid, (filename, label) in OUTPUTS.items():
        lines, (dash, hls, fresh, stale) = build(data, pid, label)
        out = os.path.join(ROOT, "playlists", filename)
        with open(out, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"{filename}: {len([l for l in lines if l.startswith('#EXTINF')])} channels "
              f"({dash} dash / {hls} hls), {fresh} fresh / {stale} stale")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"JioTV generation failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
