#!/usr/bin/env python3
"""
Independent FanCode Live Sports Playlist Generator

Source (single, deliberate):
    https://raw.githubusercontent.com/doctor-8trange/zyphx8/refs/heads/main/data/fancode.m3u

FanCode's catalogue is public, but every stream URL carries a short-lived
`hdntl` token minted from a FanCode app session - the token is NOT derivable
from a cookie or an algorithm. This generator therefore consumes the
doctor-8trange feed (which already carries a freshly minted token) and
normalises it into clean, player-safe entries:

    - strips the Kodi-only  "<url>|User-Agent=..&Referer=.."  suffix
    - re-emits those values as  #EXTVLCOPT:http-user-agent / http-referrer

Writes: playlists/fancode.m3u
"""

import os
import sys
import re
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "fancode.m3u")

SOURCES = [
    "https://raw.githubusercontent.com/doctor-8trange/zyphx8/refs/heads/main/data/fancode.m3u",
]

DEFAULT_UA = "ReactNativeVideo/9.11.1 (Linux;Android 13) AndroidXMedia3/1.6.1"
REFERER = "https://fancode.com/"
GROUP_LOGO = "https://www.google.com/s2/favicons?domain=fancode.com&sz=128"


def fetch_text(url, timeout=20):
    try:
        import requests
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"⚠️ Error fetching {url}: {e}")
        return ""


def split_inline_headers(url):
    """Split '<url>|User-Agent=..&Referer=..' into (clean_url, headers_dict)."""
    if "|" not in url:
        return url, {}
    base, _, query = url.partition("|")
    headers = {}
    for pair in query.split("&"):
        if "=" not in pair:
            continue
        k, v = pair.split("=", 1)
        key = k.strip().lower()
        if key == "user-agent":
            headers["User-Agent"] = v.strip()
        elif key in ("referer", "referrer"):
            headers["Referer"] = v.strip()
        elif key == "cookie":
            headers["Cookie"] = v.strip()
    return base.strip(), headers


def parse_m3u(text):
    """Return a list of dicts: {attrs, name, headers, url}."""
    entries = []
    attrs = None
    name = ""
    headers = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            attrs = line
            name = line.split(",")[-1].strip()
            headers = {}
        elif line.startswith(("#EXTVLCOPT:http-user-agent=",)):
            headers["User-Agent"] = line.split("=", 1)[1].strip()
        elif line.startswith(("#EXTVLCOPT:http-referrer=", "#EXTVLCOPT:http-referer=")):
            headers["Referer"] = line.split("=", 1)[1].strip()
        elif line.startswith("#EXTGRP:"):
            pass
        elif line.startswith("#"):
            continue
        elif line.startswith("http"):
            clean, inline = split_inline_headers(line)
            merged = dict(inline)
            merged.update(headers)  # explicit #EXTVLCOPT wins
            entries.append({"attrs": attrs or "", "name": name, "headers": merged, "url": clean})
            attrs, name, headers = None, "", {}
    return entries


def normalize_attrs(attrs, name):
    """Force group-title="FanCode" and keep tvg-id/name/logo."""
    out = attrs
    if 'group-title=' in out:
        out = re.sub(r'group-title="[^"]*"', 'group-title="FanCode"', out)
    else:
        out = out.replace("#EXTINF:-1 ", '#EXTINF:-1 group-title="FanCode" ')
    if 'group-logo=' not in out:
        out = out.replace(",", f' group-logo="{GROUP_LOGO}",', 1)
    if "tvg-id=" not in out:
        out = out.replace("#EXTINF:-1 ", f'#EXTINF:-1 tvg-id="{re.sub(r"[^A-Za-z0-9]+", "_", name)[:40]}" ', 1)
    return out


def generate_fancode_playlist():
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    text = fetch_text(SOURCES[0])
    entries = parse_m3u(text) if text else []

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: fancode",
        f"# Total Channels: {len(entries)}",
        f"# Source: {SOURCES[0]}",
        ""
    ]

    for e in entries:
        ua = e["headers"].get("User-Agent", DEFAULT_UA)
        ref = e["headers"].get("Referer", REFERER)
        lines.append(normalize_attrs(e["attrs"], e["name"]))
        lines.append(f"#EXTVLCOPT:http-user-agent={ua}")
        lines.append(f"#EXTVLCOPT:http-referrer={ref}")
        lines.append(e["url"])
        lines.append("")

    content = "\n".join(lines)
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"✅ Generated {OUTPUT_M3U} ({len(entries)} FanCode matches)")
    for e in entries[:3]:
        print(f"   - {e['name']} -> {e['url'][:90]}")


if __name__ == "__main__":
    generate_fancode_playlist()
