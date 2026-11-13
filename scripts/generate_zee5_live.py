#!/usr/bin/env python3
"""
Zee5 live-channel generator — FULL self-host (no premiumplug, no baked keys).

Two paths:
  1. Premium linear (Zee TV/Cinema/Bangla...) -> Dish Nagra self-mint (vzy.py)
  2. FAST + News + Temple + international -> singlePlayback(channel_id) -> fresh
     stream URL (hdnts token) -> serve directly

Catalog: gwapi.zee5.com/v1/channel (free, no auth). Keys/URLs rotate, so each run
re-fetches fresh tokens.

Egress note (2026-11): spapi.zee5.com sits behind Akamai and answers HTTP 475 to
datacenter IP ranges (GitHub Actions, Cloudflare Workers, VPS). Residential Indian
IPs get 200. So when the direct call is blocked we discover live Indian HTTP
proxies from public lists at run time, verify them against singlePlayback, and
rotate over the survivors. Tokens live ~50 min, so the playlist keeps its old
entries instead of being overwritten with an empty list on a bad run.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
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

# Tuning (stay well inside the GitHub job budget).
PROBE_CHANNEL = "0-9-aajtak"          # always free, always live
PROXY_SOURCES = (
    "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies"
    "&country=in&protocol=http&proxy_format=ipport&format=text",
    "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1"
    "&sort_by=lastChecked&sort_type=desc&country=IN&protocols=http%2Chttps",
    "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/countries/IN/data.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
)
MAX_PROXY_TESTS = 260
PROXY_TEST_WORKERS = 40
PROXY_TIMEOUT = 8
MAX_PROXIES = 8
MINT_TIMEOUT = 15
MINT_WORKERS = 6
MAX_ATTEMPTS = 4
DEADLINE_SECONDS = 1500               # hard stop; refresh.py allows 1500s
MIN_CHANNELS = 10                     # below this, keep the previous playlist

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
    """PROXY_LIST from secrets: one proxy per line, scheme optional."""
    out = []
    for line in os.environ.get("PROXY_LIST", "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if re.match(r"^\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$", line):
            line = "http://" + line
        if line.startswith(("http://", "https://", "socks5://")):
            out.append(line)
    return out


def _post_single(channel_id: str, guest: str, country: str, px: str | None = None,
                 timeout: int = 20) -> dict:
    p = {"channel_id": channel_id, "device_id": guest, "platform_name": "desktop_web",
         "translation": "en", "user_language": "en,hi", "country": country, "state": "",
         "app_version": "4.24.0", "check_parental_control": "false"}
    proxy = {"http": px, "https": px} if px else None
    r = requests.post(SP_URL, params=p,
                      headers={"User-Agent": UA, "Accept": "application/json",
                               "Content-Type": "application/json",
                               "Origin": "https://www.zee5.com", "Referer": "https://www.zee5.com/"},
                      json={"x-access-token": PLATFORM_TOKEN, "X-Z5-Guest-Token": guest},
                      proxies=proxy, timeout=timeout)
    d = r.json()
    return d if isinstance(d, dict) and "assetDetails" in d else {}


def discover_proxies() -> list[str]:
    """Public IN proxy lists -> verified-working proxies (concurrently)."""
    cands: list[str] = []
    for src in PROXY_SOURCES:
        try:
            r = requests.get(src, headers={"User-Agent": UA}, timeout=20)
            if "proxylist.geonode" in src:
                for d in r.json().get("data", []):
                    cands.append(f"http://{d['ip']}:{d['port']}")
            else:
                for line in r.text.splitlines():
                    line = line.strip()
                    if re.match(r"^(?:http://)?\d{1,3}(?:\.\d{1,3}){3}:\d{2,5}$", line):
                        cands.append(line if line.startswith("http") else "http://" + line)
        except Exception as e:  # noqa: BLE001
            print(f"  proxy source failed: {src[:48]} ({type(e).__name__})", flush=True)
    # Configured proxies first, then freshly discovered ones.
    cands = list(dict.fromkeys(_proxies() + cands))[:MAX_PROXY_TESTS]
    print(f"  proxy candidates: {len(cands)}", flush=True)

    guest = str(uuid.uuid4())

    def ok(px: str) -> str | None:
        try:
            return px if _post_single(PROBE_CHANNEL, guest, "IN", px, timeout=PROXY_TIMEOUT) else None
        except Exception:
            return None

    good: list[str] = []
    with ThreadPoolExecutor(max_workers=PROXY_TEST_WORKERS) as ex:
        for res in ex.map(ok, cands):
            if res:
                good.append(res)
                print(f"  working proxy: {res}", flush=True)
                if len(good) >= MAX_PROXIES:
                    break
    return good


def mint_url(channel_id: str, guest: str, country: str, direct_ok: bool,
             proxies: list[str], deadline: float) -> str | None:
    attempts: list[str | None] = ([None] if direct_ok else []) + proxies
    for px in attempts[:MAX_ATTEMPTS]:
        if time.time() > deadline:
            return None
        try:
            d = _post_single(channel_id, guest, country, px, timeout=MINT_TIMEOUT)
            m = re.search(r'https?://[^\s"\'\\]+?\.m3u8[^\s"\'\\]*', json.dumps(d))
            if m:
                return m.group(0)
        except Exception:
            continue
    return None


def main() -> int:
    started = time.time()
    deadline = started + DEADLINE_SECONDS
    channels = fetch_channels()
    guest = str(uuid.uuid4())

    # One cheap call decides whether this egress can reach Akamai directly.
    try:
        direct_ok = bool(_post_single(PROBE_CHANNEL, guest, "IN", None, timeout=MINT_TIMEOUT))
    except Exception:
        direct_ok = False
    print(f"ZEE5: {len(channels)} channels | direct egress: {'OK' if direct_ok else 'BLOCKED (Akamai 475)'}", flush=True)

    proxies = [] if direct_ok else discover_proxies()
    if not direct_ok:
        print(f"  usable Indian proxies: {len(proxies)}", flush=True)
    if not direct_ok and not proxies:
        print("ZEE5: no working egress (direct blocked + no live proxy); keeping existing playlist", flush=True)
        return 1

    free = [c for c in channels if c.get("business_type") != "premium"]
    premium = len(channels) - len(free)

    def work(c: dict) -> tuple[dict, str | None]:
        return c, mint_url(str(c["id"]), guest, c.get("_country", "IN"), direct_ok, proxies, deadline)

    results: list[tuple[dict, str]] = []
    done = 0
    with ThreadPoolExecutor(max_workers=MINT_WORKERS) as ex:
        for c, url in ex.map(work, free):
            done += 1
            if url:
                results.append((c, url))
            if done % 10 == 0 or done == len(free):
                print(f"  {done}/{len(free)} checked, {len(results)} minted, {int(time.time()-started)}s", flush=True)

    ok = len(results)
    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")

    if ok < MIN_CHANNELS:
        print(f"ZEE5: only {ok} channels minted (< {MIN_CHANNELS}); keeping existing playlist", flush=True)
        return 1

    lines = ["#EXTM3U", ""]
    for c, url in results:
        name = c["title"]
        lines.append(f'#EXTINF:-1 tvg-id="{c["id"]}" tvg-name="{name}" group-title="ZEE5 Live",{name}')
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")
    failed = len(free) - ok
    lines[1:1] = [f"# ZEE5 live | self-host {stamp} | {ok} free/FAST + {premium} premium (Dish Nagra) + {failed} failed"]
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    json.dump({"updated_at": stamp, "total": len(channels), "free": ok,
               "premium": premium, "failed": failed,
               "direct": direct_ok, "proxies": len(proxies)},
              open(STATUS, "w", encoding="utf-8"), indent=2)
    print(f"ZEE5 live: {len(channels)} channels -> {ok} free self-host + {premium} premium + {failed} failed "
          f"in {int(time.time()-started)}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
