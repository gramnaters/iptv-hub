# 📡 Master Auto-Updated IPTV Playlists

Live TV & Sports, auto-refreshed every 5 hours via GitHub Actions.

## Playlists

| Category | Channels | Link |
| :--- | :--- | :--- |
| **Master Combined** | 1,456 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u` |
| JioHotstar | 146 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiohotstar.m3u` |
| ZEE5 Worldwide | 112 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/zee5.m3u` |
| SonyLIV | 22 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sonyliv.m3u` |
| SunNXT | 34 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sunnxt.m3u` |
| VZY | 48 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/vzy.m3u` |
| Kids | 17 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/kids.m3u` |
| Dangal Play | 4 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/dangal.m3u` |
| FanCode | live | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/fancode.m3u` |
| Willow | live | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/willow.m3u` |
| Prime Video | live | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/prime.m3u` |

## Channel catalogs

`catalogs/*.json` — static channel lists read by the generators.

| File | Channels |
| :--- | :--- |
| `sonyliv_catalog.json` | 22 |
| `sunnxt_catalog.json` | 34 |
| `vzy_catalog.json` | 48 |

JioTV (1,209) and JioHotstar (146) are fetched live each run and folded into the combined playlist.
