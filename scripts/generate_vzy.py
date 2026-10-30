#!/usr/bin/env python3
"""
Self-key VZY playlist generator (no upstream dependency).

VZY (Dish TV) live channels are static ClearKey. The keys are stable, but the
KID rotates occasionally — so this generator re-reads the CURRENT KID from each
DASH manifest and matches the key by KID. If the KID changed (key rotated), the
channel is emitted with an empty key and flagged, never an old key on a new KID.

Layers:
  * channel seed (name/slug/group/logo/type/kid/key) -> catalogs/vzy_seed.json
  * KID  -> read live from each channel's DASH MPD
  * KEY  -> static, matched by KID from the seed

IP-safe (CloudFront manifests are not geo-gated), so it runs on GitHub Actions.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
    HAS_REQ = True
except ImportError:
    HAS_REQ = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEED = os.path.join(ROOT, "catalogs", "vzy_seed.json")
OUT = os.path.join(ROOT, "playlists", "vzy.m3u")
STATUS = os.path.join(ROOT, "catalogs", "vzy_status.json")

CDN_BASE = "https://d2o8pibksxtln6.cloudfront.net/live/media"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
GROUP_LOGO = ("https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/"
              "entry_id/bab798478e714be3a5ae861fc04606f0/version/0")


def esc(s):
    return (s or "").replace('"', " ").replace("\r", "").replace("\n", "").strip()


def extract_kid(manifest):
    m = re.search(r'(?:cenc:)?default_KID="([0-9a-fA-F-]{32,36})"', manifest)
    return m.group(1).replace("-", "").lower() if m else ""


def fetch_kid(slug):
    """Return the current KID for a DRM channel, or '' on failure."""
    url = f"{CDN_BASE}/{slug}/dash/{slug}.mpd"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        if r.status_code != 200:
            return ""
        return extract_kid(r.text)
    except Exception:
        return ""


def main():
    seed = json.load(open(SEED, encoding="utf-8"))

    # read live KIDs in parallel (DRM channels only)
    slugs = [(s["slug"], s.get("kid", "").lower()) for s in seed
             if s.get("type") == "dash" and s.get("slug")]
    live_kid = {}
    if HAS_REQ:
        with ThreadPoolExecutor(16) as ex:
            results = ex.map(lambda p: (p[0], fetch_kid(p[0])), slugs)
            for slug, kid in results:
                if kid:
                    live_kid[slug] = kid

    lines = ["#EXTM3U",
             f"# VZY self-key | generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
             f"# Total Channels: {len(seed)}", ""]

    drm = stale = missing = 0
    for s in seed:
        name = esc(s["name"])
        slug = s.get("slug", "")
        grp = esc(s.get("group"))
        logo = esc(s.get("logo")) or GROUP_LOGO
        typ = s.get("type", "hls")
        kid = (s.get("kid") or "").lower()
        key = (s.get("key") or "").lower()

        if not slug:
            continue

        if typ == "dash":
            url = f"{CDN_BASE}/{slug}/dash/{slug}.mpd"
            cur_kid = live_kid.get(slug, kid)  # fall back to seed kid if fetch failed
            # key validity: only attach key if the current KID is the one we have a key for
            if key and cur_kid == kid:
                drm += 1
            elif key and cur_kid != kid:
                stale += 1
                key = ""  # KID rotated -> don't attach an old key
            elif not key:
                missing += 1
            lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" '
                         f'tvg-category="{grp}" group-title="VZY" type="dash",{name}')
            if key:
                lines.append("#KODIPROP:inputstream=inputstream.adaptive")
                lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
                lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
                lines.append(f"#KODIPROP:inputstream.adaptive.license_key={cur_kid}:{key}")
        else:
            url = f"{CDN_BASE}/{slug}/hls_fta/{slug}.m3u8"
            lines.append(f'#EXTINF:-1 tvg-name="{name}" tvg-logo="{logo}" '
                         f'tvg-category="{grp}" group-title="VZY",{name}')

        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")

    with open(STATUS, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "total": len(seed), "drm": drm, "stale": stale, "missing": missing,
            "live_kid": len(live_kid), "source": "self-key",
        }, f, indent=2)

    print(f"VZY: wrote {OUT} ({len(seed)} ch, {drm} DRM, {stale} stale, {missing} missing, "
          f"{len(live_kid)} live KIDs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
