# 📡 Master Auto-Updated IPTV Playlists

Automated aggregator and generator for Live TV & Sports streams. Auto-refreshes every 5 hours via GitHub Actions.

## 🔗 Playlists & Direct Raw Links

| Category / Provider | Channels Count | Direct Raw M3U Link |
| :--- | :--- | :--- |
| **⭐ Master Combined (Front Root)** | **1,600+ Channels** | **`https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u`** |
| **⭐ JioHotstar (Independent Feed)** | 146 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiohotstar.m3u` |
| **📡 JioTV (Full Packs & Categories)** | 1,175 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiotv.m3u` |
| **📺 ZEE5 Worldwide** | 112 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/zee5.m3u` |
| **📺 SonyLIV** | 22 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sonyliv.m3u` |
| **☀️ SunNXT** | 33 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sunnxt.m3u` |
| **🎬 VZY (Independent, no auth)** | 48 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/vzy.m3u` |
| **👶 Kids (24/7 Kids, WOW KIDZ, Goldmines)** | 17 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/kids.m3u` |
| **🎭 Dangal Play** | 4 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/dangal.m3u` |
| **🏏 FanCode** | 5 (Live) | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/fancode.m3u` |
| **🏏 Willow** | Live Cricket | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/willow.m3u` |
| **🎥 Prime Video** | Live Sports | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/prime.m3u` |

---

## 🗂️ Channel catalogs (`catalogs/`)

Only **static** catalogs live here. The two live sources need no committed
catalog: their channel list is fetched on every run, and the published playlist
is the fallback if the upstream is down.

| File | Tracked? | Contents |
| :--- | :--- | :--- |
| `catalogs/sunnxt_catalog.json` | ✅ committed | 34 SunNXT channels — name, logo, Akamai MPD manifest URL, ClearKey |
| `catalogs/vzy_catalog.json` | ✅ committed | 48 VZY channels — name, logo, stream URL, ClearKey |

**Fetched live, not stored:**
- **JioTV** — 1,175 channels from the qwerty `Geoplus.json` list, every run.
- **SonyLIV** — 22 channels from the hub's `/sony/sliv3.json`, every run.

**Why the JioTV token is not committed:** the token lives ~6 h and is a
credential, so it is only ever written into `playlists/jiotv.m3u`. If no live
token can be fetched, the generator removes that playlist so `merge.py` falls
back to the public feed; if only the channel list is unreachable, the previous
playlist is kept.

## 🔐 How each source is authenticated

| Source | Token | Cookie | Independent? |
| :--- | :--- | :--- | :--- |
| **VZY** | ❌ none | ❌ none | ✅ **100%** — static ClearKey, plays bare, keys never rotate |
| **JioTV** | `__hdnea__` (6h) | ❌ | ⚠️ token minted by the **allinonereborn** hub (single source) |
| **FanCode** | `hdntl` (per match) | ❌ | ⚠️ token carried by the **doctor-8trange** feed |
| **SonyLIV** | `hdntl` (~22h) | ❌ | ⚠️ catalog **and** token minted by the **allinonereborn** hub (same upstream as JioTV) |
| **JioHotstar** | `hdntl` | ✅ own | ✅ **100%** — self-minted by the user's own worker |
| ZEE5 Worldwide / SunNXT / Dangal / Kids | varies | — | ❌ public feed |

> ZEE5 **India** is intentionally excluded: its ClearKey/DASH streams hang
> (measured 31 of 33 dead). Only the **Worldwide** half (112 channels) plays,
> so only that half is published.

A JioTV / FanCode / SonyLIV token **cannot** be derived from a cookie or an
algorithm — a hub holding a real login mints it. VZY and JioHotstar are the two
that are genuinely self-contained.

> ⚠️ The `allinonereborn` cookie (`jstrweb2/cookies.json`) is a **JioTV-only**
> token (`acl=/*`). It does nothing on Sony's CDN — verified: `403` with and
> without it. It is *not* a Sony auth source.

**How SonyLIV is minted instead:** from the hub's Sony catalog
`https://allinonereborn2.online/sony/sliv3.json` (22 channels). Of the hub's
three Sony catalogs, only `sliv3` is live — `sliv.json` and `sliv2.json` carry
inline `hdnea` tokens that **expired** in Dec 2025 / Feb 2026. Each `sliv3`
entry points at the hub's own playlist, which resolves to the real Sony CDN
with a **freshly minted ~22 h `hdntl`**:

```
our entry     https://allinonereborn2.online/sony-new/playlists/sony_hd.m3u8   (needs a Referer)
resolves to   https://dishmt.slivcdn.com/hls/live/2011671/SETHD/hdntl=exp=..~hmac=../master_108.m3u8
```

Our playlist therefore stores a **pointer, not a token** — the hub re-mints on
every fetch, so it can never go stale, and nothing sensitive is committed.
Verified: 22/22 playlists resolve, and playlist → variant → segment returns
~100 KB media segments.

## ⏰ Auto-Refresh Schedule
- Automatically runs **every 5 hours** using GitHub Actions (`.github/workflows/update.yml`).
  The JioTV and JioHotstar tokens live ~6 h, so a 5 h cycle keeps them fresh.
- Step order: `generate_jiotv.py` → `generate_vzy.py` → `generate_fancode.py` → `generate_sony.py` → `merge.py`.
- A generator failure is non-fatal: SonyLIV and the JioTV catalog step keep the previous playlist; if no live JioTV token is available, `playlists/jiotv.m3u` is removed so `merge.py` falls back to the public feed.
- Automatically updates stream tokens, live matches, upcoming fixtures, and manifest URLs.
