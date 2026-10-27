#!/usr/bin/env python3
"""
SonyLIV playlist generator with Linear 24/7 Channels and Native Live Sports Events.
Directly extracts live events and mints official Akamai/DAI tokens from SonyLIV's APIs.
"""
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

SLIV_PLAYLIST = os.environ.get("SLIV_URL", "")
API_BASE = "https://apiv2.sonyliv.com"
CDN_BASE = "https://dishmt.slivcdn.com/hls/live"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
SONY_REFERER = "https://www.sonyliv.com/"

GROUP = "Sony LIV"
EVENTS_GROUP = "Sonyliv events"
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

TRAY_URLS = [
    "https://apiv3.sonyliv.com/AGL/4.9/R/ENG/WEB/IN/HR/TRAY/EXTCOLLECTION/224516?layout=spotlight_layout&from=0&to=20",
    "https://apiv3.sonyliv.com/AGL/4.9/R/ENG/WEB/IN/HR/TRAY/EXTCOLLECTION/3937924064?layout=portrait_layout&from=0&to=20"
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


def fetch_live_events_native():
    """Directly fetch active SonyLIV live sports events and mint official tokens."""
    events = []
    seen = set()

    headers = {
        "User-Agent": USER_AGENT,
        "app_version": "3.6.86",
        "Referer": SONY_REFERER,
        "Origin": "https://www.sonyliv.com",
        "Content-Type": "application/json"
    }

    raw_candidates = []
    for tray_url in TRAY_URLS:
        try:
            r = requests.get(tray_url, headers={"User-Agent": USER_AGENT, "app_version": "3.6.86", "Referer": SONY_REFERER}, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for c in data.get("resultObj", {}).get("containers", []):
                    meta = c.get("metadata", {})
                    cid = meta.get("contentId")
                    if cid and meta.get("isLive") and cid not in seen:
                        seen.add(cid)
                        raw_candidates.append({
                            "id": str(cid),
                            "title": meta.get("title") or "Live Sports",
                            "tournament": meta.get("seo_title") or meta.get("title") or "SonyLIV Sports",
                            "thumb": meta.get("emfAttributes", {}).get("landscape_thumb") or meta.get("emfAttributes", {}).get("thumbnail") or GROUP_LOGO
                        })
        except Exception as e:
            print(f"  ⚠️ SonyLIV tray fetch error: {e}")

    print(f"  Found {len(raw_candidates)} live sports candidates in SonyLIV spotlight trays")

    for cand in raw_candidates:
        cid = cand["id"]
        title = cand["title"]
        prev_url = f"{API_BASE}/AGL/5.0/R/ENG/WEB/IN/UP/CONTENT/VIDEOURL/VOD/{cid}/freepreview?contactId=1359193139"
        payload = {
            "actionType": "play",
            "browser": "Chrome",
            "deviceId": "3ad207c151e544d0a899f8b20caf15d4-1785671326584",
            "os": "Windows",
            "platform": "web",
            "hasLAURLEnabled": True,
            "adsParams": {"Idtype": "uuid", "Is_lat": "0", "ppid": "44023a12a37c7644c4341eb7941bfbc6", "preroll": "disable"}
        }

        try:
            pr = requests.post(prev_url, json=payload, headers=headers, timeout=12)
            if pr.status_code == 200:
                res_obj = pr.json().get("resultObj", {})
                vurl = res_obj.get("videoURL")
                dai_key = res_obj.get("dai_asset_key")
                stream_url = vurl
                if not stream_url and dai_key:
                    stream_url = f"https://dai.google.com/linear/hls/event/{dai_key}/master.m3u8"

                if not stream_url:
                    continue

                # Quick verification of stream manifest
                try:
                    vr = requests.get(stream_url, headers={"User-Agent": USER_AGENT, "Referer": SONY_REFERER}, timeout=8)
                    if vr.status_code != 200:
                        print(f"  ⚠️ Stream verification returned HTTP {vr.status_code} for {cid}")
                        continue
                except Exception as ve:
                    print(f"  ⚠️ Stream verification failed for {cid}: {ve}")
                    continue

                langs = [l.get("audioLanguageName") for l in res_obj.get("audioLanguages", []) if l.get("audioLanguageName")]
                lang_str = ", ".join(langs) if langs else "English"

                events.append({
                    "id": cid,
                    "name": title,
                    "event_name": cand["tournament"],
                    "category": "Sports",
                    "lang": lang_str,
                    "logo": cand["thumb"],
                    "url": stream_url
                })
                print(f"  ✓ Minted native stream for [{cid}] {title}")
        except Exception as ex:
            print(f"  ⚠️ Error minting token for [{cid}]: {ex}")

    return events


def generate_playlist():
    print("📡 Fetching SonyLIV linear playlist...")
    linear_lines = []
    try:
        r = requests.get(SLIV_PLAYLIST, timeout=20) if SLIV_PLAYLIST else None
        if r is None:
            raise RuntimeError("SLIV_URL not set")
        if r.status_code == 200 and r.text.count("#EXTINF") >= MIN_CHANNELS:
            for line in r.text.splitlines():
                if line.startswith("#EXTM3U") or line.startswith("# Total") or line.startswith("# Source") or line.startswith("#DATE"):
                    continue
                if line.startswith("#EXTINF"):
                    line = re.sub(
                        r'group-title="[^"]*"',
                        f'group-title="{GROUP}" group-logo="{GROUP_LOGO}"',
                        line,
                    )
                linear_lines.append(line)
    except Exception as e:
        print(f"  ⚠️ Worker fetch error: {e}")

    if not linear_lines:
        print("  🔑 Fetching direct Sony API wildcard token...")
        token = mint_direct_token()
        if token:
            for cid, name, cat, lang, logo, path in CHANNELS:
                extinf = f'#EXTINF:-1 tvg-id="{cid}.sonyliv" tvg-name="{name}" tvg-logo="{logo}" tvg-language="{lang}" tvg-category="{cat}" group-title="{GROUP}" group-logo="{GROUP_LOGO}",{name}'
                linear_lines.append(extinf)
                linear_lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
                linear_lines.append(f"{CDN_BASE}/{path}/master.m3u8?{token}")
                linear_lines.append("")

    # Fetch dynamic live sports events natively
    print("📡 Fetching active SonyLIV live sports events natively...")
    live_events = fetch_live_events_native()
    print(f"  Total verified native live events: {len(live_events)}")

    event_lines = []
    if live_events:
        event_lines.append("# --- SonyLIV Live Sports Events ---")
        for ev in live_events:
            tid = f"sonyliv.event.{ev['id']}"
            name = ev["name"]
            logo = ev["logo"]
            lang = ev["lang"]
            cat = ev["category"]
            url = ev["url"]

            extinf = (
                f'#EXTINF:-1 tvg-id="{tid}" tvg-name="{name}" tvg-logo="{logo}" '
                f'tvg-language="{lang}" tvg-category="{cat}" group-title="{EVENTS_GROUP}" group-logo="{GROUP_LOGO}",{name}'
            )
            event_lines.append(extinf)
            event_lines.append(f"#EXTVLCOPT:http-user-agent={USER_AGENT}")
            event_lines.append(f"#EXTVLCOPT:http-referrer={SONY_REFERER}")
            event_lines.append(url)
            event_lines.append("")

    now_ist = datetime.now(IST).strftime("%d-%m-%Y %H:%M:%S IST")
    total_count = (len(linear_lines) // 3) + len(live_events)

    lines = [
        "#EXTM3U",
        f"#DATE:- {now_ist}",
        "# Category: sonyliv",
        f"# Total Channels: {total_count}",
        f"# Source: SonyLIV Self-Hosted (Linear + Live Events)",
        "",
    ] + linear_lines + ([""] if event_lines else []) + event_lines

    os.makedirs(os.path.dirname(OUTPUT_M3U), exist_ok=True)
    with open(OUTPUT_M3U, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    ch_count = open(OUTPUT_M3U, "r", encoding="utf-8").read().count("#EXTINF")
    print(f"Generated {OUTPUT_M3U} ({ch_count} total channels: {ch_count - len(live_events)} linear + {len(live_events)} live events)")
    return True


if __name__ == "__main__":
    sys.exit(0 if generate_playlist() else 1)
