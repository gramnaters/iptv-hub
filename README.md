# 📡 Master Auto-Updated IPTV Playlists

Automated aggregator and generator for Live TV & Sports streams. Auto-refreshes every 24 hours via GitHub Actions.

## 🔗 Playlists & Direct Raw Links

| Category / Provider | Channels Count | Direct Raw M3U Link |
| :--- | :--- | :--- |
| **⭐ Master Combined (Front Root)** | **1,600+ Channels** | **`https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u`** |
| **⭐ JioHotstar (Independent Feed)** | 146 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiohotstar.m3u` |
| **📡 JioTV (Full Packs & Categories)** | 1,175 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiotv.m3u` |
| **📺 ZEE5 (India & Worldwide)** | 145 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/zee5.m3u` |
| **📺 SonyLIV** | 26+ | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sonyliv.m3u` |
| **☀️ SunNXT** | 33 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sunnxt.m3u` |
| **🎬 VZY (Independent, no auth)** | 48 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/vzy.m3u` |
| **👶 Kids (24/7 Kids, WOW KIDZ, Goldmines)** | 17 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/kids.m3u` |
| **🎭 Dangal Play** | 4 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/dangal.m3u` |
| **🏏 FanCode** | 5 (Live) | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/fancode.m3u` |
| **🏏 Willow** | Live Cricket | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/willow.m3u` |
| **🎥 Prime Video** | Live Sports | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/prime.m3u` |

---

## 🗂️ Channel catalogs (`channels/`)

Every generated/injected JSON lives in **`channels/`** at the repo root, one file
per source. Generators read from here; merge.py reads the resulting playlists.

| File | Written by | Contents |
| :--- | :--- | :--- |
| `channels/vzy_catalog.json` | *(baked, static)* | 48 VZY channels — name, logo, stream URL, ClearKey |
| `channels/jiotv_catalog.json` | `generate_jiotv.py` | JioTV channel catalog cache (1,175 channels) |
| `channels/jiotv_cookie.json` | `generate_jiotv.py` | Harvested `__hdnea__` token + source + timestamp |
| `channels/zee5_catalog.json` | *(baked, static)* | 145 ZEE5 channels with ClearKeys |

## 🔐 How each source is authenticated

| Source | Token | Cookie | Independent? |
| :--- | :--- | :--- | :--- |
| **VZY** | ❌ none | ❌ none | ✅ **100%** — static ClearKey, plays bare, keys never rotate |
| **JioTV** | `__hdnea__` (6h) | ❌ | ⚠️ token minted by the **allinonereborn** hub (single source) |
| **FanCode** | `hdntl` (per match) | ❌ | ⚠️ token carried by the **doctor-8trange** feed |
| **JioHotstar** | `hdntl` (24h) | ✅ own | ✅ **100%** — self-minted by the user's own worker |
| ZEE5 / SunNXT / SonyLIV / Dangal / Kids | varies | — | ❌ public feed |

A JioTV / FanCode token **cannot** be derived from a cookie or an algorithm — a
hub holding a real login mints it. VZY and JioHotstar are the two that are
genuinely self-contained.

## ⏰ Auto-Refresh Schedule
- Automatically runs **every 24 hours** using GitHub Actions (`.github/workflows/update.yml`).
- Step order: `generate_jiotv.py` → `generate_vzy.py` → `generate_fancode.py` → `merge.py`.
- A generator failure is non-fatal: `merge.py` falls back to the public feed for that category.
- Automatically updates stream tokens, live matches, upcoming fixtures, and manifest URLs.
