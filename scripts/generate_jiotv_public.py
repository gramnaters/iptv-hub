#!/usr/bin/env python3
"""JioTV playlist from the public catalog and the allinone cookie files."""
import os
import re
import sys

import requests

CHANNELS_URL = "https://raw.githubusercontent.com/qwerty180506/json/refs/heads/main/Geoplus.json"
COOKIE_URL = "https://allinonereborn2.online/jstrweb2/cookies.json"
SPORTS_URL = "https://allinonereborn2.online/jtv-fetch/jstarcookie/cookie.json"
UA = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "playlists", "jiotv.m3u")


def get_json(url):
    r = requests.get(url, headers={"Cache-Control": "no-cache"}, timeout=40)
    r.raise_for_status()
    return r.json()


def normal_cookie(data):
    if isinstance(data, str):
        return data
    if isinstance(data, list):
        item = next((x for x in data if isinstance(x, dict) and x.get("cookie")), None)
        return (item or {}).get("cookie") or ""
    if isinstance(data, dict):
        return data.get("cookie") or ""
    return ""


def sports_urls(data):
    found = {}
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = list(data.get("successful_results") or []) + list(data.get("failed_results") or [])
    else:
        rows = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("channel_id") or "")
        url = item.get("final_url") or (item.get("error_details") or {}).get("final_url") or ""
        if cid and url:
            found[cid] = re.sub(r"/output/", "/WDVLive/", url, count=1, flags=re.I)
    return found


def keys_of(channel):
    pairs = []
    if channel.get("keyId") and channel.get("key"):
        pairs.append((channel["keyId"], channel["key"]))
    for item in channel.get("keys") or []:
        if isinstance(item, dict) and item.get("keyId") and item.get("key"):
            pairs.append((item["keyId"], item["key"]))
    if isinstance(channel.get("clearkey"), dict):
        pairs.extend(channel["clearkey"].items())
    clean = []
    for kid, key in pairs:
        if re.fullmatch(r"[0-9a-fA-F]{32}", str(kid)) and re.fullmatch(r"[0-9a-fA-F]{32}", str(key)):
            clean.append(f"{kid}:{key}")
    return ",".join(clean)


def quote(value):
    return str(value or "").replace('"', "'")


def group_of(channel):
    name = channel.get("category") or channel.get("group") or "Other"
    if name == "Malyalam":
        name = "Malayalam"
    return f"JioTV | {name}"


def main():
    channels = get_json(CHANNELS_URL)
    cookie = normal_cookie(get_json(COOKIE_URL))
    sports = sports_urls(get_json(SPORTS_URL))
    if not isinstance(channels, list) or not cookie:
        sys.exit("catalog or cookie missing")
    lines = ["#EXTM3U"]
    hosts = {"mblive": 0, "pllive": 0, "other": 0}
    for ch in channels:
        if not isinstance(ch, dict):
            continue
        cid = str(ch.get("id") or "")
        base = ch.get("url") or ""
        final = sports.get(cid)
        if not final:
            if not base:
                continue
            final = base + ("&" if "?" in base else "?") + cookie
        if "jiotvpllive" in final:
            hosts["pllive"] += 1
        elif "jiotvmblive" in final:
            hosts["mblive"] += 1
        else:
            hosts["other"] += 1
        name = quote(ch.get("name") or "JioTV")
        logo = quote(ch.get("logo") or "")
        group = quote(group_of(ch))
        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" group-title="{group}",{name}'
        )
        if ".mpd" in final.lower() or ch.get("type") == "dash":
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            key = keys_of(ch)
            if key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={key}")
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(final)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{sum(hosts.values())} channels {hosts} sports={len(sports)} -> {OUT}")


if __name__ == "__main__":
    main()
