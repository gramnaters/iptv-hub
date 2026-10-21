#!/usr/bin/env python3
"""Build playlists/sonyliv.m3u by self-minting SonyLIV's wildcard hdnea token.

Sony's anonymous API mints a wildcard `hdnea` token (~12 h, acl=/*) for one
free title, and that token unlocks all 22 dishmt.slivcdn.com linear channels.
The token is minted here with two plain HTTP calls — no Cloudflare Worker or
Browser Rendering — because Sony only flags *Cloudflare's* fetch egress as a
VPN (`AKA_0403_PANIC`); GitHub Actions and any normal egress mint fine.

The token is baked into the playlist (like the JioTV/JioHotstar tokens) and is
refreshed every workflow run. If minting fails the previous playlist is kept,
so CI never publishes a broken SonyLIV block.
"""
import os
import re
import sys
import time
import requests
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

API = "https://apiv2.sonyliv.com"
CDN = "https://dishmt.slivcdn.com/hls/live"
DEFAULT_CONTENT_ID = "1000022678"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
GROUP = "Sony LIV"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png"
LOGO_BASE = "https://jiotvimages.cdn.jio.com/dare_images/images"

MIN_CHANNELS = 5

# (slug, name, category, language, logo-file, cdn-path) — same 22 as the worker
CHANNELS = [
    ("sony-hd",       "SONY HD",       "Entertainment", "Hindi",    "Sony_HD.png",          "2011671/SETHD"),
    ("sab-hd",        "SAB HD",        "Entertainment", "Hindi",    "Sony_SAB_HD.png",      "2011749/SABHD"),
    ("sony-marathi",  "SONY MARATHI",  "Entertainment", "Marathi",  "Sony_Marathi_SD.png",  "2011740/SonyMarathi"),
    ("sony-pal",      "SONY PAL",      "Movies",        "Hindi",    "Sony_Pal.png",         "2011741/SonyPalSD"),
    ("sony-aath",     "SONY AATH",     "Entertainment", "Bengali",  "Sony_aath.png",        "2011641/SonyAathSD"),
    ("sony-yay",      "SONY YAY",      "Kids",          "Hindi",    "Sony_Yay_Hindi.png",   "2011746/SonyYaySD"),
    ("sony-max-hd",   "SONY MAX HD",   "Movies",        "Hindi",    "Sony_Max_HD.png",      "2011670/SonyMaxhd"),
    ("sony-max",      "SONY MAX",      "Movies",        "Hindi",    "Sony_Max_SD.png",      "2011745/SonyMaxSD"),
    ("sony-max2",     "SONY MAX2",     "Movies",        "Hindi",    "Sony_MAX2.png",        "2011908/MAX2"),
    ("sony-wah",      "SONY WAH",      "Movies",        "Hindi",    "Sony_Wah.png",         "2011906/SonyWah"),
    ("sony-pix-hd",   "SONY PIX HD",   "Movies",        "Hindi",    "Sony_Pix_HD.png",      "2011748/PIXHD"),
    ("sony-ten-1-hd", "SONY TEN 1 HD", "Sports",        "English",  "Ten_HD.png",           "2011747/TEN1HD"),
    ("sony-ten-1",    "SONY TEN 1",    "Sports",        "English",  "Ten_1.png",            "2011739/TEN1SD"),
    ("sony-ten-2-hd", "SONY TEN 2 HD", "Sports",        "English",  "Ten2_HD.png",          "2020434/TEN2HD"),
    ("sony-ten-2",    "SONY TEN 2",    "Sports",        "English",  "Ten2_HD.png",          "2020590/TEN2SD"),
    ("sony-ten-3-hd", "SONY TEN 3 HD", "Sports",        "Hindi",    "Ten3_HD.png",          "2020591/TEN3HD"),
    ("sony-ten-3",    "SONY TEN 3",    "Sports",        "Hindi",    "Ten3_HD.png",          "2020592/TEN3SD"),
    ("sony-ten-4-hd", "SONY TEN 4 HD", "Sports",        "Hindi",    "Ten_4_HD_Telugu.png",  "2020589/ten4hd"),
    ("sony-ten-4",    "SONY TEN 4",    "Sports",        "Telugu",   "Ten_4_Telugu.png",     "2020437/ten4sd"),
    ("sony-ten-5-hd", "SONY TEN 5 HD", "Sports",        "Hindi",    "Six_HD.png",           "2020593/SONYSIXHD"),
    ("sony-ten-5",    "SONY TEN 5",    "Sports",        "English",  "Six_HD.png",           "2020594/SONYSIXSD"),
    ("bbc-earth",     "BBC EARTH",     "Infotainment",  "English",  "Sony_BBC_Earth_HD.png", "2011907/SonyBBCEarthHD"),
]


def _expiry_hours(token):
    m = re.search(r"exp=(\d+)", token or "")
    if not m:
        return -1.0
    return (int(m.group(1)) - int(time.time())) / 3600.0


def mint_token():
    """Mint a wildcard hdnea token via Sony's anonymous API.

    Returns the token string ("hdnea=...") or "" on failure.
    """
    print("🔑 Minting SonyLIV hdnea token (anonymous API)...")
    try:
        r = requests.get(
            f"{API}/AGL/1.4/A/ENG/WEB/ALL/GETTOKEN",
            headers={"User-Agent": USER_AGENT},
            timeout=20,
        )
        r.raise_for_status()
        jwt = r.json().get("resultObj")
        if not jwt or not isinstance(jwt, str):
            print("❌ GETTOKEN returned no security_token")
            return ""
    except Exception as e:
        print(f"❌ GETTOKEN failed: {e}")
        return ""

    try:
        r2 = requests.get(
            f"{API}/AGL/1.5/A/ENG/WEB/IN/CONTENT/VIDEOURL/VOD/{DEFAULT_CONTENT_ID}",
            headers={"User-Agent": USER_AGENT, "security_token": jwt},
            timeout=20,
        )
        r2.raise_for_status()
        video_url = (r2.json().get("resultObj") or {}).get("videoURL") or ""
    except Exception as e:
        print(f"❌ VIDEOURL failed: {e}")
        return ""

    m = re.search(r"[?&](hdnea=[^&]+)", video_url)
    if not m:
        print("❌ VIDEOURL returned no hdnea token")
        return ""
    token = m.group(1)
    print(f"✅ Minted token ({_expiry_hours(token):.1f} h left, acl=/*)")
    return token


def build_channels(token):
    """Return channel dicts with direct CDN URLs carrying the token."""
    return [
        {
            "id": slug,
            "name": name,
            "logo": f"{LOGO_BASE}/{logo_file}",
            "category": category,
            "language": lang,
            "group": GROUP,
            "url": f"{CDN}/{path}/master.m3u8?{token}",
        }
        for slug, name, category, lang, logo_file, path in CHANNELS
    ]


def probe(url, timeout=15):
    """(ok, detail) - fetch a CDN master with the minted token."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if r.status_code == 200 and r.text.lstrip().startswith("#EXTM3U"):
            return True, "200"
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, type(e).__name__


def generate_sony_playlist(verify=True):
    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    token = mint_token()
    if not token:
        print("   keeping the existing playlist")
        return False

    channels = build_channels(token)
    if not channels:
        print("❌ No channels - keeping the existing playlist")
        return False

    live, dead, why = channels, [], []
    if verify:
        live, dead, why = [], [], []
        for ch in channels:
            ok, detail = probe(ch["url"])
            if ok:
                live.append(ch)
            else:
                dead.append(ch["name"])
                why.append(detail)

    if verify and len(live) < MIN_CHANNELS:
        # A datacenter IP (GitHub Actions) can be refused by the CDN even when
        # a real ISP client streams fine. Publish the full catalog instead of
        # pruning channels we could not verify from here.
        print(f"⚠️ Only {len(live)}/{len(channels)} responded ({', '.join(sorted(set(why))[:4]) or 'n/a'})")
        print("⚠️ Treating this as 'verification unavailable here', NOT as dead channels")
        live = list(channels)
        dead = []

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: sonyliv",
        f"# Total Channels: {len(live)}",
        "# Source: self-minted via Sony anonymous API (GETTOKEN -> VIDEOURL -> hdnea)",
        "",
    ]

    for ch in live:
        lines.append(
            f'#EXTINF:-1 tvg-id="{ch.get("id", "")}" tvg-name="{ch.get("name", "")}" '
            f'tvg-logo="{ch.get("logo", "")}" tvg-category="{ch.get("category", "")}" '
            f'tvg-language="{ch.get("language", "")}" group-title="{ch.get("group") or GROUP}" '
            f'group-logo="{GROUP_LOGO}",{ch.get("name", "")}'
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
