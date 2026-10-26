#!/usr/bin/env python3
"""
VZY live TV playlist generator.
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "vzy_catalog.json")
STATUS = os.path.join(ROOT, "catalogs", "vzy_status.json")
OUT = os.path.join(ROOT, "playlists", "vzy.m3u")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")
GROUP_LOGO = "https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/entry_id/bab798478e714be3a5ae861fc04606f0/version/0"
KEY_RE = re.compile(r"#EXT-X-KEY:METHOD=([A-Z0-9-]+)")


def hls_variants(url):
    """Candidate clear-HLS URLs for a catalog entry."""
    if "/live/media/" not in url:
        return []
    base = url.split("/live/media/")[1].split("/")[0]
    root = f"https://d2o8pibksxtln6.cloudfront.net/live/media/{base}"
    if url.endswith(".m3u8"):
        return [url]
    return [f"{root}/hls_fta/{base}.m3u8", f"{root}/hls/{base}.m3u8"]


def probe(url):
    """Return (playable_url, reason). Playable means no EXT-X-KEY in the variant."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
    except Exception:
        return None, "unreachable"
    if r.status_code != 200 or "#EXTM3U" not in r.text:
        return None, "missing"

    subs = [l.strip() for l in r.text.splitlines()
            if l.strip() and not l.startswith("#") and ".m3u8" in l]
    if not subs:
        return None, "no variants"

    sub = subs[0]
    if not sub.startswith("http"):
        sub = url.rsplit("/", 1)[0] + "/" + sub
    try:
        v = requests.get(sub, headers={"User-Agent": UA}, timeout=15)
    except Exception:
        return None, "unreachable"
    if v.status_code != 200:
        return None, "variant error"
    keys = KEY_RE.findall(v.text)
    if keys:
        return None, "drm:" + ",".join(sorted(set(keys)))
    return url, "clear"


def resolve(ch):
    reason = "missing"
    for url in hls_variants(ch.get("url", "")):
        good, reason = probe(url)
        if good:
            return ch, good, "clear"
    return ch, None, reason


def main():
    if not os.path.exists(CATALOG):
        print(f"missing catalog: {CATALOG}")
        return 1
    with open(CATALOG, encoding="utf-8") as f:
        channels = json.load(f)

    print(f"VZY: {len(channels)} channels")
    results = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        for ch, url, state in ex.map(resolve, channels):
            results.append((ch, url, state))

    playable = [(c, u) for c, u, _ in results if u]
    states = {}
    for _, _, s in results:
        states[s] = states.get(s, 0) + 1
    print(f"  playable: {len(playable)}/{len(channels)}  " + ", ".join(f"{k}={v}" for k, v in sorted(states.items())))

    if len(playable) < 5:
        print("  too few channels, keeping previous playlist")
        return 1

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {stamp}",
        f"# Total Channels: {len(playable)}",
        "",
    ]
    for ch, url in playable:
        name = ch.get("name", "")
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch.get("id","")}" tvg-name="{name}" tvg-logo="{ch.get("logo","")}" '
            f'tvg-category="{ch.get("group","VZY")}" group-title="VZY" group-logo="{GROUP_LOGO}",{name}'
        )
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    drm = [c["name"] for c, u, s in results if not u and s.startswith("drm")]
    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({"updated_at": stamp, "playable": len(playable),
                   "states": states, "drm_only": drm}, f, indent=2, ensure_ascii=False)

    print(f"  wrote {OUT} ({len(playable)} clear HLS, {len(drm)} DRM-only)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
