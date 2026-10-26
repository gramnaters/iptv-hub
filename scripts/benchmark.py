#!/usr/bin/env python3
"""
Stream and playlist validation test suite.
"""
import os
import sys
import re
import time
import requests

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAYLISTS_DIR = os.path.join(ROOT_DIR, "playlists")


def parse_m3u_summary(filepath):
    if not os.path.exists(filepath):
        return {"exists": False, "count": 0, "size_kb": 0, "has_clearkey": False}
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    count = len(re.findall(r'#EXTINF:', text))
    has_clearkey = "license_key=" in text
    return {
        "exists": True,
        "count": count,
        "size_kb": len(text) // 1024,
        "has_clearkey": has_clearkey,
    }


def test_http_url(url, headers=None, timeout=8):
    start = time.time()
    try:
        r = requests.get(
            url,
            headers=headers or {"User-Agent": "Mozilla/5.0"},
            timeout=timeout,
            stream=True
        )
        elapsed = (time.time() - start) * 1000
        content_sample = next(r.iter_content(1024), b'')
        return {
            "status": r.status_code,
            "elapsed_ms": int(elapsed),
            "bytes_peek": len(content_sample),
            "ok": r.status_code in [200, 206]
        }
    except Exception as e:
        return {
            "status": 0,
            "elapsed_ms": int((time.time() - start) * 1000),
            "error": str(e),
            "ok": False
        }


def run_benchmark():
    print("--- Playlist File Audit ---")
    playlists = [
        ("Combined.m3u", os.path.join(ROOT_DIR, "Combined.m3u")),
        ("jiotv.m3u", os.path.join(PLAYLISTS_DIR, "jiotv.m3u")),
        ("jiohotstar.m3u", os.path.join(PLAYLISTS_DIR, "jiohotstar.m3u")),
        ("zee5.m3u", os.path.join(PLAYLISTS_DIR, "zee5.m3u")),
        ("sonyliv.m3u", os.path.join(PLAYLISTS_DIR, "sonyliv.m3u")),
        ("sunnxt.m3u", os.path.join(PLAYLISTS_DIR, "sunnxt.m3u")),
        ("vzy.m3u", os.path.join(PLAYLISTS_DIR, "vzy.m3u")),
        ("fancode.m3u", os.path.join(PLAYLISTS_DIR, "fancode.m3u")),
        ("kids.m3u", os.path.join(PLAYLISTS_DIR, "kids.m3u")),
        ("dangal.m3u", os.path.join(PLAYLISTS_DIR, "dangal.m3u")),
        ("free.m3u", os.path.join(PLAYLISTS_DIR, "free.m3u")),
    ]

    for name, p in playlists:
        info = parse_m3u_summary(p)
        if info["exists"]:
            ck = "ClearKey" if info["has_clearkey"] else "Plain"
            print(f"  {name:<20} : {info['count']:>4} channels | {info['size_kb']:>4} KB | {ck}")
        else:
            print(f"  {name:<20} : NOT FOUND")

    print("\n--- Stream Availability Check ---")
    sample_tests = [
        ("VZY", "https://d2o8pibksxtln6.cloudfront.net/live/media/9X_Jalwa/hls_fta/9X_Jalwa.m3u8", "Mozilla/5.0"),
        ("SunNXT", "https://livestream1.sunnxt.com/05b5df1221764bca9867054c5e65ee62/SunTVB_IN_index.mpd", "plaYtv/7.1.5"),
        ("SonyLIV", "https://sliv.gramnaters.workers.dev/sony-hd.m3u8", "Mozilla/5.0"),
    ]

    for provider, url, ua in sample_tests:
        res = test_http_url(url, headers={"User-Agent": ua})
        status_tag = "OK" if res["ok"] else "FAIL"
        print(f"  {provider:<12} [{status_tag}] HTTP {res['status']} ({res['elapsed_ms']}ms)")


if __name__ == "__main__":
    run_benchmark()
