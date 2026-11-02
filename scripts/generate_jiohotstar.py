#!/usr/bin/env python3
"""Self-mint JioHotstar (Hotstar) live channels from our own account.

How the token works
-------------------
Hotstar's linear CDN (``livetv.hotstar.com`` / ``jcevents.hotstar.com`` /
``live09p.hotstar.com``) is Akamai Segmented-Media-Protection auth'd by a
single wildcard cookie::

    hdntl=exp=<epoch>~acl=%2f*~id=<hex>~data=hdntl~hmac=<sha256>

``acl=%2f*`` unlocks every channel, and the token lives ~24 h.  It is issued
as a ``Set-Cookie`` when you fetch the livetv manifest that the BFF hands back
for the one linear id the web backend resolves (1540072843).  So the mint is:

    1. POST https://www.hotstar.com/api/internal/bff/v2/start
       (session cookie + x-hs-usertoken)  ->  fresh JWT + proxystate
    2. POST again with the proxystate      ->  livetv.hotstar.com/...m3u8 URL
    3. GET that manifest (Android UA)      ->  Set-Cookie: hdntl=<fresh, acl=/*>

The channel catalogue (names / logos / stream paths / ClearKeys) is committed
in ``catalogs/hstar.json``; only the short-lived ``hdntl`` needs re-minting.

CI note: Hotstar blocks datacenter egress, so the three calls are tried direct
first and then rotated through ``PROXY_LIST`` (the same Indian proxies the
Zee5/SonyLIV generators use).
"""
import os
import re
import sys
import json
import time
import base64
import requests
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "jiohotstar.m3u")
CATALOG = os.path.join(ROOT_DIR, "catalogs", "hstar.json")

BFF_START = "https://www.hotstar.com/api/internal/bff/v2/start"
HDNTL_ID = "1540072843"

WEB_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
ANDROID_UA = "Hotstar;in.startv.hotstar/25.02.24.8.11169"
CLIENT = "platform:web;app_version:26.09.23.1;browser:Chrome;schema_version:0.0.1"
REFERER = "https://www.hotstar.com/"
ORIGIN = "https://www.hotstar.com"

GROUP = "JioHotstar"
MIN_CHANNELS = 10

CAPS = {
    "ads": ["non_ssai", "ssai"], "audio_channel": ["stereo"],
    "container": ["fmp4", "fmp4br", "ts"], "dvr": ["short"],
    "dynamic_range": ["sdr"], "encryption": ["plain"],
    "ladder": ["web", "tv", "phone"], "package": ["dash", "hls"],
    "resolution": ["sd", "hd", "fhd"], "video_codec": ["h264"],
    "video_codec_non_secure": ["h265", "h264"],
}
DRM = {"hdcp_version": ["HDCP_V2_2"], "widevine_security_level": [],
       "playready_security_level": []}

# Local-dev fallback so the script works on the dev box without a secret.
LOCAL_COOKIE = os.path.join(os.path.dirname(ROOT_DIR), "hotstar_cookies_fresh.json")

# Cloud self-mint source: our own Cloudflare worker mints the wildcard `hdntl`
# via Cloudflare Browser Rendering (a real Chrome on the edge, which Akamai
# accepts).  Hotstar's BFF 403s datacenter/proxy egress, so GitHub Actions
# cannot mint directly; it calls this worker instead.  No PC required.
JHS_WORKER = os.environ.get("JHS_WORKER", "https://jhs.gramnaters.workers.dev")
JHS_MINT_SECRET = os.environ.get("JHS_MINT_SECRET", "")


def load_cookie():
    raw = os.environ.get("HS_COOKIE", "").strip()
    if raw:
        # Secret may be base64 of the JSON (CI) or the raw JSON.
        if raw.lstrip().startswith("{"):
            data = raw
        else:
            try:
                data = base64.b64decode(raw).decode("utf-8")
            except Exception:
                data = raw
        return json.loads(data)
    if os.path.exists(LOCAL_COOKIE):
        with open(LOCAL_COOKIE, encoding="utf-8") as f:
            return json.load(f)
    return None


def _proxies():
    return [{"http": l.strip(), "https": l.strip()}
            for l in os.environ.get("PROXY_LIST", "").splitlines()
            if l.strip().startswith("http")]


def token_expiry(token):
    m = re.search(r"(?:exp|Expires)=(\d{10})", token or "")
    return int(m.group(1)) if m else 0


def _deeplink(cid):
    return ("/in/shows/x/{}/live/watch?client_capabilities={}&drm_parameters={}"
            "&request_features=consent_supported").format(
        cid,
        requests.utils.quote(json.dumps(CAPS, separators=(",", ":"))),
        requests.utils.quote(json.dumps(DRM, separators=(",", ":"))),
    )


def _start_headers(cj, tok, extra=None):
    jar = {
        "deviceId": cj.get("deviceId"), "userHID": cj.get("userHID"),
        "userPID": cj.get("userPID"), "userCountryCode": cj.get("userCountryCode"),
        "sessionUserUP": tok, "userUP": tok,
    }
    h = {
        "User-Agent": WEB_UA, "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": ORIGIN, "Referer": ORIGIN + "/in/home",
        "Cookie": "; ".join(f"{k}={v}" for k, v in jar.items() if v),
        "x-hs-usertoken": tok, "x-hs-platform": "web", "x-hs-app": "260923001",
        "x-country-code": "in", "x-hs-accept-language": "eng",
        "x-hs-device-id": cj.get("deviceId") or "", "x-hs-client": CLIENT,
        "x-hs-retry-count": "0", "x-hs-is-retry": "false",
    }
    if extra:
        h.update(extra)
    return h


def _post_start(px, cj, tok, extra=None):
    body = {"deeplink_url": _deeplink(HDNTL_ID), "app_launch_count": 34}
    return requests.post(BFF_START, headers=_start_headers(cj, tok, extra),
                         data=json.dumps(body), proxies=px, timeout=30)


def _mint_once(px, cj):
    """One full 3-step mint.  Returns (hdntl, reason)."""
    label = "direct" if px is None else "proxy"

    # 1 + 2: session -> fresh JWT + proxystate -> livetv manifest URL
    r1 = _post_start(px, cj, cj.get("sessionUserUP") or cj.get("userUP"))
    if r1.status_code != 200:
        return None, f"{label}: start HTTP {r1.status_code}"
    fresh = r1.headers.get("x-hs-usertoken") or cj.get("sessionUserUP") or cj.get("userUP")
    ps = r1.headers.get("x-hs-setproxystate") or ""
    loc = cj.get("fresh_loc") or ""
    extra = {
        "x-hs-proxystate": ps,
        "x-hs-proxystate-ud": "loc=" + loc,
        "x-hs-client-targeting": "ad_id:" + (cj.get("deviceId") or "") + ";user_lat:false;",
    }
    r2 = _post_start(px, cj, fresh, extra)
    if r2.status_code != 200:
        return None, f"{label}: start#2 HTTP {r2.status_code}"
    flat = r2.text.replace("\\/", "/")
    m = re.search(r'https://livetv\.hotstar\.com/[^"\'\\ ]+\.m3u8\?[^"\'\\ ]*', flat)
    if not m:
        return None, f"{label}: no livetv manifest URL in BFF response"

    # 3: fetch manifest -> Set-Cookie hdntl
    r3 = requests.get(m.group(0), proxies=px, timeout=30, headers={
        "User-Agent": ANDROID_UA, "Referer": REFERER, "Origin": ORIGIN,
    })
    sc = r3.headers.get("set-cookie") or ""
    cm = re.search(r'hdntl=([^;,\s]+)', sc)
    if not cm:
        return None, f"{label}: manifest {r3.status_code}, no hdntl Set-Cookie"
    hdntl = "hdntl=" + cm.group(1)
    if token_expiry(hdntl) <= time.time() + 900:
        return None, f"{label}: minted hdntl already expiring"
    return hdntl, label


def mint_hdntl(cj):
    proxies = _proxies()
    attempts = [None] + proxies
    reasons = []
    for px in attempts:
        try:
            token, why = _mint_once(px, cj)
            if token:
                print(f"Self-minted hdntl via {why} ({len(proxies)} proxies configured)")
                return token
            reasons.append(why)
        except Exception as e:
            reasons.append(f"{'direct' if px is None else 'proxy'}: {type(e).__name__}: {e}")
    print("hdntl mint failed: " + " | ".join(reasons[:8]))
    return None


def _fetch_worker_token():
    try:
        r = requests.get(f"{JHS_WORKER}/playlist.m3u", timeout=60)
        if r.status_code != 200:
            print(f"worker /playlist.m3u -> HTTP {r.status_code}")
            return None
        m = re.search(r"hdntl=([^;\s\"\\]+)", r.text)
        return ("hdntl=" + m.group(1)) if m else None
    except Exception as e:
        print(f"worker fetch: {type(e).__name__}: {e}")
        return None


def get_token_from_worker():
    """Read the wildcard `hdntl` our Cloudflare worker mints via Browser
    Rendering.  The worker's own hourly cron keeps it fresh; we only force a new
    browser mint (rate-limited) when the cached token has gone stale."""
    if not JHS_MINT_SECRET:
        print("get_token_from_worker: JHS_MINT_SECRET not set")
        return None

    token = _fetch_worker_token()
    # Healthy margin?  The worker cron re-mints at ~20h, so a token with >12h
    # left means the cron is alive and no browser launch is needed.
    if token and token_expiry(token) > time.time() + 12 * 3600:
        return token

    print("worker token stale -> forcing a Browser mint")
    try:
        pr = requests.post(f"{JHS_WORKER}/mint",
                           headers={"Authorization": "Bearer " + JHS_MINT_SECRET},
                           timeout=120)
        print(f"worker /mint -> HTTP {pr.status_code}: {pr.text[:120]}")
    except Exception as e:
        print(f"worker mint trigger: {type(e).__name__}: {e}")
    return _fetch_worker_token()


def _slug(url, i):
    try:
        from urllib.parse import urlparse
        parts = [p for p in urlparse(url).path.split("/") if p]
        parts = [re.sub(r"\.(mpd|m3u8?)$", "", p) for p in parts]
        return "-".join(parts[-3:]) or ("ch%d" % i)
    except Exception:
        return "ch%d" % i


def build_lines(hdntl):
    lines = []
    with open(CATALOG, encoding="utf-8") as f:
        items = json.load(f)

    for i, c in enumerate(items):
        if not c or not c.get("url"):
            continue
        name = str(c.get("name") or "").replace('"', "'").strip()
        logo = str(c.get("logo") or "").strip()
        url = c["url"]
        typ = c.get("type") or ("mpd" if url.endswith(".mpd") else "hls")
        tid = "hs_" + _slug(url, i)

        lines.append(f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{name}" tvg-logo="{logo}" group-title="{GROUP}",{name}')

        if typ in ("mpd", "dash"):
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.stream_headers="
                         f"User-Agent={ANDROID_UA}&Referer={REFERER}&Origin={ORIGIN}&Cookie={hdntl}")
            if c.get("keyId") and c.get("key"):
                lines.append("#KODIPROP:inputstream.adaptive.license_type=clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={c['keyId']}:{c['key']}")

        lines.append(f"#EXTVLCOPT:http-user-agent={ANDROID_UA}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(f"#EXTVLCOPT:http-cookie={hdntl}")
        exthttp = json.dumps({"Origin": ORIGIN, "Referer": REFERER,
                              "User-Agent": ANDROID_UA, "Cookie": hdntl},
                             separators=(",", ":"))
        lines.append(f"#EXTHTTP:{exthttp}")
        lines.append(url)
        lines.append("")
    return lines


def main():
    # 1) Cloud worker (Browser Rendering) — self-mints without a residential IP.
    hdntl = get_token_from_worker()
    if hdntl:
        print("Got fresh hdntl from cloud worker (Browser Rendering)")
    else:
        # 2) Direct BFF mint — only works from a residential IP (home/dev box).
        print("Cloud worker unavailable -> trying direct BFF mint...")
        cj = load_cookie()
        hdntl = mint_hdntl(cj) if cj else None

    exp = token_expiry(hdntl)
    if not hdntl or exp <= time.time() + 900:
        # Hotstar's BFF is Akamai-bot-protected: datacenter/proxy egress gets a
        # 403, and the worker may be down.  If an earlier run already left a
        # fresh playlist, keep it rather than overwriting with a stale one.
        if os.path.exists(OUTPUT_M3U):
            with open(OUTPUT_M3U, encoding="utf-8") as f:
                existing = f.read()
            exps = [int(x) for x in re.findall(r"exp=(\d{10})", existing)]
            if exps and min(exps) > time.time() + 1800:
                print("No fresh hdntl minted here, but the existing playlist is still fresh -> leaving as-is")
                return 0
        print("No fresh hdntl token -> nothing written")
        return 1

    print(f"Fresh hdntl minted (expires {datetime.fromtimestamp(exp, IST):%d-%m-%Y %H:%M:%S IST})")
    lines = build_lines(hdntl)
    ch_count = sum(1 for l in lines if l.startswith("#EXTINF"))

    header = [
        "#EXTM3U",
        f"#DATE:- {datetime.now(IST):%d-%m-%Y %H:%M:%S IST}",
        "# Category: jiohotstar",
        f"# Total Channels: {ch_count}",
        "# Source: JioHotstar Self-Hosted (own account, self-minted hdntl)",
        f"# Token-Expires:- {datetime.fromtimestamp(exp, IST):%d-%m-%Y %H:%M:%S IST}",
        f"# Refresh-After:- {datetime.fromtimestamp(max(exp - 2 * 3600, time.time()), IST):%d-%m-%Y %H:%M:%S IST}",
        "",
    ]
    if ch_count < MIN_CHANNELS:
        print(f"Only {ch_count} channels built (need >= {MIN_CHANNELS}) -> aborting")
        return 1

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(header + lines).strip() + "\n")
    print(f"Generated {OUTPUT_M3U} ({ch_count} channels)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
