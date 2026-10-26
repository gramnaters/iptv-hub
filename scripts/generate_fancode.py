#!/usr/bin/env python3
"""
Self-hosted multi-source FanCode playlist generator.
Extracts live matches across multiple community sources with automatic de-duplication,
proxy resolution, and player-compatible headers.
"""
import os
import sys
import re
import json
import requests
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

DEFAULT_UA = "ReactNativeVideo/9.11.1 (Linux;Android 13) AndroidXMedia3/1.6.1"
REFERER = "https://fancode.com/"
GROUP_TITLE = "FanCode"
GROUP_LOGO = "https://www.google.com/s2/favicons?domain=fancode.com&sz=128"
PROXY_DOMAIN = "https://dai-fancode.pages.dev"

SOURCES = [
    {
        "name": "sportlive18_fancode2",
        "url": "https://raw.githubusercontent.com/sportlive18/Fancode-New-Auto-Update/main/fancode2.m3u",
        "type": "m3u"
    },
    {
        "name": "sportlive18_fancode3",
        "url": "https://raw.githubusercontent.com/sportlive18/Fancode-New-Auto-Update/main/fancode3.m3u",
        "type": "m3u"
    },
    {
        "name": "bytecapsule_json",
        "url": "https://raw.githubusercontent.com/byte-capsule/FanCode-Hls-Fetcher/main/Fancode_hls_m3u8.Json",
        "type": "bytecapsule_json"
    },
    {
        "name": "zyphx8_fancode",
        "url": "https://raw.githubusercontent.com/doctor-8trange/zyphx8/refs/heads/main/data/fancode.m3u",
        "type": "m3u"
    },
    {
        "name": "zyphx8_np",
        "url": "https://raw.githubusercontent.com/doctor-8trange/zyphx8/refs/heads/main/data/np.m3u",
        "type": "m3u"
    },
    {
        "name": "kajju027_m3u",
        "url": "https://raw.githubusercontent.com/kajju027/Fancode-Events-Json/main/fc.m3u",
        "type": "m3u"
    }
]


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
    return base.strip(), headers


def resolve_stream_url(raw_url):
    """Ensure resilient playback URL with fallback for FanCode CDN links."""
    clean_url, headers = split_inline_headers(raw_url)
    clean_url = clean_url.strip()

    # If already a dai-fancode proxy or Google DAI link, use as-is
    if "dai-fancode.pages.dev" in clean_url or "dai.google.com" in clean_url:
        return clean_url, headers

    # If it is an in-mc-flive or in-mc-plive FanCode CDN URL, create the resilient proxy variant
    m = re.search(r'fancode\.com(/mumbai/[^?]+)', clean_url)
    if m:
        path = m.group(1)
        idx_path = re.sub(r'/\d+p\.m3u8$', '/index.m3u8', path)
        if not idx_path.endswith('.m3u8'):
            idx_path = idx_path.rstrip('/') + '/index.m3u8'
        return f"{PROXY_DOMAIN}{idx_path}", headers

    return clean_url, headers


def parse_m3u_text(text):
    """Parse M3U into list of event dicts."""
    events = []
    cur_id, cur_name, cur_logo, cur_lang = "", "", "", "English"
    cur_headers = {}

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m_id = re.search(r'tvg-id="([^"]+)"', line)
            m_name = re.search(r'tvg-name="([^"]+)"', line)
            m_logo = re.search(r'tvg-logo="([^"]+)"', line)
            m_lang = re.search(r'tvg-language="([^"]+)"', line)
            
            cur_id = m_id.group(1) if m_id else ""
            cur_name = m_name.group(1) if m_name else line.split(",")[-1].strip()
            cur_logo = m_logo.group(1) if m_logo else ""
            cur_lang = m_lang.group(1) if m_lang else "English"
            cur_headers = {}
        elif line.startswith("#EXTVLCOPT:http-user-agent="):
            cur_headers["User-Agent"] = line.split("=", 1)[1].strip()
        elif line.startswith(("#EXTVLCOPT:http-referrer=", "#EXTVLCOPT:http-referer=")):
            cur_headers["Referer"] = line.split("=", 1)[1].strip()
        elif line.startswith("http"):
            resolved_url, inline_hdrs = resolve_stream_url(line)
            merged_hdrs = dict(inline_hdrs)
            merged_hdrs.update(cur_headers)
            
            events.append({
                "id": cur_id,
                "name": cur_name,
                "logo": cur_logo,
                "language": cur_lang,
                "url": resolved_url,
                "headers": merged_hdrs
            })
            cur_id, cur_name, cur_logo, cur_lang = "", "", "", "English"
            cur_headers = {}

    return events


def parse_bytecapsule_json(data):
    """Parse Byte Capsule JSON structure."""
    events = []
    for m in data.get("matches", []):
        mid = str(m.get("match_id", "")).strip()
        name = m.get("match_name", "").strip() or m.get("event_name", "FanCode Event")
        stream_link = m.get("stream_link", "").strip()
        if not stream_link:
            continue
        logo = m.get("banner") or m.get("team_1_flag") or GROUP_LOGO
        events.append({
            "id": mid,
            "name": name,
            "logo": logo,
            "language": "English",
            "url": stream_link,
            "headers": {}
        })
    return events


def fetch_all_fancode_events():
    """Fetch and aggregate live matches across all sources with de-duplication."""
    all_events = []
    seen_keys = set()

    for s in SOURCES:
        name = s["name"]
        url = s["url"]
        stype = s["type"]
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
            if r.status_code != 200 or not r.text.strip():
                continue
            
            if stype == "m3u":
                parsed = parse_m3u_text(r.text)
            elif stype == "bytecapsule_json":
                parsed = parse_bytecapsule_json(r.json())
            else:
                parsed = []

            for ev in parsed:
                # Key for de-duplication: clean match ID or normalized name
                mid = ev.get("id") or ""
                mname = re.sub(r'[^a-zA-Z0-9]', '', ev.get("name", "").lower())
                dedup_key = f"id_{mid}" if mid and mid.isdigit() else f"name_{mname}"

                if dedup_key not in seen_keys and ev.get("url"):
                    seen_keys.add(dedup_key)
                    all_events.append(ev)
        except Exception as e:
            print(f"  ⚠️ FanCode source {name} fetch error: {e}")

    return all_events


def generate_fancode_playlist():
    print("📡 Fetching FanCode live sports events across multi-source aggregator...")
    events = fetch_all_fancode_events()

    if not events:
        print("  ⚠️ No active FanCode events discovered across sources.")
        # If output file exists, leave it intact to prevent blanking
        if os.path.exists(OUTPUT_M3U) and os.path.getsize(OUTPUT_M3U) > 100:
            print("  Keeping existing fancode.m3u")
            return True
        return False

    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: fancode",
        f"# Total Channels: {len(events)}",
        "# Source: Multi-source FanCode Aggregator (Self-Hosted)",
        ""
    ]

    for ev in events:
        tid = ev.get("id") or re.sub(r'[^A-Za-z0-9]+', '_', ev["name"])[:40]
        name = ev["name"]
        logo = ev["logo"] or GROUP_LOGO
        lang = ev.get("language", "English")
        url = ev["url"]

        extinf = (
            f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-language="{lang}" group-title="{GROUP_TITLE}" group-logo="{GROUP_LOGO}",{name}'
        )
        lines.append(extinf)
        lines.append(f"#EXTVLCOPT:http-user-agent={DEFAULT_UA}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(url)
        lines.append("")

    content = "\n".join(lines).strip() + "\n"
    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated {OUTPUT_M3U} ({len(events)} active FanCode live events)")
    for ev in events[:3]:
        print(f"   - {ev['name']} -> {ev['url'][:80]}")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate_fancode_playlist() else 1)
