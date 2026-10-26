#!/usr/bin/env python3
"""
JioTV Widevine key extraction utility.
"""
import os
import sys
import re
import json
import base64
import argparse
import requests

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jio_auth  # noqa: E402

STB_UA = "JioTVPlus/2.8.4_2076/PlugX(PlugX;JioSTB) JioTvPlus-AndroidTv"

GENRE = {
    8: "Sports", 5: "Entertainment", 6: "Movies", 12: "News", 13: "Music",
    7: "Kids", 9: "Lifestyle", 10: "Infotainment", 15: "Devotional",
    16: "Business", 17: "Educational", 18: "Shopping", 19: "JioDarshan",
}


def load_creds():
    if os.environ.get("JIOTV_CREDS"):
        try:
            return json.loads(os.environ["JIOTV_CREDS"])
        except Exception:
            pass
    for p in [os.path.join(ROOT_DIR, "jiotv_creds.json"),
              os.path.join(ROOT_DIR, "..", "jiotv_creds.json")]:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
    return None


def fetch_channels(creds):
    try:
        headers = jio_auth.auth_headers(creds)
        url = ("https://jiotvapi.cdn.jio.com/apis/v3.1/getMobileChannelList/get/"
               "?langId=6&os=android&devicetype=phone&usertype=JIO&version=315&langId=6")
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        chans = r.json().get("result", [])
        if chans:
            return chans
    except Exception:
        pass
    snap = os.path.join(ROOT_DIR, "catalogs", "jiotv_channels.json")
    if os.path.exists(snap):
        with open(snap, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def get_premium(ch, creds):
    """Return (mpd_url, license_url, cookie) for a channel, or None if not premium/DASH."""
    sso = creds.get("ssoToken", "")
    sub = creds.get("subscriberId", "")
    uni = creds.get("uniqueId", "")
    dev = creds.get("deviceId", "3c6d6b5702fa09bd")
    auth = creds.get("authToken", "")
    cid = str(ch["channel_id"])

    try:
        r = requests.post(
            "https://tv.media.jio.com/apis/v2.1/getchannelurl/getchannelurl",
            json={"channel_id": cid, "stream_type": "Live"}, timeout=15,
            headers={
                "Content-Type": "application/json", "User-Agent": STB_UA,
                "appkey": "NzNiMDhlYzQyNjJm", "ssotoken": sso, "deviceId": dev,
                "crmid": sub, "uniqueId": uni, "subscriberId": sub,
                "lbcookie": "1", "usergroup": "tvYR7NSNn7rymo3F",
                "versionCode": "284", "accessToken": auth,
            },
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None

    d = r.json()
    mpd = d.get("mpd") or {}
    mpd_url = mpd.get("result", "") if isinstance(mpd, dict) else ""
    lic = mpd.get("key", "") if isinstance(mpd, dict) else ""
    if not mpd_url or not lic:
        return None

    m = re.search(r'__hdnea__=([^&\s]+)', mpd_url)
    cookie = f"__hdnea__={m.group(1)}" if m else ""
    return mpd_url, lic, cookie


def get_pssh(mpd_url, cookie):
    r = requests.get(mpd_url, headers={
        "User-Agent": STB_UA, "Cookie": cookie,
    }, timeout=10)
    if r.status_code != 200:
        return None
    m = re.search(r'<cenc:pssh[^>]*>([^<]+)</cenc:pssh>', r.text)
    return m.group(1) if m else None


def _srno():
    import datetime
    n = datetime.datetime.now()
    return f"{n.year % 100:02d}{n.month:02d}{n.day:02d}{n.hour:02d}{n.minute:02d}{int(n.microsecond / 1000):03d}"


def extract_keys(wvd_path, pssh, license_url, cookie, creds, channel_id):
    """Use pywidevine to POST a signed challenge to license_url and return content keys."""
    from pywidevine.cdm import Cdm
    from pywidevine.device import Device
    from pywidevine.pssh import PSSH

    device = Device.load(wvd_path)
    cdm = Cdm.from_device(device)
    session_id = cdm.open()
    try:
        challenge = cdm.get_license_challenge(session_id, PSSH(pssh))

        # Full auth headers required by tv.media.jio.com/proxy (JioTV-Go DRMKeyHandler).
        headers = {
            "accesstoken": creds.get("authToken", ""),
            "Connection": "keep-alive",
            "os": "android",
            "appName": "RJIL_JioTV",
            "subscriberId": creds.get("subscriberId", ""),
            "User-Agent": "plaYtv/7.1.8 (Linux;Android 8.1.0) ExoPlayerLib/2.11.7",
            "ssotoken": creds.get("ssoToken", ""),
            "x-platform": "android",
            "srno": _srno(),
            "crmid": creds.get("subscriberId", ""),
            "channelid": channel_id,
            "uniqueId": creds.get("uniqueId", ""),
            "versionCode": "422",
            "usergroup": "tvYR7NSNn7rymo3F",
            "devicetype": "phone",
            "osVersion": "13",
            "deviceId": creds.get("deviceId", "3c6d6b5702fa09bd"),
            "Content-Type": "application/octet-stream",
            "Cookie": cookie,
        }
        r = requests.post(license_url, data=challenge, headers=headers, timeout=20)
        if r.status_code != 200:
            return None
        cdm.parse_license(session_id, r.content)
        keys = []
        for k in cdm.get_keys(session_id):
            if k.type == "CONTENT":
                kid = k.kid.hex
                key = k.key.hex()
                keys.append({
                    "kty": "oct",
                    "kid": base64.urlsafe_b64encode(bytes.fromhex(kid)).decode().rstrip("="),
                    "k": base64.urlsafe_b64encode(bytes.fromhex(key)).decode().rstrip("="),
                })
        return keys
    finally:
        cdm.close(session_id)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wvd", required=True, help="path to .wvd Widevine device file")
    ap.add_argument("--out", default=os.path.join(ROOT_DIR, "catalogs", "jiotv_keys.json"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not os.path.exists(args.wvd):
        print(f"❌ .wvd file not found: {args.wvd}")
        sys.exit(1)

    creds = load_creds()
    if not creds or not creds.get("authToken"):
        print("❌ No JioTV creds.")
        sys.exit(1)

    print("🔑 Refreshing tokens...")
    creds = jio_auth.ensure_fresh(creds)

    channels = fetch_channels(creds)
    print(f"📡 {len(channels)} channels")

    out = []
    for i, ch in enumerate(channels, 1):
        meta = get_premium(ch, creds)
        if not meta:
            continue
        mpd_url, lic, cookie = meta
        pssh = get_pssh(mpd_url, cookie)
        if not pssh:
            continue
        try:
            keys = extract_keys(args.wvd, pssh, lic, cookie, creds, str(ch["channel_id"]))
        except Exception as e:
            print(f"  ⚠️ {ch['channel_name']}: {e}")
            continue
        if keys:
            out.append({
                "contentId": str(ch["channel_id"]),
                "name": ch["channel_name"],
                "mpd": mpd_url.split("?")[0],
                "cookie": cookie,
                "key": {"keys": keys, "type": "temporary"},
            })
            print(f"  ✅ {ch['channel_name']}: {len(keys)} keys")
        else:
            print(f"  ❌ {ch['channel_name']}: no keys")
        if args.limit and len(out) >= args.limit:
            break

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Extracted keys for {len(out)} channels -> {args.out}")


if __name__ == "__main__":
    main()
