# iptv-hub

```
https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u
```

| Playlist | File |
|---|---|
| JioTV | `playlists/jiotv.m3u` |
| JioHotstar | `playlists/jiohotstar.m3u` |
| SonyLIV | `playlists/sonyliv.m3u` |
| ZEE5 | `playlists/zee5.m3u` |
| VZY | `playlists/vzy.m3u` |
| FanCode | `playlists/fancode.m3u` |
| SunNXT | `playlists/sunnxt.m3u` |
| Free | `playlists/free.m3u` |

Refresh times: `catalogs/schedule.json`.

```
python scripts/refresh.py            # refresh whatever is due
python scripts/refresh.py --force    # refresh everything
python scripts/refresh.py --only vzy
```
