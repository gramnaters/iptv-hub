from datetime import datetime, timezone
from pathlib import Path
import json

CATALOG_PATH = Path(__file__).resolve().parent.parent / "catalogs" / "zee5_catalog.json"
PLAYLIST_PATH = Path(__file__).resolve().parent.parent / "playlists" / "zee5.m3u"
USER_AGENT = "com.graymatrix.did;Android TV;5.82.6(203230929);Android(10);Xiaomi(Redmi Note 8 Pro)"
BASE_STREAM_URL = "https://zee.gramnaters.workers.dev/live"

def generate_playlist():
    if not CATALOG_PATH.exists():
        print(f"Error: {CATALOG_PATH} not found.")
        return

    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        channels = json.load(f)

    timestamp = datetime.now(timezone.utc).strftime("%d-%m-%Y %H:%M:%S UTC")
    lines = [
        "#EXTM3U",
        f"# Generated: {timestamp}",
        f"# Total Channels: {len(channels)}",
        ""
    ]

    for ch in channels:
        cid = ch.get("id", "").strip()
        name = ch.get("name", "").strip()
        logo = ch.get("logo", "").strip()
        genre = ch.get("genre", "Entertainment").strip()
        group = ch.get("group", "ZEE5 India").strip()

        if not cid or not name:
            continue

        extinf = f'#EXTINF:-1 tvg-id="{cid}" tvg-name="{name}" tvg-logo="{logo}" tvg-category="{genre}" group-title="{group}",{name}'
        lines.append(extinf)
        lines.append(f'#EXTVLCOPT:http-user-agent={USER_AGENT}')
        lines.append(f'{BASE_STREAM_URL}/{cid}.m3u8')
        lines.append("")

    PLAYLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PLAYLIST_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    print(f"Successfully generated {PLAYLIST_PATH} with {len(channels)} channels.")

if __name__ == "__main__":
    generate_playlist()
