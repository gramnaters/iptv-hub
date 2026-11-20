#!/usr/bin/env python3
"""
Generate one standalone M3U per PlugX API playlist (all 17).

Source: the single PlugX login API catalog (POST .../api.php, action=login).
The API has no per-playlist export URL, so we slice its channels by playlist_id
and emit a self-contained M3U for each, preserving:
  - per-channel auth cookies (as query params where possible, headers otherwise)
  - EXTVLCOPT / EXTHTTP header directives
  - ClearKey (#KODIPROP) DRM info for DASH channels

Output: playlists/plugx/<slug>.m3u  (one file per playlist id)
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "playlists", "plugx")
EXP_RE = re.compile(r"exp=(\d+)")


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "playlist"


def login():
    body = json.dumps(CREDS).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Content-Type": "application/json", "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    if not j.get("ok"):
        raise RuntimeError(f"PlugX login failed: {j.get('error')}")
    return j["data"]


def quote(v):
    return str(v or "").replace('"', "'").replace("\r", " ").replace("\n", " ").strip()


def build(data, pid, group):
    cats = {c["id"]: c["name"] for c in data.get("categories", [])}
    now = time.time()
    lines = ["#EXTM3U", f"# PlugX playlist: {group} (id={pid})",
             f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S IST')}"]
    fresh = stale = 0
    for c in data.get("channels", []):
        if c.get("playlist_id") != pid:
            continue
        headers = c.get("headers") or {}
        cookie = str(headers.get("cookie") or headers.get("Cookie") or "").strip()
        url = str(c.get("stream_url") or "").strip()
        if not url:
            continue
        exp = EXP_RE.search(cookie or url)
        if exp and int(exp.group(1)) <= now:
            stale += 1
            continue
        fresh += 1
        # fold cookie into URL as query param if no embedded "|cookie=" form
        if "|cookie=" not in url and cookie and "?" not in url.split("|")[0]:
            url = url.split("|")[0] + "?" + cookie.lstrip("?")
        name = quote(c.get("name") or "Channel")
        logo = quote(c.get("logo") or "")
        grp = group if group else quote(cats.get(c.get("category_id")) or "Other")
        lines.append(
            f'#EXTINF:-1 tvg-id="{c.get("id") or ""}" tvg-name="{name}" '
            f'tvg-logo="{logo}" group-title="{grp}",{name}'
        )
        base = url.split("|cookie=")[0].rstrip("?&")
        is_dash = ".mpd" in base.lower() or (c.get("manifest_type") or "").lower() in ("mpd", "dash")
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            sh = f"User-Agent={headers.get('user-agent', headers.get('User-Agent', UA))}"
            if cookie:
                sh += f"&Cookie={cookie}"
            lines.append(f"#KODIPROP:inputstream.adaptive.stream_headers={sh}")
            ltype = str(c.get("license_type") or "").strip().lower()
            lkey = str(c.get("license_key") or "").strip()
            if ltype == "clearkey" and lkey:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={lkey}")
        ua = str(headers.get("user-agent", headers.get("User-Agent", UA))).strip() or UA
        lines.append(f"#EXTVLCOPT:http-user-agent={ua}")
        if cookie:
            lines.append(f"#EXTVLCOPT:http-cookie={cookie}")
        lines.append(url)
    return lines, fresh, stale


def main():
    data = login()
    os.makedirs(OUTDIR, exist_ok=True)
    for p in data.get("playlists", []):
        pid, name = p["id"], p["name"]
        lines, fresh, stale = build(data, pid, name)
        path = os.path.join(OUTDIR, slug(name) + ".m3u")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        print(f"{pid:>3} {name:26} -> {os.path.basename(path):28} {fresh} ch (dropped {stale} stale)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"generate_plugx_all failed: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
