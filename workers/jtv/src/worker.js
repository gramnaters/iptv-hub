import { CHANNELS } from "./channels.js";

const CHANNELS_JSON = JSON.stringify(CHANNELS, null, 4);
const GITHUB_PLAYLIST = "https://raw.githubusercontent.com/gramnaters/iptv-hub/main/playlists/jiotv.m3u";

const TOKEN_ENDPOINTS = [
  "https://plugxvipplaylist.lovable.app/api/playlist",
  "https://allinonereborn2.online/jstrweb2/cookies.json",
  "https://raw.githubusercontent.com/sportlive18/Sportlink-wtf/refs/heads/main/cookie.json"
];

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

async function fetchLiveToken() {
  for (const url of TOKEN_ENDPOINTS) {
    try {
      const res = await fetch(url, {
        headers: { "User-Agent": "Mozilla/5.0" },
        cf: { cacheTtl: 60 }
      });
      if (!res.ok) continue;

      const body = await res.text();
      const m = body.match(/(__hdnea__=st=\d+~exp=(\d+)~acl=[^~"'\r\n\s]+~hmac=[a-f0-9]+)/);
      if (m) {
        const expSec = parseInt(m[2], 10);
        const nowSec = Math.floor(Date.now() / 1000);
        if (expSec - nowSec > 1800) {
          return m[1];
        }
      }
    } catch (e) {}
  }
  return null;
}

async function getFreshPlaylist(ctx) {
  const cacheKey = new Request("https://jtv-internal.cache/jiotv.m3u", { method: "GET" });
  const cache = caches.default;
  const hit = await cache.match(cacheKey);
  if (hit) {
    return await hit.text();
  }

  const upstream = await fetch(GITHUB_PLAYLIST, {
    headers: { "User-Agent": "Cloudflare-Worker" },
    cf: { cacheTtl: 300, cacheEverything: true }
  });

  if (!upstream.ok) {
    throw new Error(`Upstream returned ${upstream.status}`);
  }

  let text = await upstream.text();
  const tokenMatch = text.match(/(__hdnea__=st=\d+~exp=(\d+)~acl=[^~"'\r\n\s]+~hmac=[a-f0-9]+)/);

  let isExpired = false;
  if (tokenMatch) {
    const expSec = parseInt(tokenMatch[2], 10);
    const nowSec = Math.floor(Date.now() / 1000);
    if (expSec - nowSec < 1800) {
      isExpired = true;
    }
  } else {
    isExpired = true;
  }

  if (isExpired) {
    const freshToken = await fetchLiveToken();
    if (freshToken) {
      text = text.replace(/__hdnea__=st=\d+~exp=\d+~acl=[^~"'\r\n\s]+~hmac=[a-f0-9]+/g, freshToken);
    }
  }

  const responseToCache = new Response(text, {
    headers: {
      "Content-Type": "audio/x-mpegurl; charset=utf-8",
      "Cache-Control": "public, max-age=300"
    }
  });

  if (ctx && ctx.waitUntil) {
    ctx.waitUntil(cache.put(cacheKey, responseToCache.clone()));
  }

  return text;
}

async function refreshAuthToken(creds) {
  try {
    const res = await fetch("https://auth.media.jio.com/tokenservice/apis/v1/refreshtoken?langId=6", {
      method: "POST",
      headers: {
        appkey: "NzNiMDhlYzQyNjJm",
        devicetype: "phone",
        os: "android",
        deviceId: creds.deviceId || "3c6d6b5702fa09bd",
        isott: "false",
        accesstoken: creds.authToken,
        uniqueId: creds.uniqueId,
        "Content-Type": "application/json",
        "User-Agent": "okhttp/4.2.2"
      },
      body: JSON.stringify({
        appName: "RJIL_JioTV",
        deviceId: creds.deviceId || "3c6d6b5702fa09bd"
      })
    });

    if (res.ok) {
      const data = await res.json();
      return data.authToken || null;
    }
  } catch (err) {}
  return null;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const p = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    // 1. Root / or /data or /channels.json -> Coder-friendly JSON (cricindia95 format)
    if (p === "/" || p === "/data" || p === "/channels.json") {
      return new Response(CHANNELS_JSON, {
        status: 200,
        headers: {
          ...CORS,
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    // 2. Health & Status check
    if (p === "/health" || p === "/status") {
      const hasPersonalCreds = Boolean(env.JIOTV_CREDS);
      return Response.json({
        ok: true,
        service: "jtv",
        status: "healthy",
        channels: CHANNELS.length,
        personal_account_active: hasPersonalCreds,
        endpoints: {
          data_json: `https://${url.host}/`,
          live_m3u: `https://${url.host}/live.m3u`,
          playlist_m3u: `https://${url.host}/playlist.m3u`,
          stream_resolver: `https://${url.host}/live/{id}.m3u8`
        },
        ts: new Date().toISOString()
      }, { headers: CORS });
    }

    // 3. Direct Personal Playback Proxy (/live/:id.m3u8 or /play/:id)
    const playMatch = p.match(/^\/(?:play|live)\/(\d+)(?:\.m3u8)?$/);
    if (playMatch) {
      const channelId = playMatch[1];
      try {
        let creds = null;
        if (env.JIOTV_CREDS) {
          try { creds = JSON.parse(env.JIOTV_CREDS); } catch {}
        }
        if (!creds || !creds.authToken) {
          return new Response("Personal JioTV credentials not configured in Worker\n", { status: 500, headers: CORS });
        }

        const fetchStream = async (token) => {
          const getUrlPayload = new URLSearchParams({
            stream_type: "Seek",
            channel_id: channelId
          });
          return await fetch("https://jiotvapi.media.jio.com/playback/apis/v1/geturl?langId=6", {
            method: "POST",
            headers: {
              appkey: "NzNiMDhlYzQyNjJm",
              devicetype: "phone",
              os: "android",
              deviceId: creds.deviceId || "3c6d6b5702fa09bd",
              isott: "false",
              channel_id: channelId,
              accesstoken: token,
              "Content-Type": "application/x-www-form-urlencoded",
              "User-Agent": "okhttp/4.2.2"
            },
            body: getUrlPayload.toString()
          });
        };

        let jioRes = await fetchStream(creds.authToken);

        if (jioRes.status === 419) {
          const freshAuthToken = await refreshAuthToken(creds);
          if (freshAuthToken) {
            creds.authToken = freshAuthToken;
            jioRes = await fetchStream(freshAuthToken);
          }
        }

        if (jioRes.status === 200) {
          const jioData = await jioRes.json();
          const streamUrl = jioData.result;
          if (streamUrl) {
            return Response.redirect(streamUrl, 302);
          }
        }
        return new Response(`Upstream Jio error: ${jioRes.status}\n`, { status: 502, headers: CORS });
      } catch (err) {
        return new Response(`Playback error: ${err.message}\n`, { status: 500, headers: CORS });
      }
    }

    // 4. Independent Personal Playlist (/live.m3u or /personal.m3u)
    if (p === "/live.m3u" || p === "/personal.m3u") {
      try {
        const raw = await getFreshPlaylist(ctx);
        const host = url.host;
        
        const lines = raw.split("\n");
        let curId = null;
        const out = [];
        for (const line of lines) {
          const trimmed = line.trim();
          if (trimmed.startsWith("#EXTINF")) {
            const m = trimmed.match(/tvg-id="(\d+)"/);
            curId = m ? m[1] : null;
            out.push(line);
          } else if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
            if (curId) {
              out.push(`https://${host}/live/${curId}.m3u8`);
              curId = null;
            } else {
              out.push(line);
            }
          } else {
            out.push(line);
          }
        }
        const transformed = out.join("\n");

        return new Response(transformed, {
          status: 200,
          headers: {
            ...CORS,
            "Content-Type": "application/vnd.apple.mpegurl",
            "Content-Disposition": 'inline; filename="live_jiotv.m3u"',
            "Cache-Control": "public, max-age=600"
          }
        });
      } catch (err) {
        return new Response("Error generating personal playlist: " + err.message + "\n", { status: 502, headers: CORS });
      }
    }

    // 5. Direct Master Playlist endpoint (/playlist.m3u, /jiotv.m3u)
    if (p === "/playlist.m3u" || p === "/jiotv.m3u") {
      try {
        const playlistText = await getFreshPlaylist(ctx);
        return new Response(playlistText, {
          status: 200,
          headers: {
            ...CORS,
            "Content-Type": "application/vnd.apple.mpegurl",
            "Content-Disposition": 'inline; filename="jiotv.m3u"',
            "Cache-Control": "public, max-age=300"
          }
        });
      } catch (err) {
        return new Response("Error generating playlist: " + err.message + "\n", { status: 502, headers: CORS });
      }
    }

    return new Response("Not Found\n", { status: 404, headers: CORS });
  }
};
