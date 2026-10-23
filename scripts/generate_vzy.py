#!/usr/bin/env python3
import os
import re
import sys
import json
import requests
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    from Crypto.Cipher import AES
    HAS_AES = True
except ImportError:
    HAS_AES = False

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "vzy.m3u")

BASE = "https://vzyweb.42web.io"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
GROUP_LOGO = "https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/entry_id/bab798478e714be3a5ae861fc04606f0/version/0"

MIN_CHANNELS = 10


def solve_cookie():
    if not HAS_AES:
        return None
    r = requests.get(f"{BASE}/?i=1", headers={"User-Agent": USER_AGENT}, timeout=20)
    h = re.findall(r'toNumbers\("([0-9a-f]+)"\)', r.text)
    if len(h) < 3:
        return None
    a, b, c = h[0], h[1], h[2]
    pt = AES.new(bytes.fromhex(a), AES.MODE_CBC, bytes.fromhex(b)).decrypt(bytes.fromhex(c))
    return pt.hex()


def fetch_channels():
    c = solve_cookie()
    if not c:
        raise RuntimeError("could not solve VZY challenge (pycryptodome missing?)")
    r = requests.get(f"{BASE}/api.php", headers={"User-Agent": USER_AGENT, "Cookie": f"__test={c}"}, timeout=30)
    if r.status_code != 200 or not r.text.lstrip().startswith("["):
        raise RuntimeError(f"VZY api.php unavailable: HTTP {r.status_code}")
    return r.json()


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def generate_vzy_playlist():
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    try:
        channels = fetch_channels()
    except Exception as e:
        print(f"❌ VZY fetch failed: {e} — keeping existing playlist")
        return False
    if len(channels) < MIN_CHANNELS:
        print(f"❌ VZY returned only {len(channels)} channels — keeping existing playlist")
        return False

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: vzy",
        f"# Total Channels: {len(channels)}",
        "",
    ]

    for i, ch in enumerate(channels):
        name = ch.get("name", "")
        logo = ch.get("logo", "")
        group = ch.get("group", "VZY")
        url = ch.get("url", "")
        kid = ch.get("kid", "")
        key = ch.get("key", "")
        if not url:
            continue
        is_dash = ".mpd" in url.lower()
        type_tag = ' type="dash"' if is_dash else ''
        cid = ch.get("id") or slug(name) or str(i)

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{group}" group-title="VZY" group-logo="{GROUP_LOGO}"{type_tag},{name}'
        )
        if is_dash and kid and key:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={kid}:{key}")
        lines.append(url)
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    dash = sum(1 for c in channels if ".mpd" in c.get("url", "").lower())
    print(f"✅ Generated {OUTPUT_M3U} ({len(channels)} VZY channels, {dash} DASH)")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate_vzy_playlist() else 1)
