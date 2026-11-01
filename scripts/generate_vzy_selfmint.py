#!/usr/bin/env python3
"""
Dish/Zee live-channel playlist — FULL SELF-MINT (no upstream, no baked keys).

Enumerates every DTH linear channel from the Kaltura channel collection, then
self-mints the Widevine (Dish Nagra) keys for the DRM channels and passes the FTA
channels straight through. Keys rotate, so every run re-mints fresh keys.

Flow per DRM channel:
  Kaltura channel list (KalturaChannelFilter, miniEPGCollectionId) -> externalId (HE_E_...)
  externalId -> content-auth-token -> Nagra license -> content key (KID:KEY)
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
sys.path.insert(0, os.path.join(ROOT, "wv-extract"))

import requests  # noqa: E402

from vzy import get_keys as mint_keys  # noqa: E402
from vzy import kaltura_session, kaltura_external_id  # noqa: E402

OUT = os.path.join(ROOT, "playlists", "vzy.m3u")
CHANNELS = os.path.join(ROOT, "catalogs", "dth_channels.json")
STATUS = os.path.join(ROOT, "catalogs", "vzy_status.json")

KALTURA_BASE = "https://5093.dsp1.ott.kaltura.com/api_v3"
MINI_EPG_COLLECTION_ID = 366800  # the Kaltura "channel" collection id

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
GROUP_LOGO = ("https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/"
              "entry_id/bab798478e714be3a5ae861fc04606f0/version/0")


def fetch_channels() -> list[dict]:
    """Enumerate the DTH linear channels (name + externalId + mpd/hls url + logo)."""
    ks = kaltura_session()
    rows = []
    page = 1
    while True:
        body = {
            "apiVersion": "11.2.0.1", "clientTag": "KSPAND-1.0.3(100)", "ks": ks,
            "filter": {"objectType": "KalturaChannelFilter", "idEqual": MINI_EPG_COLLECTION_ID},
            "pager": {"objectType": "KalturaFilterPager", "pageIndex": page, "pageSize": 500},
            "language": "en",
        }
        r = requests.post(f"{KALTURA_BASE}/service/asset/action/list",
                          headers={"User-Agent": UA, "Accept": "application/json",
                                   "Content-Type": "application/json"},
                          json=body, timeout=30)
        res = r.json().get("result", {})
        if "error" in res:
            raise RuntimeError(f"Kaltura channel list: {res['error'].get('message')}")
        objs = res.get("objects") or []
        for c in objs:
            if not isinstance(c, dict):
                continue
            dash_url = hls_url = None
            for mf in (c.get("mediaFiles") or []):
                t = (mf.get("type") or "").upper()
                u = mf.get("url") or ""
                if t == "DASH_WV":
                    dash_url = u
                elif t in ("HLS_FP", "HLS"):
                    hls_url = u
            logo = ""
            for img in (c.get("images") or []):
                if img.get("imageTypeName") == "16x9_Cover":
                    logo = img.get("url") or ""
                    break
            rows.append({
                "name": c.get("name") or "",
                "external_id": c.get("externalId") or "",
                "asset_id": c.get("id"),
                "dash_url": dash_url,
                "hls_url": hls_url,
                "logo": logo or GROUP_LOGO,
            })
        total = res.get("totalCount", 0)
        if not objs or page * 500 >= total:
            break
        page += 1
    return rows


def is_drm(ch) -> bool:
    """A channel is DRM if it has a DASH_WV url that is NOT the free-to-air variant."""
    return bool(ch.get("dash_url") and "/dash_fta/" not in ch["dash_url"])


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main() -> int:
    channels = fetch_channels()
    os.makedirs(os.path.dirname(CHANNELS), exist_ok=True)
    json.dump(channels, open(CHANNELS, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    minted = 0
    drm = 0
    fta = 0
    lines = ["#EXTM3U", ""]
    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")

    for c in channels:
        name = c["name"]
        logo = c["logo"] or GROUP_LOGO
        kid = key = ""
        url = None
        if is_drm(c):
            drm += 1
            try:
                keys = mint_keys(c["dash_url"], content_id=c["external_id"])
                if keys:
                    kid, key = next(iter(keys.items()))
                    minted += 1
            except Exception as e:  # noqa: BLE001
                print(f"  [!] {name}: {type(e).__name__}: {e}")
            url = c["dash_url"]
        else:
            fta += 1
            url = c["hls_url"] or c["dash_url"]

        if not url:
            continue
        cid = c["asset_id"] or slug(name)
        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'group-title="VZY",{name}'
        )
        if kid and key:
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={kid}:{key}")
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    header = [f"# VZY | self-minted {stamp} | {drm} DRM ({minted} minted) + {fta} FTA"]
    lines[1:1] = header
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")
    json.dump({"updated_at": stamp, "total": len(channels), "drm": drm,
               "minted": minted, "fta": fta},
              open(STATUS, "w", encoding="utf-8"), indent=2)
    print(f"VZY: {len(channels)} channels ({drm} DRM, {minted} minted, {fta} FTA) -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
