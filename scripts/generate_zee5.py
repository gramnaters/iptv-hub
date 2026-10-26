#!/usr/bin/env python3
"""
ZEE5 Native Generator.
100% self-hosted & self-contained generator using official ZEE5 APIs:
1. ZEE5 India: 32 pure CloudFront DASH channels with W3C ClearKeys from catalogs/zee5_catalog.json.
2. ZEE5 Free & Fast Live Channels: Discovered directly from official ZEE5 Catalog API
   (catalogapi.zee5.com) with native playback tokens minted from spapi.zee5.com.
Zero third-party APIs or aggregator scrapers.
"""
import base64
import json
import os
import re
import sys
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "zee5_catalog.json")
STATUS = os.path.join(ROOT, "catalogs", "zee5_status.json")
OUT = os.path.join(ROOT, "playlists", "zee5.m3u")

TOKEN_URL = "https://launchapi.zee5.com/token/platform_tokens"
CATALOG_URL = "https://catalogapi.zee5.com/v1/channel"
PLAYBACK_URL = "https://spapi.zee5.com/singlePlayback/v2/getDetails/secure"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg"
UA = "plaYtv/7.1.5 (Linux;Android 14) ExoPlayerLib/2.11.7"
DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"


def get_platform_token():
    try:
        req = urllib.request.Request(TOKEN_URL, headers={"User-Agent": DESKTOP_UA})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("token")
    except Exception as e:
        print(f"ZEE5: Failed to fetch platform token: {e}")
        return None


def fetch_all_catalog_channels():
    channels = []
    page = 1
    while True:
        url = f"{CATALOG_URL}?content_types=all&translation=en&orderby=popularity&page={page}"
        req = urllib.request.Request(url, headers={"User-Agent": DESKTOP_UA})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data.get("items", [])
                if not items:
                    break
                channels.extend(items)
                if len(items) < 25:
                    break
                page += 1
        except Exception as e:
            print(f"ZEE5: Catalog pagination stopped at page {page} ({e})")
            break
    return channels


def get_dd_token():
    dd_obj = {
        "schema_version": "1",
        "os_name": "N/A",
        "os_version": "N/A",
        "platform_name": "Chrome",
        "platform_version": "104",
        "device_name": "",
        "app_name": "Web",
        "app_version": "2.52.31",
        "player_capabilities": {
            "audio_channel": ["STEREO"],
            "video_codec": ["H264"],
            "container": ["MP4", "TS"],
            "package": ["DASH", "HLS"],
            "resolution": ["240p", "SD", "HD", "FHD"],
            "dynamic_range": ["SDR"],
        },
        "security_capabilities": {
            "encryption": ["WIDEVINE_AES_CTR"],
            "widevine_security_level": ["L3"],
            "hdcp_version": ["HDCP_V1", "HDCP_V2", "HDCP_V2_1", "HDCP_V2_2"],
        },
    }
    return base64.b64encode(json.dumps(dd_obj).encode("utf-8")).decode("utf-8")


def resolve_native_stream(item, platform_token, dd_token):
    cid = item.get("id")
    title = item.get("title", "")
    guest = str(uuid.uuid4())
    pb_url = (
        f"{PLAYBACK_URL}?channel_id={cid}&device_id={guest}&platform_name=desktop_web"
        f"&translation=en&user_language=en,hi&country=IN&state=&app_version=4.24.0"
        f"&user_type=guest&check_parental_control=false"
    )
    body = json.dumps({
        "x-access-token": platform_token,
        "X-Z5-Guest-Token": guest,
        "x-dd-token": dd_token,
    }).encode("utf-8")

    req = urllib.request.Request(pb_url, data=body, headers={
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://www.zee5.com",
        "Referer": "https://www.zee5.com/",
        "User-Agent": DESKTOP_UA,
    })

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            vt = data.get("keyOsDetails", {}).get("video_token")
            if vt:
                # Get best logo
                images = item.get("image_url", {}) or item.get("list_image", "")
                logo = ""
                if isinstance(images, dict):
                    logo = images.get("16:9") or images.get("9:16") or ""
                elif isinstance(images, str):
                    logo = images
                if not logo and item.get("image"):
                    logo = "https://akamaividz2.zee5.com/image/upload/resources/" + item.get("image")
                if not logo:
                    logo = GROUP_LOGO

                genres = item.get("genres", [])
                cat = genres[0].get("value") if (genres and isinstance(genres[0], dict)) else "Entertainment"

                return {
                    "id": cid,
                    "name": title,
                    "logo": logo,
                    "cat": cat,
                    "group": "ZEE5 Worldwide",
                    "url": vt,
                }
    except Exception:
        pass
    return None


def main():
    if not os.path.exists(CATALOG):
        print(f"ZEE5: Missing local catalog: {CATALOG}")
        return 1

    with open(CATALOG, "r", encoding="utf-8") as f:
        india_channels = json.load(f)

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        "# Source: ZEE5 Native CloudFront & Official Playback Minting",
        "",
    ]

    # 1. ZEE5 India (32 Verified ClearKey Channels)
    for ch in india_channels:
        cid = ch.get("id", "")
        name = ch.get("name", "")
        logo = ch.get("logo", GROUP_LOGO)
        cat = ch.get("cat", "Entertainment")
        url = ch.get("url", "")
        key = ch.get("key", "")

        is_dash = ".mpd" in url.lower()
        type_attr = ' type="dash"' if is_dash else ""

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{cat}" group-title="ZEE5 India" group-logo="{GROUP_LOGO}"{type_attr},{name}'
        )

        if is_dash and key:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")

        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    # 2. ZEE5 Native Live Streams from Official API
    print("ZEE5: Minting live tokens natively from official ZEE5 APIs...")
    platform_token = get_platform_token()
    native_channels = []
    if platform_token:
        dd_token = get_dd_token()
        catalog_items = fetch_all_catalog_channels()
        print(f"ZEE5: Fetched {len(catalog_items)} live channels from catalogapi.zee5.com")

        # Concurrent resolution
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [pool.submit(resolve_native_stream, item, platform_token, dd_token) for item in catalog_items]
            for fut in futures:
                res = fut.result()
                if res:
                    native_channels.append(res)

        print(f"ZEE5: Successfully minted native streams for {len(native_channels)} channels")
        for ch in native_channels:
            cid = ch["id"]
            name = ch["name"]
            logo = ch["logo"]
            cat = ch["cat"]
            url = ch["url"]

            lines.append(
                f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
                f'tvg-category="{cat}" group-title="ZEE5 Worldwide" group-logo="{GROUP_LOGO}",{name}'
            )
            lines.append(f"#EXTVLCOPT:http-user-agent=com.graymatrix.did;Android TV;5.82.6(203230929);Android(10);Xiaomi(Redmi Note 8 Pro)")
            lines.append(f"#EXTVLCOPT:http-referrer=https://www.zee5.com/")
            lines.append(f'#EXTHTTP:{{"User-Agent":"com.graymatrix.did;Android TV;5.82.6(203230929);Android(10);Xiaomi(Redmi Note 8 Pro)","Referer":"https://www.zee5.com/"}}')
            lines.append(url)
            lines.append("")

    total_count = len(india_channels) + len(native_channels)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": stamp,
            "total": total_count,
            "zee5_india": len(india_channels),
            "zee5_worldwide": len(native_channels),
            "source": "100% Native Official ZEE5 APIs"
        }, f, indent=2)

    print(f"ZEE5: Wrote {OUT} ({total_count} channels: {len(india_channels)} India ClearKey, {len(native_channels)} Worldwide Native Minted)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
