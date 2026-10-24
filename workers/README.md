# Cloudflare Workers Suite — IPTV Hub

This directory contains the production source code for all Cloudflare Workers deployed across `*.gramnaters.workers.dev`:

## 1. Master Live Hub (`workers/live`)
- **Domain**: `https://live.gramnaters.workers.dev`
- **Purpose**: Master IPTV Aggregator serving all 1,578+ channels across 8 providers.
- **Endpoints**:
  - `GET /`: Interactive web community dashboard (for browsers) / Raw Master M3U playlist (for IPTV players).
  - `GET /playlist.m3u` & `GET /Combined.m3u`: Raw M3U playlist.
  - `GET /status` & `GET /health`: Aggregation health and source status.
- **Deploy**: `cd workers/live && npx wrangler deploy`

## 2. JioTV Engine (`workers/jtv`)
- **Domain**: `https://jtv.gramnaters.workers.dev`
- **Purpose**: Autonomous JioTV Stream Engine with 1,175 live channels.
- **Endpoints**:
  - `GET /`: Dark-glass community dashboard with dynamic channel search and category filters.
  - `GET /live.m3u`: 100% independent M3U playlist routing through real-time minter.
  - `GET /playlist.m3u`: Master JioTV M3U playlist with ClearKeys.
  - `GET /live/:id.m3u8`: Real-time stream URL minter (calls Jio's official `/playback/apis/v1/geturl`).
  - `GET /channels.json`: Channel metadata JSON.
  - `GET /health`: Health status.
- **Deploy**: `cd workers/jtv && npx wrangler deploy`

## 3. JioHotstar Engine (`workers/jhs`)
- **Domain**: `https://jhs.gramnaters.workers.dev`
- **Purpose**: Self-hosted JioHotstar streaming engine with 146 live channels and automated Puppeteer browser token minter.
- **Endpoints**:
  - `GET /`: Community dashboard with real-time token validity countdown and copy links.
  - `GET /playlist.m3u`: Direct M3U playlist with baked Akamai `hdntl` cookies.
  - `GET /status`: KV token freshness and health JSON.
- **Deploy**: `cd workers/jhs && npx wrangler deploy`

## 4. ZEE5 Engine (`workers/zee`)
- **Domain**: `https://zee.gramnaters.workers.dev`
- **Purpose**: ZEE5 Live Stream resolving engine for 118 live entertainment and regional channels.
- **Endpoints**:
  - `GET /`: Purple community dashboard with live searchable directory and quick copy endpoints.
  - `GET /playlist.m3u`: Complete ZEE5 M3U playlist.
  - `GET /channels.json`: Complete 118-channel catalog JSON.
  - `GET /live/:id.m3u8`: On-demand stream resolver proxying to signed CDN streams.
  - `GET /status`: Service health.
- **Deploy**: `cd workers/zee && npx wrangler deploy`

## 5. SonyLIV Engine (`workers/sliv`)
- **Domain**: `https://sliv.gramnaters.workers.dev`
- **Purpose**: SonyLIV Live Stream Engine with 22 HD sports, movie, and entertainment channels.
- **Endpoints**:
  - `GET /`: Dark-blue community dashboard with live channel explorer and copy cards.
  - `GET /playlist.m3u`: Direct 22-channel SonyLIV M3U playlist.
  - `GET /channels.json`: Sony channels metadata JSON.
  - `GET /:slug.m3u8`: 302 stream resolver redirecting to `dishmt.slivcdn.com` with active `hdnea` wildcard token.
  - `GET /status`: Token freshness and health.
- **Deploy**: `cd workers/sliv && npx wrangler deploy`
