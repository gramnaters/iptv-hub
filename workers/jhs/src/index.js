/**
 * jhs — JioHotstar live playlist, self-minting.
 *
 * The streams are gated by one Akamai `hdntl` token (acl=/*, 24h). It is minted
 * from the owner's Hotstar session:
 *
 *   POST https://www.hotstar.com/api/internal/bff/v2/start   (x2, session token)
 *     -> response contains a livetv.hotstar.com manifest URL
 *   GET  <that URL>
 *     -> Set-Cookie: hdntl=exp=...~acl=%2f*~id=...~hmac=...
 *
 * Why a browser: a plain Worker fetch is rejected by Akamai (403) from
 * Cloudflare's datacenter egress, same as GitHub Actions. Browser Run uses a
 * different egress and is accepted, so the mint runs in a headless page.
 *
 * Route map
 *   GET  /                 playlist (M3U). Every path except /status serves it.
 *   GET  /status           token freshness + channel count (JSON)
 *   POST /mint             force a mint now (Authorization: Bearer MINT_SECRET)
 *   cron (hourly)          mint only when the stored token has < 8h left
 *
 * Secrets
 *   HS_COOKIE     trimmed Hotstar cookie jar (sessionUserUP, deviceId, ...)
 *   MINT_SECRET   bearer token for POST /mint
 */

import { CHANNELS } from "./channels.js";
import { USER_TOKEN as SEED_TOKEN, MINTED_AT as SEED_MINTED_AT } from "./token.js";
import puppeteer from "@cloudflare/puppeteer";

const KV_KEY = "hs:token:v1";
const MIN_TTL_MS = 8 * 60 * 60 * 1000; // mint when less than this is left
const COOKIE_KEYS = ["deviceId", "userHID", "userPID", "userCountryCode", "sessionUserUP", "userUP"];

const USER_AGENT = "Hotstar;in.startv.hotstar/25.02.24.8.11169@Premium Plugx(Android/15)";
const REFERER = "https://www.hotstar.com/";
const ORIGIN = "https://www.hotstar.com";

const APP_UA = "Hotstar;in.startv.hotstar/25.02.24.8.11169";
const WEB_CLIENT = "platform:web;app_version:26.09.23.1;browser:Chrome;schema_version:0.0.1";
const BFF = "https://www.hotstar.com/api/internal/bff/v2/start";
// Any cheap page on the site works: it only exists to give the BFF fetch a
// same-origin context. Loading the real home page costs seconds of billed time.
const ORIGIN_URL = "https://www.hotstar.com/robots.txt";

const CAPS = { ads: ["non_ssai", "ssai"], audio_channel: ["stereo"], container: ["fmp4", "fmp4br", "ts"], dvr: ["short"], dynamic_range: ["sdr"], encryption: ["plain"], ladder: ["web", "tv", "phone"], package: ["dash", "hls"], resolution: ["sd", "hd", "fhd"], video_codec: ["h264"], video_codec_non_secure: ["h265", "h264"] };
const DRM = { hdcp_version: ["HDCP_V2_2"], widevine_security_level: [], playready_security_level: [] };

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

/* ------------------------------------------------------------------ helpers */

const tokenExp = (t) => {
  const m = t && t.match(/exp=(\d+)/);
  return m ? Number(m[1]) * 1000 : 0;
};

const stateOf = (token, mintedAt, source) => {
  const exp = tokenExp(token);
  return {
    ok: true,
    source,
    mintedAt,
    exp: exp ? new Date(exp).toISOString() : null,
    expiresInHours: exp ? Number(((exp - Date.now()) / 3.6e6).toFixed(2)) : null,
    totalChannels: CHANNELS.length,
  };
};

async function loadState(env) {
  try {
    const raw = await env.HS_CACHE.get(KV_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && parsed.token) return { token: parsed.token, mintedAt: parsed.mintedAt, source: "kv" };
    }
  } catch (e) {
    console.warn("kv read failed:", e && e.message);
  }
  return { token: SEED_TOKEN, mintedAt: SEED_MINTED_AT, source: "seed" };
}

async function storeToken(env, token) {
  const mintedAt = new Date().toISOString();
  await env.HS_CACHE.put(KV_KEY, JSON.stringify({ token, mintedAt }), {
    // keep a copy well past the token life so /status can always explain itself
    expirationTtl: 60 * 60 * 24 * 30,
  });
  return mintedAt;
}

/* --------------------------------------------------------------------- mint */

// Runs inside the headless page: needs a same-origin context for the BFF calls.
async function mintInPage(args) {
  const { dl, session, jar, client } = args;
  const headers = (tok, extra) => Object.assign({
    Accept: "application/json",
    "Content-Type": "application/json",
    "x-hs-usertoken": tok,
    "x-hs-platform": "web",
    "x-hs-app": "260923001",
    "x-country-code": "in",
    "x-hs-accept-language": "eng",
    "x-hs-device-id": jar.deviceId,
    "x-hs-client": client,
    "x-hs-retry-count": "0",
    "x-hs-is-retry": "false",
  }, extra || {});

  const post = async (tok, extra) => {
    const r = await fetch("/api/internal/bff/v2/start", {
      method: "POST",
      headers: headers(tok, extra),
      body: JSON.stringify({ deeplink_url: dl, app_launch_count: 34 }),
    });
    const text = (await r.text()).split("\\/").join("/");
    return { status: r.status, text, tok: r.headers.get("x-hs-usertoken"), ps: r.headers.get("x-hs-setproxystate") };
  };

  const first = await post(session, null);
  if (first.status !== 200) return { error: "bff step 1 -> HTTP " + first.status, body: first.text.slice(0, 160) };

  const second = await post(first.tok || session, {
    "x-hs-proxystate": first.ps || "",
    "x-hs-proxystate-ud": "loc=" + (jar.fresh_loc || ""),
    "x-hs-client-targeting": "ad_id:" + jar.deviceId + ";user_lat:false;",
  });
  if (second.status !== 200) return { error: "bff step 2 -> HTTP " + second.status, body: second.text.slice(0, 160) };

  const m = second.text.match(/https:\/\/(?:livetv|live09p|jcevents)\.hotstar\.com\/[^"'\s]+/);
  if (!m) return { error: "no livetv url in bff payload" };
  return { manifestUrl: m[0] };
}

async function mintWithBrowser(env) {
  const jar = JSON.parse(env.HS_COOKIE || "{}");
  if (!jar.sessionUserUP) throw new Error("HS_COOKIE missing sessionUserUP");

  const id = env.MINT_ID || "1540072843";
  const dl = "/in/shows/x/" + id + "/live/watch?client_capabilities=" +
    encodeURIComponent(JSON.stringify(CAPS)) + "&drm_parameters=" +
    encodeURIComponent(JSON.stringify(DRM)) + "&request_features=consent_supported";

  const browser = await puppeteer.launch(env.BROWSER);
  try {
    const page = await browser.newPage();
    const cdp = await page.createCDPSession();
    await cdp.send("Network.enable");

    // keep the billed session short: only the JSON/XHR traffic matters
    await page.setRequestInterception(true);
    page.on("request", (req) => {
      const u = req.url();
      // Akamai only issues the real wildcard token when the manifest request
      // looks like a media sub-request from the site. Without the Referer it
      // answers 403 with a decoy hdntl that fails on playback.
      if (u.includes("hotstar.com/") && (u.startsWith("https://livetv.") || u.startsWith("https://live09p.") || u.startsWith("https://jcevents."))) {
        req.continue({ headers: { "User-Agent": USER_AGENT, Referer: REFERER, Origin: ORIGIN, Accept: "*/*" } }).catch(() => {});
        return;
      }
      const type = req.resourceType();
      const drop = type === "image" || type === "font" || type === "media" || type === "stylesheet";
      (drop ? req.abort() : req.continue()).catch(() => {});
    });

    const cookies = COOKIE_KEYS.filter((k) => jar[k]).map((k) => ({
      name: k, value: String(jar[k]), domain: ".hotstar.com", path: "/", secure: true,
    }));
    if (cookies.length) await page.setCookie(...cookies);

    await page.goto(ORIGIN_URL, { waitUntil: "domcontentloaded", timeout: 45000 });

    const res = await page.evaluate(mintInPage, { dl, session: jar.sessionUserUP, jar, client: WEB_CLIENT });
    if (!res || res.error) throw new Error(res ? res.error : "page mint returned nothing");

    // The manifest itself answers 403 for a headless UA, but the CDN still
    // hands back the wildcard token in Set-Cookie. That is all we need.
    try {
      await page.goto(res.manifestUrl, { waitUntil: "domcontentloaded", timeout: 30000 });
    } catch (e) {
      console.warn("manifest navigation:", e && e.message);
    }

    const all = await cdp.send("Network.getAllCookies");
    const hd = (all.cookies || []).find((c) => c.name === "hdntl");
    if (!hd || !hd.value) throw new Error("no hdntl cookie after manifest fetch");
    const token = "hdntl=" + hd.value;
    if (!tokenExp(token)) throw new Error("hdntl cookie has no exp claim");
    return token;
  } finally {
    try { await browser.close(); } catch {}
  }
}

async function refresh(env, force) {
  const current = await loadState(env);
  const leftMs = tokenExp(current.token) - Date.now();
  if (!force && leftMs > MIN_TTL_MS) {
    return { skipped: true, expiresInHours: Number((leftMs / 3.6e6).toFixed(2)) };
  }
  const started = Date.now();
  const token = await mintWithBrowser(env);
  const mintedAt = await storeToken(env, token);
  const out = {
    minted: true,
    mintedAt,
    expiresInHours: Number(((tokenExp(token) - Date.now()) / 3.6e6).toFixed(2)),
    tookMs: Date.now() - started,
  };
  console.log("mint ok", JSON.stringify(out));
  return out;
}

/* ----------------------------------------------------------------- playlist */

function buildPlaylist(hdntl) {
  const lines = ["#EXTM3U", "# JioHotstar Channels", "# 100% Self-Hosted & Self-Dependent Playlist (Your Cookies)", ""];
  for (const ch of CHANNELS) {
    const idAttr = ch.tvgId ? `tvg-id="${ch.tvgId}" ` : "";
    lines.push(`#EXTINF:-1 ${idAttr}tvg-name="${ch.name}" tvg-logo="${ch.logo}" group-title="${ch.group}", ${ch.name}`);
    const isMpd = ch.type === "mpd" || ch.url.includes(".mpd");
    if (isMpd) {
      lines.push("#KODIPROP:inputstream=inputstream.adaptive");
      lines.push("#KODIPROP:inputstream.adaptive.manifest_type=mpd");
      if (ch.keyId && ch.key) {
        lines.push("#KODIPROP:inputstream.adaptive.license_type=clearkey");
        lines.push(`#KODIPROP:inputstream.adaptive.license_key=${ch.keyId}:${ch.key}`);
      }
    }
    lines.push(`#EXTVLCOPT:http-user-agent=${USER_AGENT}`);
    lines.push(`#EXTVLCOPT:http-referrer=${REFERER}`);
    lines.push(`#EXTVLCOPT:http-extra-headers=Origin: ${ORIGIN}`);
    if (hdntl) {
      lines.push(`#EXTVLCOPT:http-cookie=${hdntl}`);
      lines.push(`#EXTHTTP:${JSON.stringify({ Origin: ORIGIN, Referer: REFERER, Cookie: hdntl })}`);
    }
    lines.push(ch.url);
    lines.push("");
  }
  return lines.join("\n");
}

/* --------------------------------------------------------------------- main */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });

    if (path === "/status") {
      const state = await loadState(env);
      const payload = { ...stateOf(state.token, state.mintedAt, state.source), cookieConfigured: !!env.HS_COOKIE, cron: "0 * * * *" };
      return Response.json(payload, { headers: CORS });
    }

    if (path === "/mint") {
      if (request.method !== "POST") {
        return new Response("POST required\n", { status: 405, headers: CORS });
      }
      const auth = request.headers.get("Authorization") || "";
      if (!env.MINT_SECRET || auth !== "Bearer " + env.MINT_SECRET) {
        return new Response("unauthorized\n", { status: 401, headers: CORS });
      }
      try {
        const result = await refresh(env, true);
        return Response.json(result, { headers: CORS });
      } catch (e) {
        return Response.json({ minted: false, error: (e && e.message) || String(e) }, { status: 502, headers: CORS });
      }
    }

    const state = await loadState(env);
    return new Response(buildPlaylist(state.token), {
      headers: {
        ...CORS,
        "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
        "Content-Disposition": 'inline; filename="jhs.m3u"',
        "Cache-Control": "public, max-age=300",
      },
    });
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      refresh(env, false).catch((e) => console.error("scheduled mint failed:", (e && e.stack) || e)),
    );
  },
};
