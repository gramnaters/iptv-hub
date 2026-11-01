#!/usr/bin/env python3
"""
Zee5 live-channel generator — FULL self-host (no premiumplug, no baked keys).

Two paths:
  1. Premium linear (Zee TV/Cinema/Bangla...) -> Dish Nagra self-mint (vzy.py)
  2. FAST + News + Temple + international -> singlePlayback(channel_id) -> fresh
     stream URL (hdnts token) -> serve directly

Catalog: gwapi.zee5.com/v1/channel (free, no auth). Keys/URLs rotate, so each run
re-fetches fresh tokens.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PARENT = os.path.dirname(ROOT)
sys.path.insert(0, os.path.join(_PARENT, "wv-extract"))

import requests  # noqa: E402

OUT = os.path.join(ROOT, "playlists", "zee5_live.m3u")
STATUS = os.path.join(ROOT, "catalogs", "zee5_live_status.json")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
CHANNEL_API = "https://gwapi.zee5.com/v1/channel"
SP_URL = "https://spapi.zee5.com/singlePlayback/v2/getDetails/secure"

# Platform token for singlePlayback. The singlePlayback endpoint validates the
# JWT's *signature* (HMAC), not its expiry, so this token stays valid as long as
# Zee5's signing secret is unchanged. It is still refreshed on each run when
# possible (see refresh_platform_token). Override with env ZEE5_PLATFORM_TOKEN.
_DEFAULT_PLATFORM_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwbGF0Zm9ybV9jb2RlIjoiV2ViQCQhdDM4NzEy"
    "IiwiaXNzdWVkQXQiOiIyMDI1LTEwLTIyVDAzOjQ4OjA1LjAyOVoiLCJwcm9kdWN0X2NvZGUiOiJ6"
    "ZWU1QDk3NSIsInR0bCI6ODY0MDAwMDAsImlhdCI6MTc2MTEwNDg4NX0."
    "8HnOYX7GmvGGWWiPfYPlvJk55Bzmjd1qEQIx6ueOnCs"
)


def refresh_platform_token() -> str:
    """Try to fetch a fresh platform token; fall back to the known-good one.

    The old token-endpoint (useraction.zee5.com/token/platform_tokens.php) is
    currently 404, so this is best-effort: env var > fresh fetch > default.
    """
    env = os.environ.get("ZEE5_PLATFORM_TOKEN", "").strip()
    if env:
        return env
    for base in ("https://useraction.zee5.com", "https://useraction-crm.zee5.com"):
        for pn in ("desktop_web", "android_app"):
            try:
                r = requests.get(f"{base}/token/platform_tokens.php?platform_name={pn}",
                                 headers={"User-Agent": UA, "Accept": "text/plain"}, timeout=10)
                if r.status_code == 200 and r.text.strip().startswith("eyJ"):
                    return r.text.strip()
            except Exception:
                pass
    return _DEFAULT_PLATFORM_TOKEN


PLATFORM_TOKEN = refresh_platform_token()


def fetch_channels() -> list[dict]:
    out = []
    seen = set()
    for country in ("IN", "US", "GB", "AE", "AU", "SG", "CA", "NZ"):
        page = 1
        while True:
            try:
                r = requests.get(CHANNEL_API, params={"sort_by_field": "title", "page": str(page),
                                                      "page_size": "200", "genres": "", "languages": "",
                                                      "country": country, "translation": "en"},
                                 headers={"User-Agent": UA, "Accept": "application/json"}, timeout=20)
                d = r.json()
                items = d.get("items", [])
                for it in items:
                    cid = it.get("id")
                    if cid and cid not in seen:
                        seen.add(cid)
                        it["_country"] = country
                        out.append(it)
                if page * 200 >= d.get("total", 0) or not items:
                    break
                page += 1
            except Exception:
                break
    return out


def _proxies() -> list[str]:
    return [l.strip() for l in (os.environ.get("PROXY_LIST", "").splitlines())
            if l.strip().startswith("http")]


def single_playback(channel_id: str, guest: str, country: str = "IN") -> dict:
    p = {"channel_id": channel_id, "device_id": guest, "platform_name": "desktop_web",
         "translation": "en", "user_language": "en,hi", "country": country, "state": "",
         "app_version": "4.24.0", "check_parental_control": "false"}
    proxies = _proxies()
    # try direct first, then rotate through proxies (GitHub Actions IPs are often blocked)
    for attempt in range(len(proxies) + 1):
        px = None if attempt == 0 else {"http": proxies[attempt - 1], "https": proxies[attempt - 1]}
        try:
            r = requests.post(SP_URL, params=p,
                              headers={"User-Agent": UA, "Accept": "application/json",
                                       "Content-Type": "application/json",
                                       "Origin": "https://www.zee5.com", "Referer": "https://www.zee5.com/"},
                              json={"x-access-token": PLATFORM_TOKEN, "X-Z5-Guest-Token": guest},
                              proxies=px, timeout=20)
            d = r.json()
            if "assetDetails" in d:
                return d
        except Exception:
            continue
    return {}


def main() -> int:
    channels = fetch_channels()
    guest = str(uuid.uuid4())

    lines = ["#EXTM3U", ""]
    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    ok = 0
    free = 0
    premium = 0
    failed = 0

    for c in channels:
        name = c["title"]
        cid = c["id"]
        biz = c.get("business_type", "")
        country = c.get("_country", "IN")
        logo = ""  # leave logo empty; channel list has image fragments, not full urls

        if biz == "premium":
            premium += 1
            continue  # covered by the Dish Nagra generator (India) / needs subscription (intl)

        try:
            d = single_playback(cid, guest, country)
            s = json.dumps(d)
            m = re.search(r'https?://[^\s"\'\\]+?\.m3u8[^\s"\'\\]*', s)
            if not m:
                failed += 1
                continue
            url = m.group(0)
            ok += 1
            lines.append(f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" group-title="ZEE5 Live",{name}')
            lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
            lines.append(url)
            lines.append("")
        except Exception:
            failed += 1

    lines[1:1] = [f"# ZEE5 live | self-host {stamp} | {ok} free/FAST + {premium} premium (Dish Nagra) + {failed} failed"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    json.dump({"updated_at": stamp, "total": len(channels), "free": ok,
               "premium": premium, "failed": failed},
              open(STATUS, "w", encoding="utf-8"), indent=2)
    print(f"ZEE5 live: {len(channels)} channels -> {ok} free self-host + {premium} premium + {failed} failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
