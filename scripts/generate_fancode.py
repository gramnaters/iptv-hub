#!/usr/bin/env python3
"""
FanCode playlist generator for live sports events.
Natively discovers live matches directly from FanCode, mints/resolves stream URLs,
verifies playback status (HTTP 200), and outputs player-compatible M3U playlists.
"""
import os
import sys
import re
import json
import uuid
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
WEB_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
REFERER = "https://fancode.com/"
GROUP_TITLE = "FanCode"
GROUP_LOGO = "https://www.google.com/s2/favicons?domain=fancode.com&sz=128"
PROXY_DOMAIN = "https://dai-fancode.pages.dev"

# Official FanCode GraphQL query configuration
FC_GRAPHQL = "https://www.fancode.com/graphql"
FC_PERSISTED_HASH = "a1d17ed10aaddaaf4452ce04fc840eee8d44a26ef7762f5deaacd66d8c7560b3"

SUPPLEMENTARY_SOURCES = [
    {
        "name": "sportlive18_fancode2",
        "url": "https://raw.githubusercontent.com/sportlive18/Fancode-New-Auto-Update/main/fancode2.m3u",
        "type": "m3u"
    },
    {
        "name": "zyphx8_fancode",
        "url": "https://raw.githubusercontent.com/doctor-8trange/zyphx8/refs/heads/main/data/fancode.m3u",
        "type": "m3u"
    },
    {
        "name": "kajju027_m3u",
        "url": "https://raw.githubusercontent.com/kajju027/Fancode-Events-Json/main/fc.m3u",
        "type": "m3u"
    }
]


def fetch_native_fancode_matches():
    """Extract live matches directly from FanCode's official web application."""
    matches = {}
    try:
        r = requests.get('https://www.fancode.com/', headers={'User-Agent': WEB_UA}, timeout=10)
        if r.status_code != 200:
            return matches
        idx = r.text.find('__INIT_STATE__ = ')
        if idx == -1:
            return matches
        idx += len('__INIT_STATE__ = ')
        brace = 0
        end_idx = idx
        for i in range(idx, len(r.text)):
            if r.text[i] == '{':
                brace += 1
            elif r.text[i] == '}':
                brace -= 1
                if brace == 0:
                    end_idx = i + 1
                    break
        data = json.loads(r.text[idx:end_idx])
        for k, v in data.items():
            if 'LiveNowSegment' in k and isinstance(v, dict):
                edges = v.get('liveNowSegment', {}).get('edges', [])
                for e in edges:
                    mid = str(e.get('id', ''))
                    if not mid:
                        continue
                    match = e.get('match', {})
                    features = e.get('features', {})
                    tour = e.get('tour', {})
                    title = features.get('title') or match.get('name') or "Live Match"
                    sport = match.get('sport', {}).get('name', 'Sports')
                    logo = features.get('bgImageUrl') or features.get('largeBgImage') or ""
                    matches[mid] = {
                        'id': mid,
                        'name': title,
                        'sport': sport,
                        'tournament': tour.get('name') or tour.get('collectionSlug', ''),
                        'logo': logo
                    }
    except Exception as ex:
        print(f"  ⚠️ FanCode native discovery error: {ex}")
    return matches


def query_fancode_graphql_stream(match_id):
    """Query official FanCode GraphQL FanLiveStreamDweb endpoint for stream URL."""
    headers = {
        'user-agent': WEB_UA,
        'accept': '*/*',
        'appversion': '1.0.0',
        'content-type': 'application/json',
        'fc-device-type': 'desktop',
        'fc-x-country-code': 'IN',
        'referer': REFERER,
        'source': 'fc-web',
        'tp-source': 'fc-web',
        'tp-uid': str(uuid.uuid4())
    }
    params = {
        'extensions': json.dumps({"persistedQuery": {"version": 1, "sha256Hash": FC_PERSISTED_HASH}}),
        'operation': 'query',
        'operationName': 'FanLiveStreamDweb',
        'operationType': 'query',
        'variables': json.dumps({
            "input": {
                "id": int(match_id),
                "drmType": "WIDEVINE",
                "showAdFunded": True,
                "videoProtocols": ["HLS", "DASH"],
                "supportedCodecs": [],
                "currentVideoSource": {
                    "isCasting": False,
                    "cslSessionId": None,
                    "drmProvider": "INTER_TRUST",
                    "ssaiProvider": "DAI",
                    "url": None
                }
            }
        })
    }
    try:
        res = requests.get(FC_GRAPHQL, params=params, headers=headers, timeout=8)
        if res.status_code == 200:
            data = res.json().get('data', {}).get('fanLiveStream', {})
            sources = data.get('liveStreams', {}).get('sources', [])
            if sources and sources[0].get('url'):
                return sources[0]['url']
    except Exception:
        pass
    return None


def verify_stream(url):
    """Verify stream manifest returns HTTP 200 and valid HLS headers."""
    try:
        r = requests.get(url, headers={"User-Agent": DEFAULT_UA, "Referer": REFERER}, timeout=7)
        if r.status_code == 200 and ("#EXTM3U" in r.text or "#EXT-X-" in r.text):
            return True
    except Exception:
        pass
    return False


def parse_supplementary_m3u(text):
    """Parse supplementary M3U lines for stream path fallback."""
    streams = {}
    cur_id, cur_name, cur_logo, cur_sport = "", "", "", "Sports"
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            m_id = re.search(r'tvg-id="([^"]+)"', line)
            m_name = re.search(r'tvg-name="([^"]+)"', line)
            m_logo = re.search(r'tvg-logo="([^"]+)"', line)
            m_group = re.search(r'group-title="([^"]+)"', line)
            cur_id = m_id.group(1) if m_id else ""
            cur_name = m_name.group(1) if m_name else line.split(",")[-1].strip()
            cur_logo = m_logo.group(1) if m_logo else ""
            cur_sport = m_group.group(1) if m_group else "Sports"
        elif line.startswith("http"):
            stream_url = line.split("|")[0].strip()
            mid = cur_id
            if not mid:
                m_match = re.search(r'/mumbai/(\d{7})', stream_url)
                if m_match:
                    mid = m_match.group(1)
            if mid:
                streams[mid] = {
                    "id": mid,
                    "name": cur_name,
                    "logo": cur_logo,
                    "sport": cur_sport,
                    "url": stream_url
                }
            cur_id, cur_name, cur_logo, cur_sport = "", "", "", "Sports"
    return streams


def fetch_all_fancode_events():
    """Aggregate live events with primary native discovery and verified streams."""
    print("📡 Discovering live matches directly from FanCode...")
    native_matches = fetch_native_fancode_matches()
    print(f"  Found {len(native_matches)} active matches on FanCode homepage")

    # Fetch supplementary stream path map if direct GraphQL tokens require routing
    supplementary_map = {}
    for src in SUPPLEMENTARY_SOURCES:
        try:
            r = requests.get(src["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=8)
            if r.status_code == 200:
                parsed = parse_supplementary_m3u(r.text)
                for mid, info in parsed.items():
                    if mid not in supplementary_map:
                        supplementary_map[mid] = info
        except Exception as e:
            print(f"  ⚠️ Supplementary source {src['name']} error: {e}")

    events = []
    seen = set()

    # Process all matches (native first, then any additional supplementary)
    all_match_ids = list(native_matches.keys())
    for mid in supplementary_map.keys():
        if mid not in all_match_ids:
            all_match_ids.append(mid)

    for mid in all_match_ids:
        if mid in seen:
            continue

        meta = native_matches.get(mid) or supplementary_map.get(mid, {})
        name = meta.get("name") or "FanCode Event"
        sport = meta.get("sport") or "Sports"
        logo = meta.get("logo") or GROUP_LOGO

        # Try direct GraphQL stream URL
        stream_url = query_fancode_graphql_stream(mid)

        # Fallback to high-availability DAI stream path
        if not stream_url and mid in supplementary_map:
            stream_url = supplementary_map[mid].get("url")

        if not stream_url:
            continue

        # If it's a FanCode Akamai link without DAI, resolve proxy path
        m = re.search(r'fancode\.com(/mumbai/[^?]+)', stream_url)
        if m:
            path = m.group(1)
            idx_path = re.sub(r'/\d+p\.m3u8$', '/index.m3u8', path)
            if not idx_path.endswith('.m3u8'):
                idx_path = idx_path.rstrip('/') + '/index.m3u8'
            stream_url = f"{PROXY_DOMAIN}{idx_path}"

        # Verify stream playback
        if verify_stream(stream_url):
            seen.add(mid)
            events.append({
                "id": mid,
                "name": name,
                "sport": sport,
                "logo": logo,
                "url": stream_url
            })
            print(f"  ✓ Verified [{mid}] {name} ({sport})")
        else:
            print(f"  ⚠️ Stream verification failed for [{mid}] {name}")

    return events


def generate_fancode_playlist():
    events = fetch_all_fancode_events()

    if not events:
        print("  ⚠️ No active FanCode events discovered.")
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
        "# Source: FanCode Self-Hosted Live Sports Events",
        ""
    ]

    for ev in events:
        tid = f"fancode.{ev['id']}"
        name = ev["name"]
        logo = ev["logo"]
        sport = ev.get("sport", "Sports")
        url = ev["url"]

        extinf = (
            f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-language="English" group-title="{GROUP_TITLE}" group-logo="{GROUP_LOGO}",{name}'
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

    ch_count = content.count("#EXTINF")
    print(f"Generated {OUTPUT_M3U} ({ch_count} verified FanCode live sports events)")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate_fancode_playlist() else 1)
