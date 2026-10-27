# 📡 Master Auto-Updated IPTV Hub

Automated aggregator and stream engine for Live TV & Sports. Runs 100% autonomously in the cloud via **Cloudflare Workers** and **GitHub Actions** (every 4 hours). Zero local PC uptime required.

---

## ⚡ Primary Cloudflare Edge Endpoints (For OTT Navigator / TiviMate / Kodi)

| Endpoint | Description | Status |
| :--- | :--- | :--- |
| **`https://live.gramnaters.workers.dev`** | **⭐ Master Aggregated Playlist (1,600+ Channels)** | 🟢 24/7 Edge Cached & Self-Healing |
| **`https://jtv.gramnaters.workers.dev/playlist.m3u`** | **📡 JioTV Playlist (1,200+ Channels with ClearKeys, per-channel tokens from premiumplugx feed)** | 🟢 Rebuilt every 5 min · `/status` for token health |
| **`https://jhs.gramnaters.workers.dev/playlist.m3u`** | **⭐ JioHotstar Live TV (146 Channels)** | 🟢 Headless Browser Self-Minted |

---

## 🔗 Direct Repository Raw M3U Links

| Category / Provider | Channels | Direct Raw M3U Link |
| :--- | :--- | :--- |
| **⭐ Master Combined** | 1,600+ | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u` |
| **⭐ JioHotstar** | 146 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiohotstar.m3u` |
| **📡 JioTV (Full)** | 1,175 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiotv.m3u` |
| **📺 ZEE5 Worldwide** | 118 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/zee5.m3u` |
| **📺 SonyLIV** | 26+ | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sonyliv.m3u` |
| **☀️ SunNXT** | 33 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sunnxt.m3u` |
| **🎬 VZY (Independent)** | 48 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/vzy.m3u` |
| **👶 Kids 24/7** | 17 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/kids.m3u` |
| **🎭 Dangal Play** | 4 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/dangal.m3u` |
| **🏏 FanCode** | 5 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/fancode.m3u` |
| **🏏 Willow Cricket** | Live | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/willow.m3u` |
| **🎥 Prime Video** | Live | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/prime.m3u` |

---

## 🛠️ Architecture

Automated updates are scheduled every 4 hours via GitHub Actions (`.github/workflows/update.yml`), keeping playlist sources and tokens refreshed autonomously in the cloud without requiring local PC uptime.
