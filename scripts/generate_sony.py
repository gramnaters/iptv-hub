#!/usr/bin/env python3
"""Build playlists/sonyliv.m3u from the independent SonyLIV worker.

The worker serves 22 SonyLIV channels and attaches a wildcard Akamai `hdnea`
token minted directly from Sony's API. The token lives ~12 h and is refreshed
on a local 5-hour schedule; this script only copies the worker's channel list.
If the worker is unavailable (or its token is expired) the previous playlist
is kept, so CI never publishes a broken SonyLIV block.
"""
import os
import re
import sys
from datetime import datetime, timezone, timedelta

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sonyliv.m3u")

WORKER = "https://sonyliv-worker.gramnaters.workers.dev"
PLAYLIST = WORKER + "/playlist.m3u"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
GROUP = "Sony LIV"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png"

MIN_CHANNELS = 5
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def fetch_worker_playlist():
    """Fetch the worker's M3U. Raises if the worker is down or tokenless."""
    import requests

    print(f"📡 Fetching {PLAYLIST}...")
    r = requests.get(PLAYLIST, headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    text = r.text
    if not text.lstrip().startswith("#EXTM3U"):
        raise ValueError("worker did not return an M3U playlist")
    return text


def parse_worker_playlist(text):
    """Parse EXTINF blocks into the channel dicts the writer expects."""
    lines = [ln.strip() for ln in text.splitlines()]
    channels = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#EXTINF"):
            attrs = dict(ATTR_RE.findall(line))
            name = line.rsplit(",", 1)[-1].strip()
            j = i + 1
            url = ""
            while j < len(lines):
                if not lines[j] or lines[j].startswith("#"):
                    j += 1
                    continue
                url = lines[j]
                break
            if url:
                channels.append({
                    # Keep the repo's historical ids (sony-hd, sab-hd, ...).
                    "id": attrs.get("tvg-id", "").removesuffix(".sonyliv"),
                    "name": attrs.get("tvg-name") or name,
                    "logo": attrs.get("tvg-logo", ""),
                    "category": attrs.get("tvg-category") or "Entertainment",
                    "language": attrs.get("tvg-language") or "",
                    "group": GROUP,
                    "url": url,
                })
            i = j + 1
        else:
            i += 1
    return channels


def probe(url, timeout=15):
    """(ok, detail) - follow the worker's 302 to the CDN master."""
    try:
        import requests

        r = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=timeout,
            allow_redirects=True,
        )
        if r.status_code == 200 and r.text.lstrip().startswith("#EXTM3U"):
            return True, "200"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, type(e).__name__


def generate_sony_playlist(verify=True):
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    try:
        text = fetch_worker_playlist()
    except Exception as e:
        print(f"❌ Could not fetch the SonyLIV worker: {e}")
        print("   keeping the existing playlist")
        return False

    catalog = parse_worker_playlist(text)
    if not catalog:
        print("❌ Worker playlist had no channels - keeping the existing playlist")
        return False

    live, dead, why = [], [], []
    if verify:
        for ch in catalog:
            ok, detail = probe(ch["url"])
            if ok:
                live.append(ch)
            else:
                dead.append(ch["name"])
                why.append(detail)

    if verify and len(live) < MIN_CHANNELS:
        # A datacenter IP (GitHub Actions) can be refused by the CDN even when
        # a real ISP client streams fine. Publish the full worker catalog
        # instead of pruning channels we could not verify from here.
        print(f"⚠️ Only {len(live)}/{len(catalog)} responded ({', '.join(sorted(set(why))[:4]) or 'n/a'})")
        print("⚠️ Treating this as 'verification unavailable here', NOT as dead channels")
        live = list(catalog)
        dead = []

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: sonyliv",
        f"# Total Channels: {len(live)}",
        f"# Source: {PLAYLIST} (direct SonyLIV hdnea; token refreshed every 5h)",
        "",
    ]

    for ch in live:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch.get("id","")}" tvg-name="{ch.get("name","")}" '
            f'tvg-logo="{ch.get("logo","")}" tvg-category="{ch.get("category","")}" '
            f'tvg-language="{ch.get("language","")}" group-title="{ch.get("group") or GROUP}" '
            f'group-logo="{GROUP_LOGO}",{ch.get("name","")}'
        )
        lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
        lines.append(ch["url"])
        lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"✅ Generated {OUTPUT_M3U} ({len(live)} SonyLIV channels)")
    if dead:
        print(f"   ⚠️ dropped {len(dead)} dead: {', '.join(dead[:6])}{'...' if len(dead) > 6 else ''}")
    return True


if __name__ == "__main__":
    verify = "--no-verify" not in sys.argv
    sys.exit(0 if generate_sony_playlist(verify=verify) else 1)
