# 📡 Master Auto-Updated IPTV Playlists

Automated aggregator and generator for Indian and International Live TV & Sports streams. Auto-refreshes every 6 hours via GitHub Actions.

## 🔗 Playlists & Direct Raw Links

| Category / Provider | Channels Count | Direct Raw M3U Link |
| :--- | :--- | :--- |
| **⭐ Master Combined** | **~1,400+** | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/Combined.m3u` |
| **⭐ JioHotstar** | 146 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiohotstar.m3u` |
| **📡 JioTV** | 1,175 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiotv.m3u` |
| **📺 SonyLIV** | 31+ | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sonyliv.m3u` |
| **🏏 FanCode** | Live Matches | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/fancode.m3u` |
| **🎬 VZY** | 48 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/vzy.m3u` |
| **🎥 Prime Video** | Live Sports | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/primevideo.m3u` |
| **🏏 Willow** | Live Cricket | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/willow.m3u` |

---

## 🛠️ Included Standalone Generator Scripts
- `build_playlists.py`: Master aggregator that queries all upstream sources and builds `playlists/Combined.m3u`.
- `generate_jiotv.py`: Standalone JioTV generator (`data/jiotv.json`, `data/jiotv.m3u`).
- `generate_sony.py`: Standalone SonyLIV generator (`data/sony.json`, `data/sony.m3u`).
- `generate_zee5.py`: Standalone ZEE5 generator (`data/zee5.json`, `data/zee5.m3u`).

---

## ⏰ Auto-Refresh Schedule
- Automatically runs **every 6 hours** using GitHub Actions (`.github/workflows/update.yml`).
- Automatically updates dynamic `__hdnea__` tokens, live matches, upcoming fixtures, and ClearKeys.
