#!/usr/bin/env python3
"""
VZY playlist — fetch current ClearKey keys from the upstream VZY API.

The VZY live keys are static ClearKey but ROTATE occasionally, and the key itself
cannot be derived from public data (it's the Dish/Nagra content key). So the only
self-hostable path is to pull the current key table from the upstream API (which
stays current) and fall back to a local seed if it's down.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import requests
    from Crypto.Cipher import AES
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = os.path.join(ROOT, "catalogs", "vzy_catalog.json")
SEED = os.path.join(ROOT, "catalogs", "vzy_seed.json")
STATUS = os.path.join(ROOT, "catalogs", "vzy_status.json")
OUT = os.path.join(ROOT, "playlists", "vzy.m3u")

UPSTREAMS = [
    "https://vzyweb.42web.io/api.php",
    "https://premiumplugx.web.id/api.php",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
GROUP_LOGO = ("https://imagesv2.dsp1.ott.kaltura.com/Service.svc/GetImage/p/5093/"
              "entry_id/bab798478e714be3a5ae861fc04606f0/version/0")


def solve_challenge(url):
    """Solve the InfinityFree AES cookie wall and return the channel list."""
    if not HAS_DEPS:
        return None
    s = requests.Session()
    s.headers["User-Agent"] = UA
    s.verify = False
    import urllib3
    urllib3.disable_warnings()
    try:
        r = s.get(url, timeout=20)
        nums = re.findall(r'toNumbers\("([0-9a-fA-F]{32})"\)', r.text)
        if len(nums) < 3:
            return None
        key, iv, ct = (bytes.fromhex(x) for x in nums[:3])
        cookie = AES.new(key, AES.MODE_CBC, iv).decrypt(ct).hex()
        s.headers["Cookie"] = f"__test={cookie}"
        r2 = s.get(url + "?i=1", timeout=20)
        if r2.status_code == 200:
            d = r2.json()
            if isinstance(d, list) and len(d) >= 10:
                return d
    except Exception:
        pass
    return None


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def main():
    channels = None
    source = "seed"

    for up in UPSTREAMS:
        data = solve_challenge(up)
        if data:
            channels = data
            source = up
            break

    if channels is None:
        # fallback to cached catalog / seed
        if os.path.exists(CATALOG):
            channels = json.load(open(CATALOG, encoding="utf-8"))
            source = "cached catalog"
        elif os.path.exists(SEED):
            channels = json.load(open(SEED, encoding="utf-8"))
            source = "seed"
        else:
            print("VZY: no upstream and no seed available")
            return 1

    # normalize to the 7-field schema
    rows = []
    for i, item in enumerate(channels):
        if not isinstance(item, dict):
            continue
        name = item.get("name") or "VZY Channel"
        grp = item.get("group") or "Entertainment"
        logo = item.get("logo") or GROUP_LOGO
        url = item.get("url") or ""
        kid = (item.get("kid") or "").lower()
        key = (item.get("key") or "").lower()
        typ = item.get("type") or ("dash" if ".mpd" in url.lower() else "hls")
        cid = item.get("id") or slug(name) or str(i + 1)
        if not url:
            continue
        rows.append({
            "id": str(cid), "name": name, "group": grp, "logo": logo,
            "url": url, "kid": kid, "key": key, "type": typ,
        })

    # persist catalog for fallback
    os.makedirs(os.path.dirname(CATALOG), exist_ok=True)
    json.dump(rows, open(CATALOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    stamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = ["#EXTM3U",
             f"# VZY | generated {stamp}",
             f"# Total Channels: {len(rows)}", ""]

    dash = 0
    for c in rows:
        name = c["name"]
        grp = c["group"]
        logo = c["logo"]
        url = c["url"]
        key = c["key"]
        cid = c["id"]
        is_dash = ".mpd" in url.lower()
        type_attr = ' type="dash"' if is_dash else ""

        lines.append(
            f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" '
            f'tvg-category="{grp}" group-title="VZY" group-logo="{GROUP_LOGO}"'
            f'{type_attr},{name}'
        )
        if is_dash and key and c["kid"]:
            dash += 1
            lines.append("#KODIPROP:inputstream=inputstream.adaptive")
            lines.append("#KODIPROP:inputstream.adaptive.manifest_type=mpd")
            lines.append("#KODIPROP:inputstream.adaptive.license_type=org.w3.clearkey")
            lines.append(f"#KODIPROP:inputstream.adaptive.license_key={c['kid']}:{key}")
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)
        lines.append("")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(lines).rstrip() + "\n")

    json.dump({"updated_at": stamp, "total": len(rows), "dash": dash,
               "hls": len(rows) - dash, "source": source},
              open(STATUS, "w", encoding="utf-8"), indent=2)

    print(f"VZY: {len(rows)} channels ({dash} DRM) from {source} -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
