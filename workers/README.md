# Cloudflare Workers Suite — IPTV Hub

This directory contains the source code for all Cloudflare Workers deployed to `*.gramnaters.workers.dev`:

## 1. JTV Worker (`workers/jtv`)
- **Domain**: `https://jtv.gramnaters.workers.dev`
- **Purpose**: Autonomous JioTV Stream Engine.
- **Endpoints**:
  - `GET /live.m3u` & `GET /personal.m3u`: 100% independent M3U playlist routing every channel through your personal real-time minter.
  - `GET /playlist.m3u`: Master JioTV M3U playlist with ClearKeys and edge self-healing.
  - `GET /live/:id.m3u8` & `GET /play/:id`: Real-time stream URL minter (calls Jio's official `/playback/apis/v1/geturl` using your Jio login credentials).
  - `GET /channels.json`: JSON API for channels.
  - `GET /health`: Health status.
- **Deploy**: `cd workers/jtv && npx wrangler deploy`

## 2. Live Master Worker (`workers/live`)
- **Domain**: `https://live.gramnaters.workers.dev`
- **Purpose**: Master IPTV Aggregator endpoint serving `Combined.m3u`.
- **Endpoints**:
  - `GET /`: Serves aggregated multi-source playlist with edge caching and token self-healing.
  - `GET /health`: Health check.
- **Deploy**: `cd workers/live && npx wrangler deploy`

## 3. JioHotstar Worker (`workers/jhs`)
- **Domain**: `https://jhs.gramnaters.workers.dev`
- **Purpose**: 100% self-hosted JioHotstar live stream playlist engine with automated Puppeteer browser token minter running on Cloudflare Browser Rendering cron.
- **Endpoints**:
  - `GET /` & `GET /playlist.m3u`: Live JioHotstar M3U playlist.
  - `GET /status`: KV token freshness and status.
- **Deploy**: `cd workers/jhs && npx wrangler deploy`

## 4. ZEE5 Worker (`workers/zee`)
- **Domain**: `https://zee.gramnaters.workers.dev`
- **Purpose**: ZEE5 Live Stream resolving proxy for Indian channels.
- **Endpoints**:
  - `GET /live/:id.m3u8`: Stream resolver.
  - `GET /status`: Status check.
- **Deploy**: `cd workers/zee && npx wrangler deploy`
