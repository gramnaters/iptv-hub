# 📡 Master Auto-Updated IPTV Playlists

Automated aggregator and generator for Live TV & Sports streams. Auto-refreshes every 5 hours via GitHub Actions; SonyLIV self-mints its token from Sony's anonymous API on the same runner.

## 🔗 Playlists & Direct Raw Links

| Category / Provider | Channels Count | Direct Raw M3U Link |
| :--- | :--- | :--- |
| **⭐ Master Combined (Front Root)** | **1,570+ Channels** | **`https://raw.githubusercontent.com/gramnaters/iptv-hub/main/Combined.m3u`** |
| **⭐ JioHotstar (Independent Feed)** | 146 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiohotstar.m3u` |
| **📡 JioTV (Full Packs & Categories)** | 1,209 | *(folded into `Combined.m3u` as `Jio TV+ | …` groups)* |
| **📺 ZEE5 Worldwide** | 112 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/zee5.m3u` |
| **📺 SonyLIV** | 22 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sonyliv.m3u` |
| **☀️ SunNXT** | 34 | `https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/sunnxt.m3u` |
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
- **JioTV** — 1,209 channels taken straight from the plugx public feed (which
  carries fresh ClearKey DRM keys and the `__hdnea__` cookie), every run.
- **SonyLIV** — 22 channels self-minted from Sony's anonymous API (`GETTOKEN` → `VIDEOURL`), every run.

## 🔐 How each source is authenticated

| Source | Token | Cookie | Independent? |
| :--- | :--- | :--- | :--- |
| **VZY** | ❌ none | ❌ none | ✅ **100%** — static ClearKey, plays bare, keys never rotate |
| **JioTV** | `__hdnea__` (6h) | ❌ | ⚠️ token + ClearKey carried by the **plugx** public feed |
| **FanCode** | `hdntl` (per match) | ❌ | ⚠️ token carried by the **doctor-8trange** feed |
| **SonyLIV** | `hdnea` (~12h) | ❌ | ✅ **100%** — direct Sony anonymous-API token, self-minted on the GitHub runner |
| **JioHotstar** | `hdntl` | ✅ own | ✅ **100%** — self-minted by the user's own worker |
| ZEE5 Worldwide / SunNXT / Dangal / Kids | varies | — | ❌ public feed |

> ZEE5 **India** is intentionally excluded: its ClearKey/DASH streams hang
> (measured 31 of 33 dead). Only the **Worldwide** half (112 channels) plays,
> so only that half is published.

A JioTV / FanCode token **cannot** be derived from a cookie or an algorithm —
a hub holding a real login mints it. VZY, JioHotstar and SonyLIV are genuinely
self-contained. SonyLIV mints on the GitHub runner (Azure egress), which Sony
does not flag — only Cloudflare's fetch egress is blocked as a VPN.

> ⚠️ The JioTV `__hdnea__` cookie (`acl=/*`) is a **JioTV-only** token. It does
> nothing on Sony's CDN — verified: `403` with and without it. It is *not* a
> Sony auth source.

**How SonyLIV is minted (independent):** Sony's own anonymous API returns a
wildcard `hdnea` for one free title, minted directly by `generate_sony.py` on
the GitHub runner:

```
GET  apiv2.sonyliv.com/AGL/1.4/A/ENG/WEB/ALL/GETTOKEN
GET  apiv2.sonyliv.com/AGL/1.5/A/ENG/WEB/IN/CONTENT/VIDEOURL/VOD/1000022678
  security_token: <JWT from GETTOKEN>
-> videoURL?hdnea=exp=...~acl=/*~id=...~hmac=...        (~12 h)
```

One token covers all 22 `dishmt.slivcdn.com` channels (22/22 masters verified).
The anonymous API needs **no credential**, so there is no secret to store; the
token is ephemeral (~12 h) and baked into the playlist like the JioTV/JioHotstar
tokens. Normal Cloudflare Workers `fetch` cannot mint it (`AKA_0403_PANIC`), but
GitHub Actions / any normal egress can — which is why it was moved off the
Cloudflare Worker + Browser Rendering. The CDN may 403 the GitHub datacenter IP
during verification, so `generate_sony.py` falls back to publishing the full
catalog when it cannot verify from the runner.

## ⏰ Auto-Refresh Schedule
- Automatically runs **every 5 hours** using GitHub Actions (`.github/workflows/update.yml`).
  The JioTV and JioHotstar tokens live ~6 h, and SonyLIV's ~12 h, so a 5 h
  cycle keeps them all fresh.
- Step order: `generate_vzy.py` → `generate_fancode.py` → `generate_sony.py` → `merge.py`.
- A generator failure is non-fatal: each script leaves the previous playlist
  untouched if its upstream is unavailable.
- Automatically updates stream tokens, live matches, upcoming fixtures, and manifest URLs.
