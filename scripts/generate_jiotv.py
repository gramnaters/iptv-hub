#!/usr/bin/env python3
"""
generate_jiotv.py  Self-hosted JioTV playlist generator (mobile account).

Flow:
  1. Load mobile creds (jiotv_creds.json or JIOTV_CREDS env).
  2. Refresh authToken + ssoToken (jio_auth.ensure_fresh).
  3. Fetch the live channel list (v3.1).
  4. Per channel, resolve a stream via getchannelurl (v2.1, BTS tier) then
     fall back to mobile geturl (v1.1):
       - clear HLS  -> emit as HLS (plays everywhere)
       - Widevine DASH -> emit as DASH + Widevine license URL (Kodi / OTT
         Navigator decrypt via their Widevine CDM)
  5. Write playlists/jiotv.m3u.

The BTS getchannelurl endpoint (tv.media.jio.com) returns premium channels
(Sony/Star/Colors) that mobile geturl 403s, unlocking ~1040 of 1052 channels.
"""
import os
import sys
import re
import json
import base64
import time
import datetime
import requests
from concurrent.futures import ThreadPoolExecutor

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "jiotv.m3u")
COOKIE_FILE = os.path.join(ROOT_DIR, "catalogs", "jiotv_cookie.json")
KEY_CACHE = os.path.join(ROOT_DIR, "catalogs", "jiotv_keys.json")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jio_auth  # noqa: E402

USER_AGENT_PLAYT = "plaYtv/7.1.8 (Linux;Android 8.1.0) ExoPlayerLib/2.11.7"
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
    for cpath in [
        os.path.join(ROOT_DIR, "jiotv_creds.json"),
        os.path.join(ROOT_DIR, "..", "jiotv_creds.json"),
    ]:
        if os.path.exists(cpath):
            try:
                with open(cpath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return None


def fetch_channels(creds):
    # 1. try the live channel list (works on residential IP, 450 on datacenter)
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
    # 2. fall back to the baked snapshot (catalogs/jiotv_channels.json)
    snap = os.path.join(ROOT_DIR, "catalogs", "jiotv_channels.json")
    if os.path.exists(snap):
        with open(snap, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def _getchannelurl(ch, creds):
    """tv.media.jio.com getchannelurl v2.1  returns HLS + DASH(Widevine) + license."""
    cid = ch["channel_id"]
    sso = creds.get("ssoToken", "")
    sub = creds.get("subscriberId", "")
    uni = creds.get("uniqueId", "")
    dev = creds.get("deviceId", "3c6d6b5702fa09bd")
    auth = creds.get("authToken", "")

    try:
        r = requests.post(
            "https://tv.media.jio.com/apis/v2.1/getchannelurl/getchannelurl",
            json={"channel_id": str(cid), "stream_type": "Live"}, timeout=25,
            headers={
                "Content-Type": "application/json",
                "User-Agent": STB_UA,
                "appkey": "NzNiMDhlYzQyNjJm",
                "ssotoken": sso, "deviceId": dev, "crmid": sub,
                "uniqueId": uni, "subscriberId": sub,
                "lbcookie": "1", "usergroup": "tvYR7NSNn7rymo3F",
                "versionCode": "284", "accessToken": auth,
            },
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None
    return r.json()


def _mob_geturl(ch, creds):
    """mobile geturl v1.1  clear HLS for free tier."""
    cid = ch["channel_id"]
    sub = creds.get("subscriberId", "")
    dev = creds.get("deviceId", "3c6d6b5702fa09bd")
    sso = creds.get("ssoToken", "")
    uni = creds.get("uniqueId", "")

    begin = str(int(time.time() * 1000))
    srno = datetime.datetime.now().strftime("%Y%m%d")

    headers = jio_auth.auth_headers(creds)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    headers["channel_id"] = str(cid)

    try:
        r = requests.post(
            "https://jiotvapi.media.jio.com/playback/apis/v1.1/geturl?langId=6",
            headers=headers,
            data=f"channel_id={cid}&stream_type=Seek&begin={begin}&srno={srno}",
            timeout=25,
        )
    except Exception:
        return None
    if r.status_code != 200:
        return None
    return r.json()


def _strip_hdnea(url):
    return re.sub(r"[?&](__hdnea__|hdnea)=[^&\s]+", "", url)


def resolve(ch, creds):
    """Return a playlist tuple (kind, url, cookie, license) or None.

    kind is 'hls' (clear) or 'dash' (Widevine).

    Priority:
      1. mobile geturl v1.1 -> clear HLS Fallback (free tier, plays everywhere)
      2. BTS getchannelurl v2.1 -> Widevine DASH + license (premium tier; the
         BTS HLS is a stub with looping child manifests, so we use DASH)
    """
    cid = str(ch["channel_id"])

    # --- 1. mobile clear HLS ---
    md = _mob_geturl(ch, creds)
    if md:
        url = md.get("result", "")
        if url:
            try:
                r2 = requests.get(url, headers={
                    "User-Agent": USER_AGENT_PLAYT,
                    "crmid": creds.get("subscriberId", ""),
                    "deviceId": creds.get("deviceId", "3c6d6b5702fa09bd"),
                    "devicetype": "phone", "os": "Android", "osVersion": "8.1.0",
                    "ssotoken": creds.get("ssoToken", ""),
                    "uniqueId": creds.get("uniqueId", ""),
                    "usergroup": "tvYR7NSNn7rymo3F", "versionCode": "422",
                }, timeout=15)
            except Exception:
                r2 = None
            if r2 is not None and r2.status_code == 200 and "#EXT-X-KEY" not in r2.text:
                sc = (r2.headers.get("set-cookie") or "").split(";")[0].strip()
                if not sc.startswith("__hdnea__="):
                    m = re.search(r'__hdnea__=([^&\s]+)', url)
                    sc = f"__hdnea__={m.group(1)}" if m else ""
                if sc:
                    return ("hls", _strip_hdnea(url), sc, None)

    # --- 2. BTS Widevine DASH (premium) ---
    d = _getchannelurl(ch, creds)
    if d:
        mpd = d.get("mpd") or {}
        mpd_url = mpd.get("result", "") if isinstance(mpd, dict) else ""
        lic = mpd.get("key", "") if isinstance(mpd, dict) else ""
        if mpd_url and lic:
            tok = ""
            m = re.search(r'__hdnea__=([^&\s]+)', mpd_url)
            if m:
                tok = m.group(1)
            cookie = f"__hdnea__={tok}" if tok else ""
            return ("dash", mpd_url, cookie, lic)

    return None


def _ensure_wvd():
    """Return a usable .wvd path, decoding JIOTV_WVD (base64) if set.

    Decoding in Python avoids shell `echo | base64 -d` breaking on long secrets.
    """
    path = os.path.join(ROOT_DIR, "device.wvd")
    env = (os.environ.get("JIOTV_WVD") or "").strip()
    if env:
        try:
            import base64 as _b64
            s = "".join(env.split())
            data = _b64.b64decode(s + "=" * (-len(s) % 4))
            if len(data) > 100:
                with open(path, "wb") as f:
                    f.write(data)
                return path
        except Exception as e:
            print(f"  ! JIOTV_WVD decode failed: {e}")
    if os.path.exists(path) and os.path.getsize(path) > 100:
        return path
    alt = os.path.join(ROOT_DIR, "wvd", "device.wvd")
    if os.path.exists(alt) and os.path.getsize(alt) > 100:
        return alt
    return None


def generate():
    creds = load_creds()
    if not creds or not creds.get("authToken"):
        print(" No JioTV mobile credentials (jiotv_creds.json / JIOTV_CREDS).")
        return False

    print(" Refreshing JioTV tokens...")
    creds = jio_auth.ensure_fresh(creds)
    if not creds.get("authToken"):
        print(" Token refresh failed - re-login required.")
        return False

    print(" Fetching channel list...")
    try:
        channels = fetch_channels(creds)
    except Exception as e:
        print(f" Channel list failed: {e}")
        return False
    print(f"  {len(channels)} channels in catalog")

    # Locate the .wvd device file (Widevine L3 CDM) for ClearKey extraction.
    # Prefer decoding JIOTV_WVD (base64) in Python  shell `echo | base64 -d`
    # mangles long secrets. Falls back to a local device.wvd if present.
    wvd_path = _ensure_wvd()
    if wvd_path:
        import hashlib
        try:
            h = hashlib.sha256(open(wvd_path, "rb").read()).hexdigest()[:16]
            print(f"  .wvd: {wvd_path} ({os.path.getsize(wvd_path)}B, sha256:{h})")
        except Exception:
            pass
    else:
        print("  ! No .wvd (JIOTV_WVD) - ClearKey extraction disabled")

    print(" Resolving streams (BTS -> mobile fallback)...")
    out = []
    with ThreadPoolExecutor(max_workers=32) as ex:
        for i, res in enumerate(ex.map(lambda ch: (ch, resolve(ch, creds)), channels), 1):
            if res[1]:
                out.append(res)
            if i % 250 == 0:
                print(f"  ... {i}/{len(channels)} done, {len(out)} resolved")

    hls = sum(1 for _, (k, *_) in out if k == "hls")
    dash = sum(1 for _, (k, *_) in out if k == "dash")
    print(f"  resolved: {len(out)} ({hls} HLS, {dash} DASH)")

    if len(out) < 50:
        print(" Too few channels - aborting.")
        return False

    # --- ClearKey extraction for DASH (premium) channels ---
    if dash and wvd_path:
        print(f" Extracting ClearKey for {dash} premium channels (pywidevine + .wvd)...")
        import generate_jiotv_keys as jk

        cache = {}
        if os.path.exists(KEY_CACHE):
            try:
                with open(KEY_CACHE, encoding="utf-8") as f:
                    cache = json.load(f)
            except Exception:
                cache = {}

        def _extract(item):
            ch, (kind, url, cookie, lic) = item
            if kind != "dash":
                return ch, (kind, url, cookie, lic, None)
            cid = str(ch["channel_id"])
            mpd_kid = ""
            try:
                r = requests.get(url, headers={"User-Agent": STB_UA, "Cookie": cookie}, timeout=12)
                if r.status_code != 200:
                    raise ValueError("mpd " + str(r.status_code))
                mpd_kids = {k.replace("-", "").lower()
                            for k in re.findall(r'default_KID="([0-9a-fA-F\-]+)"', r.text)}
                mpd_kid = next(iter(mpd_kids), "")
                pssh = jk.get_pssh(url, cookie)
                if not pssh or not mpd_kids:
                    raise ValueError("no pssh/kid")
                keys = jk.extract_keys(wvd_path, pssh, lic, cookie, creds, cid)
                if not keys:
                    raise ValueError("no keys")
                for k in keys:
                    kid_hex = base64.urlsafe_b64decode(k["kid"] + "==").hex()
                    key_hex = base64.urlsafe_b64decode(k["k"] + "==").hex()
                    if kid_hex in mpd_kids:
                        return ch, ("clearkey", url, cookie, f"{kid_hex}:{key_hex}", f"{kid_hex}:{key_hex}")
                raise ValueError("kid mismatch")
            except Exception:
                cached = cache.get(cid)
                if cached and cached.split(":")[0] in mpd_kids:
                    return ch, ("clearkey", url, cookie, cached, None)
                return ch, ("dash", url, cookie, lic, None)

        extracted = []
        fresh = {}
        done = 0
        with ThreadPoolExecutor(max_workers=16) as ex:
            for ch, res in ex.map(_extract, out):
                kind, url, cookie, lic, newkey = res
                if newkey:
                    fresh[str(ch["channel_id"])] = newkey
                extracted.append((ch, (kind, url, cookie, lic)))
                done += 1
                if done % 50 == 0:
                    print(f"  ... {done}/{len(out)} key-extracted")
        out = extracted

        if fresh:
            cache.update(fresh)
            try:
                with open(KEY_CACHE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, indent=2)
            except Exception:
                pass
        clear_early = sum(1 for _, (k, *_) in out if k == "clearkey")
        print(f"  ClearKey verified: {clear_early}/{dash} ({len(fresh)} new, {len(cache)} cached)")

    # DASH entries without a key that matches the manifest are unplayable on
    # this account. Keep them out of the playlist unless JIO_KEEP_DASH=1.
    blocked = [(ch, t[1]) for ch, t in out if t[0] == "dash"]
    if blocked and os.environ.get("JIO_KEEP_DASH") != "1":
        out = [(ch, t) for ch, t in out if t[0] != "dash"]
        try:
            with open(os.path.join(ROOT_DIR, "catalogs", "jiotv_premium_blocked.json"), "w",
                      encoding="utf-8") as f:
                json.dump([{"channel_id": str(ch["channel_id"]), "channel_name": ch["channel_name"],
                            "reason": "license keys do not match manifest kid"} for ch, _ in blocked],
                          f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        print(f"  dropped {len(blocked)} DASH channels without a usable key")

    clear = sum(1 for _, (k, *_) in out if k == "clearkey")
    dash_remaining = sum(1 for _, (k, *_) in out if k == "dash")
    print(f"  clearkey: {clear}, dash(no key): {dash_remaining}")

    lines = ["#EXTM3U", f"# Total Channels: {len(out)}", ""]
    for ch, (kind, url, cookie, lic) in out:
        name = ch["channel_name"]
        category = GENRE.get(ch.get("channelCategoryId"), "Other")
        logo = "https://jiotv.catchup.cdn.jio.com/dare_images/images/" + ch.get("logoUrl", "")
        cid = str(ch["channel_id"])

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="JioTV - {category}",{name}'
        )
        if kind == "hls":
            lines.append(f"#EXTVLCOPT:http-user-agent={STB_UA}")
            lines.append(f"#EXTVLCOPT:http-cookie={cookie}")
            lines.append(url)
        elif kind == "clearkey":
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={lic}")
            lines.append(f"#EXTVLCOPT:http-user-agent={STB_UA}")
            lines.append(f"#EXTVLCOPT:http-cookie={cookie}")
            lines.append(url)
        else:  # dash (Widevine fallback, no extracted key)
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=com.widevine.alpha")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={lic}")
            lines.append(f"#EXTVLCOPT:http-user-agent={STB_UA}")
            lines.append(f"#EXTVLCOPT:http-cookie={cookie}")
            lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            json.dump({"updated_at": datetime.datetime.now().isoformat(),
                       "total": len(out), "hls": hls, "dash": dash,
                       "catalog": len(channels)}, f, indent=2)
    except Exception:
        pass

    print(f" Wrote {OUTPUT_M3U} with {len(out)} channels ({hls} HLS, {dash} DASH).")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate() else 1)
