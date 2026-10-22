# 📡 Master Auto-Updated IPTV Playlists

Live TV & Sports, auto-refreshed every 5 hours via GitHub Actions.

## Playlists

| Category | Channels | Link |
| :--- | :--- | :--- |
| **Master Combined** | 1,456 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u` |
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

JioTV and ZEE5 come from the plugx public feed, and JioHotstar from the `jhs` worker; all are fetched live each run and folded into the combined playlist.
