# 📡 Master Auto-Updated IPTV Playlists

Automated aggregator and generator for Indian and International Live TV & Sports streams. Auto-refreshes every 6 hours via GitHub Actions.

## 🔗 Playlists & Direct Raw Links

| Category / Provider | Channels Count | Direct Raw M3U Link |
| :--- | :--- | :--- |
| **⭐ Master Combined (Front Root)** | **~1,400+** | **`https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u`** |
| **⭐ JioHotstar** | 146 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiohotstar.m3u` |
| **📡 JioTV** | 1,175 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiotv.m3u` |
| **📺 SonyLIV** | 31+ | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sonyliv.m3u` |
| **🏏 FanCode** | Live Matches | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/fancode.m3u` |
| **🎬 VZY** | 48 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/vzy.m3u` |
| **🎥 Prime Video** | Live Sports | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/primevideo.m3u` |
| **🏏 Willow** | Live Cricket | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/willow.m3u` |

---

## 📁 Repository Structure
```
iptv-hub/
├── .github/
│   └── workflows/
│       └── update.yml      # Auto-refreshes every 6 hours
├── scripts/
│   ├── merge.py            # Master updater & aggregator
│   ├── generate_jiotv.py   # JioTV live M3U & ClearKey generator
│   ├── generate_sony.py    # SonyLIV live catalog & Akamai token generator
│   └── generate_zee5.py    # ZEE5 live linear & sports event generator
├── playlists/              # Individual provider playlists
│   ├── jiohotstar.m3u
│   ├── jiotv.m3u
│   ├── sonyliv.m3u
│   ├── fancode.m3u
│   ├── vzy.m3u
│   ├── primevideo.m3u
│   └── willow.m3u
├── Combined.m3u            # Master merged playlist in root
└── README.md
```

---

## ⏰ Auto-Refresh Schedule
- Automatically runs **every 6 hours** using GitHub Actions (`.github/workflows/update.yml`).
- Automatically updates dynamic `__hdnea__` tokens, live matches, upcoming fixtures, and ClearKeys.
