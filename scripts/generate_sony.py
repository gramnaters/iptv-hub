#!/usr/bin/env python3
import os
import re
import sys
import requests
from datetime import datetime, timezone, timedelta

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

IST = timezone(timedelta(hours=5, minutes=30))

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_M3U = os.path.join(ROOT_DIR, "playlists", "sonyliv.m3u")

SLIV_PLAYLIST = "https://sliv.gramnaters.workers.dev/playlist.m3u"
API_BASE = "https://apiv2.sonyliv.com"
CDN_BASE = "https://dishmt.slivcdn.com/hls/live"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

GROUP = "Sony LIV"
GROUP_LOGO = "https://upload.wikimedia.org/wikipedia/commons/f/f7/SonyLIV_2020.png"
MIN_CHANNELS = 5

CHANNELS = [
    ("sony-hd", "SONY HD", "Entertainment", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_HD.png", "2011671/SETHD"),
    ("sab-hd", "SAB HD", "Entertainment", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_SAB_HD.png", "2011749/SABHD"),
    ("sony-marathi", "SONY MARATHI", "Entertainment", "Marathi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_Marathi_SD.png", "2011740/SonyMarathi"),
    ("sony-pal", "SONY PAL", "Entertainment", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_Pal.png", "2011741/SonyPalSD"),
    ("sony-aath", "SONY AATH", "Entertainment", "Bengali", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_aath.png", "2011641/SonyAathSD"),
    ("sony-yay", "SONY YAY", "Kids", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_Yay_Hindi.png", "2011746/SonyYaySD"),
    ("sony-max-hd", "SONY MAX HD", "Movies", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_Max_HD.png", "2011670/SonyMaxhd"),
    ("sony-max", "SONY MAX", "Movies", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_Max_SD.png", "2011745/SonyMaxSD"),
    ("sony-max2", "SONY MAX2", "Movies", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_MAX2.png", "2011908/MAX2"),
    ("sony-wah", "SONY WAH", "Movies", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_Wah.png", "2011906/SonyWah"),
    ("sony-pix-hd", "SONY PIX HD", "Movies", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_Pix_HD.png", "2011748/PIXHD"),
    ("sony-ten-1-hd", "SONY TEN 1 HD", "Sports", "English", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten_HD.png", "2011747/TEN1HD"),
    ("sony-ten-1", "SONY TEN 1", "Sports", "English", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten_1.png", "2011739/TEN1SD"),
    ("sony-ten-2-hd", "SONY TEN 2 HD", "Sports", "English", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten2_HD.png", "2020434/TEN2HD"),
    ("sony-ten-2", "SONY TEN 2", "Sports", "English", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten2_HD.png", "2020590/TEN2SD"),
    ("sony-ten-3-hd", "SONY TEN 3 HD", "Sports", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten3_HD.png", "2020591/TEN3HD"),
    ("sony-ten-3", "SONY TEN 3", "Sports", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten3_HD.png", "2020592/TEN3SD"),
    ("sony-ten-4-hd", "SONY TEN 4 HD", "Sports", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten_4_HD_Telugu.png", "2020589/ten4hd"),
    ("sony-ten-4", "SONY TEN 4", "Sports", "Telugu", "https://jiotvimages.cdn.jio.com/dare_images/images/Ten_4_Telugu.png", "2020437/ten4sd"),
    ("sony-ten-5-hd", "SONY TEN 5 HD", "Sports", "Hindi", "https://jiotvimages.cdn.jio.com/dare_images/images/Six_HD.png", "2020593/SONYSIXHD"),
    ("sony-ten-5", "SONY TEN 5", "Sports", "English", "https://jiotvimages.cdn.jio.com/dare_images/images/Six_HD.png", "2020594/SONYSIXSD"),
    ("bbc-earth", "BBC EARTH", "Infotainment", "English", "https://jiotvimages.cdn.jio.com/dare_images/images/Sony_BBC_Earth_HD.png", "2011907/SonyBBCEarthHD"),
]


def mint_direct_token():
    try:
        r1 = requests.get(f"{API_BASE}/AGL/1.4/A/ENG/WEB/ALL/GETTOKEN", headers={"User-Agent": USER_AGENT}, timeout=15)
        jwt = r1.json().get("resultObj")
        if not jwt or not isinstance(jwt, str):
            return None
        r2 = requests.get(
            f"{API_BASE}/AGL/1.5/A/ENG/WEB/IN/CONTENT/VIDEOURL/VOD/1000022678",
            headers={"User-Agent": USER_AGENT, "security_token": jwt},
            timeout=15,
        )
        vurl = (r2.json().get("resultObj") or {}).get("videoURL") or ""
        m = re.search(r"[?&](hdnea=[^&]+)", vurl)
        return m.group(1) if m else None
    except Exception as e:
        print(f"  ⚠️ Direct mint error: {e}")
        return None


def generate_playlist():
    print(f"📡 Fetching SonyLIV playlist from {SLIV_PLAYLIST}...")
    text = ""
    try:
        r = requests.get(SLIV_PLAYLIST, timeout=20)
        if r.status_code == 200 and r.text.count("#EXTINF") >= MIN_CHANNELS:
            text = r.text
    except Exception as e:
        print(f"  ⚠️ Worker fetch error: {e}")

    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")

    if text and text.count("#EXTINF") >= MIN_CHANNELS:
        count = text.count("#EXTINF")
        body = []
        for line in text.splitlines():
            if line.startswith("#EXTM3U") or line.startswith("# Total") or line.startswith("# Source"):
                continue
            if line.startswith("#EXTINF"):
                line = re.sub(
                    r'group-title="[^"]*"',
                    f'group-title="{GROUP}" group-logo="{GROUP_LOGO}"',
                    line,
                )
            body.append(line)

        lines = [
            "#EXTM3U",
            f"#DATE:- {now_ist}",
            "# Category: sonyliv",
            f"# Total Channels: {count}",
            f"# Source: {SLIV_PLAYLIST}",
            "",
        ] + body
    else:
        print("  🔑 Fetching direct Sony API wildcard token...")
        token = mint_direct_token()
        if not token:
            print("  ❌ Direct token mint failed; keeping existing playlist")
            return False

        lines = [
            "#EXTM3U",
            f"#DATE:- {now_ist}",
            "# Category: sonyliv",
            f"# Total Channels: {len(CHANNELS)}",
            "# Source: SonyLIV Direct API",
            "",
        ]
        for cid, name, cat, lang, logo, path in CHANNELS:
            extinf = f'#EXTINF:-1 tvg-id="{cid}.sonyliv" tvg-name="{name}" tvg-logo="{logo}" tvg-language="{lang}" tvg-category="{cat}" group-title="{GROUP}" group-logo="{GROUP_LOGO}",{name}'
            lines.append(extinf)
            lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
            lines.append(f"{CDN_BASE}/{path}/master.m3u8?{token}")
            lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    ch_count = open(OUTPUT_M3U, "r", encoding="utf-8").read().count("#EXTINF")
    print(f"✅ Generated {OUTPUT_M3U} ({ch_count} SonyLIV channels)")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate_playlist() else 1)
