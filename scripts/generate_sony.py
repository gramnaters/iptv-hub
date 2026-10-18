#!/usr/bin/env python3
"""
Full SonyLIV Playlist & JSON Generator
Reconstructs data/sony.json and data/sony.m3u matching doctor-8trange/zyphora schema.

Features:
- Fetches live events / channels & upcoming matches
- Uses SonyLIV / Akamai auth token parameters
- Outputs valid sony.json and playable sony.m3u
"""

import os
import sys
import json
import time
import requests
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output on Windows consoles
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

# ----------------- Configuration -----------------
OUTPUT_JSON = "data/sony.json"
OUTPUT_M3U = "data/sony.m3u"

SONY_CATALOG_SOURCES = [
    "https://raw.githubusercontent.com/doctor-8trange/zyphora/main/data/sony.json",
    "https://raw.githubusercontent.com/sportlive18/Sonyliv-Playlist-Autoupdate/main/sonyliv2.json",
    "https://raw.githubusercontent.com/sm-monirulislam/SonyLiv_Event_Playlist/main/sonyLiv_data.json"
]

COOKIE_SOURCES = [
    "https://allinonereborn2.online/jstrweb2/cookies.json"
]

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:157.0) Gecko/20100101 Firefox/157.0"
ORIGIN = "https://www.sonyliv.com"
REFERER = "https://www.sonyliv.com/"

def get_current_ist_str():
    now = datetime.now(IST)
    return now.strftime("%d-%m-%Y %H:%M")

def fetch_json(url, timeout=15):
    try:
        resp = requests.get(url, headers={"User-Agent": DEFAULT_USER_AGENT}, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"⚠️ Failed to fetch from {url}: {e}")
        return None

def fetch_active_cookie():
    for source in COOKIE_SOURCES:
        data = fetch_json(source)
        if data and isinstance(data, list):
            for item in data:
                if "cookie" in item:
                    cookie = item["cookie"]
                    # Clean prefix if __hdnea__=
                    if cookie.startswith("__hdnea__="):
                        cookie = cookie.replace("__hdnea__=", "", 1)
                    return cookie
    return None

def fetch_catalog_events():
    for source in SONY_CATALOG_SOURCES:
        data = fetch_json(source)
        if data and isinstance(data, dict):
            # Check if this matches doctor-8trange schema
            if "data" in data or "upcoming" in data:
                return data
            elif "matches" in data:
                # Transmute sm-monirulislam format to zyphora schema
                upcoming = []
                for m in data.get("matches", []):
                    upcoming.append({
                        "contentId": m.get("contentId"),
                        "video_info": {
                            "title": m.get("event_name", ""),
                            "shortDescription": m.get("event_name", ""),
                            "longDescription": m.get("event_name", ""),
                            "genres": [m.get("event_category", "Sports")],
                            "episodeTitle": ""
                        },
                        "stream_info": {
                            "Maximum_Video_Quality": "SDR",
                            "dai_asset_key": None,
                            "broadcast_channel": m.get("broadcast_channel", ""),
                            "audio_language_list": [{"lang_code": m.get("audioLanguageName", "HIN"), "lang_label": "Hindi"}],
                            "emfAttributes__audio_languages": m.get("audioLanguageName", "HIN"),
                            "platformVariants": {
                                "assetType": "MASTER",
                                "assetName": "VOD_FULL_HD",
                                "videoType": "FULL_HD",
                                "audioLanguages": [],
                                "subtitlesLanguages": [],
                                "videoUrl": "NA"
                            }
                        },
                        "air_dates": {
                            "contractStartDate": "",
                            "contractEndDate": "",
                            "originalAirDate": None
                        },
                        "image_cdn": {
                            "portrait_thumb": m.get("src", ""),
                            "thumbnail": m.get("src", ""),
                            "landscape_thumb": m.get("src", "")
                        },
                        "multiple_audio_links": []
                    })
                return {"data": [], "upcoming": upcoming}
    return {"data": [], "upcoming": []}

def generate_sony_json(catalog_data, active_token):
    time_str = get_current_ist_str()
    
    result = {
        "name": "Sony Live Matches API",
        "last_updated": time_str,
        "app_settings": {
            "PROXY": "ON",
            "state_code": "MH",
            "MULTI_CDN": "OFF",
            "Debugging": "OFF",
            "SUB_TYPE": "PREMIUM",
            "RECIVER": "OFF",
            "REALTIME": "OFF",
            "REPLACEMENT": "OFF",
            "FREEPREVIEW": "AUTO",
            "ALL_IN_ONE": "OFF",
            "SERVER_STATUS": "NORMAL",
            "USAGE_GUIDE": []
        },
        "data": catalog_data.get("data", []),
        "upcoming": catalog_data.get("upcoming", [])
    }
    return result

def generate_sony_m3u(sony_json, active_token):
    lines = [
        "#EXTM3U",
        f"#DATE:- {sony_json['last_updated']}"
    ]

    session_id = f"sess_{int(time.time()*1000)}"

    for item in sony_json.get("data", []):
        content_id = item.get("contentId", "")
        title = item.get("video_info", {}).get("title", "")
        logo = item.get("image_cdn", {}).get("thumbnail", "") or item.get("image_cdn", {}).get("landscape_thumb", "")
        genres = ", ".join(item.get("video_info", {}).get("genres", ["Sports"]))

        for audio in item.get("multiple_audio_links", []):
            lang_label = audio.get("language", "Hindi")
            lang_code = audio.get("lang_code", "HIN")
            raw_url = audio.get("data", {}).get("Playback_videoURL", "")

            if not raw_url:
                continue

            stream_url = raw_url
            if active_token:
                stream_url = f"{raw_url}?hdnea={active_token}"

            stream_url += f"|User-Agent={DEFAULT_USER_AGENT}&Referer={REFERER}&Origin={ORIGIN}&x-playback-session-id={session_id}"

            extinf = f'#EXTINF:-1 tvg-id="{content_id}" tvg-name="{title}" tvg-logo="{logo}" tvg-language="{lang_label}" group-title="{genres}",{lang_code} | {title}'
            lines.append(extinf)
            lines.append(stream_url)

    return "\n".join(lines) + "\n"

def main():
    print("🚀 Running Sony Playlist & JSON Generator...")
    os.makedirs("data", exist_ok=True)

    print("🔑 Fetching active Akamai / Sony auth token...")
    token = fetch_active_cookie()
    if token:
        print(f"✅ Token obtained: {token[:40]}...")
    else:
        print("⚠️ No dynamic token found, proceeding with catalog base URLs.")

    print("📦 Fetching latest Sony live & upcoming catalog...")
    catalog = fetch_catalog_events()
    live_count = len(catalog.get("data", []))
    upcoming_count = len(catalog.get("upcoming", []))
    print(f"✅ Loaded {live_count} live channels/events, {upcoming_count} upcoming events.")

    # Build sony.json
    sony_json = generate_sony_json(catalog, token)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(sony_json, f, indent=2, ensure_ascii=False)
    print(f"✅ Wrote JSON to {OUTPUT_JSON} ({os.path.getsize(OUTPUT_JSON)} bytes)")

    # Build sony.m3u
    sony_m3u = generate_sony_m3u(sony_json, token)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write(sony_m3u)
    print(f"✅ Wrote M3U to {OUTPUT_M3U} ({os.path.getsize(OUTPUT_M3U)} bytes)")

if __name__ == "__main__":
    main()
