#!/usr/bin/env python3
"""
zee5.py — ZEE5 Widevine key extractor (VOD + own-CDN live).

PROVEN flow (verified end-to-end against a real ZEE5 title, key matches the
publicly known value):

  1. singlePlayback  POST spapi.zee5.com/singlePlayback/getDetails/secure
                     ?content_id=<id>&device_id=<uuid>&platform_name=desktop_web
                     &translation=en&user_language=en,hi&country=IN&state=
                     &app_version=4.24.0&user_type=guest&check_parental_control=false
                     body: {"x-access-token": <platform JWT>,
                            "X-Z5-Guest-Token": <uuid>}
                     -> assetDetails.video_url.mpd   (DRM manifest)
                     -> keyOsDetails.sdrm            ("Nagra_<hex>" -> customdata header)
                     -> keyOsDetails.nl              (<hex> -> nl header)
  2. fetch MPD -> Widevine PSSH + default_KID
  3. license       POST spapi.zee5.com/widevine/getLicense
                     headers: customdata=<sdrm>, nl=<nl>, Content-Type octet-stream
                     body:   CDM license challenge
  4. parse_license -> content key  {kid: key}

For premium titles pass user_type=premium + a real x-access-token (the guest
token 401s on premium). The premium LIVE channels are served from Dish's
Broadpeak CDN (no PSSH in the MPD) and use Dish's Nagra license server instead —
see vzy.py / the README for that path.
"""

from __future__ import annotations

import json
import os
import sys
import uuid

import requests

from mpd import parse_mpd
from wv import extract as wv_extract

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36")

LICENSE_URL = "https://spapi.zee5.com/widevine/getLicense"
SINGLEPLAYBACK = "https://spapi.zee5.com/singlePlayback/v2/getDetails/secure"

# Public guest platform JWT (same credential the web player uses, no login).
PLATFORM_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwbGF0Zm9ybV9jb2RlIjoiV2ViQCQhdDM4NzEy"
    "IiwiaXNzdWVkQXQiOiIyMDI1LTEwLTIyVDAzOjQ4OjA1LjAyOVoiLCJwcm9kdWN0X2NvZGUiOiJ6"
    "ZWU1QDk3NSIsInR0bCI6ODY0MDAwMDAsImlhdCI6MTc2MTEwNDg4NX0."
    "8HnOYX7GmvGGWWiPfYPlvJk55Bzmjd1qEQIx6ueOnCs"
)


def single_playback(content_id: str, token: str = "", user_type: str = "guest") -> dict:
    """Return the singlePlayback JSON for a content id."""
    g = str(uuid.uuid4())
    url = (
        f"{SINGLEPLAYBACK}?content_id={content_id}&device_id={g}"
        "&platform_name=desktop_web&translation=en&user_language=en,hi"
        f"&country=IN&state=&app_version=4.24.0&user_type={user_type}"
        "&check_parental_control=false"
    )
    r = requests.post(
        url,
        headers={
            "User-Agent": UA, "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://www.zee5.com", "Referer": "https://www.zee5.com/",
        },
        json={"x-access-token": token or PLATFORM_TOKEN, "X-Z5-Guest-Token": g},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def get_keys(content_id: str, token: str = "", user_type: str = "guest",
             wvd_dir: str | None = None) -> dict:
    """Extract the content key for a ZEE5 content id. Returns {kid: key}."""
    d = single_playback(content_id, token, user_type)

    osd = d.get("keyOsDetails") or {}
    sdrm = osd.get("sdrm") or ""
    nl = osd.get("nl") or ""

    mpd_url = ((d.get("assetDetails") or {}).get("video_url") or {}).get("mpd")
    if not mpd_url:
        raise RuntimeError(f"no DRM manifest for content {content_id}")

    mpd = requests.get(mpd_url, headers={"User-Agent": UA}, timeout=20).text
    meta = parse_mpd(mpd)
    if not meta["pssh"]:
        raise RuntimeError(f"no Widevine PSSH in {mpd_url}")

    headers = {
        "User-Agent": UA,
        "customdata": sdrm,
        "nl": nl,
        "Content-Type": "application/octet-stream",
        "Origin": "https://www.zee5.com",
        "Referer": "https://www.zee5.com/",
    }
    kwargs = {"headers": headers}
    if wvd_dir:
        kwargs["wvd_dir"] = wvd_dir
    return wv_extract(meta["pssh"], LICENSE_URL, **kwargs)


def _main(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="ZEE5 Widevine key extractor")
    ap.add_argument("content_id", help="ZEE5 content id (e.g. 0-0-230188)")
    ap.add_argument("--token", default="", help="x-access-token (premium login)")
    ap.add_argument("--user-type", default="guest", help="guest | premium")
    ap.add_argument("--wvd-dir", default=None, help="directory of .wvd files")
    ap.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)

    try:
        keys = get_keys(args.content_id, args.token, args.user_type, args.wvd_dir)
    except Exception as e:  # noqa: BLE001
        print(f"[-] {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(keys, indent=2))
    else:
        for kid, key in keys.items():
            print(f"{kid}:{key}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
