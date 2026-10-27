#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "jiotv_catalog.json")
KEYS_FILE = os.path.join(ROOT, "catalogs", "jiotv_keys.json")
COOKIE_FILE = os.path.join(ROOT, "catalogs", "jiotv_cookie.json")
OUT = os.path.join(ROOT, "playlists", "jiotv.m3u")

PUBLIC_COOKIE_SOURCES = [
    "https://raw.githubusercontent.com/sportlive18/Sportlink-wtf/refs/heads/main/cookie.json",
    "https://raw.githubusercontent.com/qwerty180506/Geo/refs/heads/main/jiotv_cf.m3u",
    "https://raw.githubusercontent.com/purupc00-dev/Gmax-JioTV/refs/heads/main/Playlists/JioTV_S10.m3u",
    "https://allinonereborn2.online/jstrweb2/cookies.json",
] + ([os.environ["JTV_URL"]] if os.environ.get("JTV_URL") else [])
# Premium/BTS channels (Zee, &TV, Star on jiotvpllive) reject the wildcard token and
# only play with a token whose acl is scoped to that channel's own path.
PER_CHANNEL_SOURCE = "https://premiumplugx.com/gibt/shoebpl.php"
CLEARKEY_RE = re.compile(r"^[0-9a-fA-F]{32}:[0-9a-fA-F]{32}(,[0-9a-fA-F]{32}:[0-9a-fA-F]{32})*$")
USER_AGENT = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0"
ORIGIN = "https://www.jiotv.com/"


def get_ist_time():
    return datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")


def expiry_hours(cookie):
    m = re.search(r"~exp=(\d+)~", cookie or "")
    if not m:
        return -1.0
    return (int(m.group(1)) - int(time.time())) / 3600.0


def try_mint_direct_cookie():
    creds = None
    creds_path = None
    if os.environ.get("JIOTV_CREDS"):
        try:
            creds = json.loads(os.environ["JIOTV_CREDS"])
        except Exception:
            pass
    if not creds:
        for p in [os.path.join(ROOT, "jiotv_creds.json"), os.path.join(ROOT, "..", "jiotv_creds.json")]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        creds = json.load(f)
                    creds_path = p
                    break
                except Exception:
                    pass
    if not creds:
        return None
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import jio_auth
        creds = jio_auth.ensure_fresh(creds)
        if creds_path and creds.get("authToken"):
            try:
                with open(creds_path, "w", encoding="utf-8") as f:
                    json.dump(creds, f, indent=2)
            except Exception:
                pass
        auth_token = creds.get("authToken")
        if not auth_token:
            return None
        payload = {"stream_type": "Seek", "channel_id": "144"}
        headers = {
            "appkey": "NzNiMDhlYzQyNjJm",
            "devicetype": "phone",
            "os": "android",
            "deviceId": creds.get("deviceId", "3c6d6b5702fa09bd"),
            "isott": "false",
            "channel_id": "144",
            "accesstoken": auth_token,
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "okhttp/4.2.2"
        }
        res = requests.post("https://jiotvapi.media.jio.com/playback/apis/v1/geturl?langId=6", data=payload, headers=headers, timeout=8)
        if res.status_code == 200:
            result_url = res.json().get("result", "")
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=[^~"\'\r\n\s]+~hmac=[a-f0-9]+)', result_url)
            if m:
                cookie = m.group(1)
                if "acl=/*" in cookie:
                    return cookie
    except Exception:
        pass
    return None


def fetch_live_cookie():
    if os.path.exists(COOKIE_FILE):
        try:
            with open(COOKIE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            cookie = data.get("cookie", "")
            if expiry_hours(cookie) > 0.5:
                return cookie
        except Exception:
            pass

    direct = try_mint_direct_cookie()
    if direct and expiry_hours(direct) > 0.5:
        return direct

    for src in PUBLIC_COOKIE_SOURCES:
        try:
            r = requests.get(src, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code == 200:
                # Search for wildcard __hdnea__ token
                matches = re.findall(r'(__hdnea__=st=\d+~exp=(\d+)~acl=/\*~hmac=[a-f0-9]+)', r.text)
                for full_cookie, exp_str in matches:
                    if expiry_hours(full_cookie) > 0.5:
                        print(f"JioTV: Acquired active wildcard token from source {PUBLIC_COOKIE_SOURCES.index(src) + 1} (TTL: {expiry_hours(full_cookie):.1f}h)")
                        return full_cookie
                # Also check JSON structure if present
                try:
                    data = r.json()
                    c = data.get("cookie", "") if isinstance(data, dict) else ""
                    if c and "acl=/*" in c and expiry_hours(c) > 0.5:
                        print(f"JioTV: Acquired active token from JSON source {PUBLIC_COOKIE_SOURCES.index(src) + 1} (TTL: {expiry_hours(c):.1f}h)")
                        return c
                except Exception:
                    pass
        except Exception as e:
            continue

    if os.path.exists(OUT):
        try:
            with open(OUT, "r", encoding="utf-8") as f:
                content = f.read(5000)
            m = re.search(r'(__hdnea__=st=\d+~exp=\d+~acl=/\*~hmac=[a-f0-9]+)', content)
            if m:
                cookie = m.group(1)
                if expiry_hours(cookie) > 0.5:
                    return cookie
        except Exception:
            pass

    return ""


def fetch_channel_overrides():
    try:
        r = requests.get(PER_CHANNEL_SOURCE, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        items = r.json() if r.status_code == 200 else []
    except Exception:
        return {}, {}
    streams, clearkeys = {}, {}
    for it in items if isinstance(items, list) else []:
        cid = str(it.get("id"))
        ck = (it.get("clearkey") or "").strip()
        if CLEARKEY_RE.match(ck):
            clearkeys[cid] = ck
        cookie = ((it.get("headers") or {}).get("cookie") or "").strip()
        url = (it.get("mpd_url") or "").split("?")[0]
        if url and "acl=/bpk-tv/" in cookie and expiry_hours(cookie) > 0.5:
            streams[cid] = (url, cookie)
    return streams, clearkeys


def load_channels():
    if not os.path.exists(CATALOG):
        return [], {}
    with open(CATALOG, "r", encoding="utf-8") as f:
        channels = json.load(f)

    keys = {}
    if os.path.exists(KEYS_FILE):
        try:
            with open(KEYS_FILE, "r", encoding="utf-8") as f:
                keys = json.load(f)
        except Exception:
            pass

    return channels, keys


def main():
    channels, keys = load_channels()
    if not channels:
        print("Missing JioTV catalog.")
        return 1

    cookie = fetch_live_cookie()
    if not cookie:
        print("Failed to acquire live playback token.")
        return 1
    overrides, feed_keys = fetch_channel_overrides()
    used_overrides = 0

    now_ist = get_ist_time()
    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: jiotv",
        f"# Total Channels: {len(channels)}",
        f"# Cookie: {cookie}",
        "",
    ]

    for ch in channels:
        cid = str(ch.get("id") or ch.get("tvg-id") or "")
        name = ch.get("name") or ch.get("channel-name") or "JioTV Channel"
        cat = ch.get("category") or ch.get("group") or ch.get("group-title") or "General"
        logo = ch.get("logo") or ch.get("tvg-logo") or ""
        url = ch.get("url") or ch.get("mpd_url") or ""

        key_id = ch.get("keyId") or ch.get("kid") or ""
        key = ch.get("key") or ""
        if not key_id or not key:
            cached_k = keys.get(cid, "")
            if ":" in cached_k:
                key_id, key = cached_k.split(":", 1)

        base_url = url.split("?")[0] if "?" in url else url
        ch_cookie = cookie
        license_key = feed_keys.get(cid) or (f"{key_id}:{key}" if key_id and key else "")
        if cid in overrides:
            base_url, ch_cookie = overrides[cid]
            used_overrides += 1
        elif "jiotvpllive.cdn.jio.com" in base_url:
            base_url = base_url.replace("jiotvpllive.cdn.jio.com", "jiotvmblive.cdn.jio.com").replace("_BTS", "_MOB")

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="JioTV - {cat}",{name}'
        )

        is_dash = ".mpd" in base_url.lower()
        if is_dash:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            if license_key:
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={license_key}")

        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(f"#EXTVLCOPT:http-cookie={ch_cookie}")

        hdr = {
            "User-Agent": USER_AGENT,
            "Origin": ORIGIN,
            "Cookie": ch_cookie,
        }
        lines.append(f"#EXTHTTP:{json.dumps(hdr, ensure_ascii=False)}")
        lines.append(f"{base_url}?{ch_cookie}")
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump({"updated_at": now_ist, "cookie": cookie}, f, indent=2)
    except Exception:
        pass

    hrs = expiry_hours(cookie)
    print(f"JioTV: generated {OUT} ({len(channels)} channels, {used_overrides} with per-channel tokens, token TTL: {hrs:.1f}h)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
