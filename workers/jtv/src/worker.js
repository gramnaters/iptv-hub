import { CHANNELS } from "./channels.js";

const CHANNELS_JSON = JSON.stringify(CHANNELS, null, 4);

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

let inMemoryJioToken = "";
let inMemoryJioExp = 0;

async function refreshAuthToken(creds) {
  try {
    const refreshTok = creds.refreshToken;
    if (!refreshTok) return null;

    const res = await fetch("https://auth.media.jio.com/tokenservice/apis/v1/refreshtoken?langId=6", {
      method: "POST",
      headers: {
        "devicetype": "phone",
        "versionCode": "290",
        "os": "android",
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": "okhttp/4.2.2"
      },
      body: JSON.stringify({
        appName: "RJIL_JioTV",
        deviceId: creds.deviceId || "3c6d6b5702fa09bd",
        refreshToken: refreshTok
      })
    });

    if (res.ok) {
      const data = await res.json();
      return data.authToken || null;
    }
  } catch (err) {}
  return null;
}

async function mintJioLiveToken(creds) {
  if (inMemoryJioToken && inMemoryJioExp - Date.now() > 1800000) {
    return inMemoryJioToken;
  }
  if (!creds || !creds.authToken) return null;

  const fetchToken = async (token) => {
    const getUrlPayload = new URLSearchParams({
      stream_type: "Seek",
      channel_id: "144"
    });
    return await fetch("https://jiotvapi.media.jio.com/playback/apis/v1/geturl?langId=6", {
      method: "POST",
      headers: {
        appkey: "NzNiMDhlYzQyNjJm",
        devicetype: "phone",
        os: "android",
        deviceId: creds.deviceId || "3c6d6b5702fa09bd",
        isott: "false",
        channel_id: "144",
        accesstoken: token,
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "okhttp/4.2.2"
      },
      body: getUrlPayload.toString()
    });
  };

  try {
    let res = await fetchToken(creds.authToken);
    if (res.status === 419) {
      const freshAuth = await refreshAuthToken(creds);
      if (freshAuth) {
        creds.authToken = freshAuth;
        res = await fetchToken(freshAuth);
      }
    }
    if (res.ok) {
      const data = await res.json();
      const resultUrl = data.result || "";
      const m = resultUrl.match(/(__hdnea__=st=\d+~exp=(\d+)~acl=[^~"'\r\n\s]+~hmac=[a-f0-9]+)/);
      if (m) {
        inMemoryJioToken = m[1];
        inMemoryJioExp = parseInt(m[2], 10) * 1000;
        return inMemoryJioToken;
      }
    }
  } catch (e) {}
  return inMemoryJioToken || null;
}

function buildJioPlaylist(host, token = "") {
  const lines = [
    "#EXTM3U",
    "# JioTV Direct Playlist v2.5",
    `# Total Channels: ${CHANNELS.length}`,
    `# Source: https://${host}`,
    ""
  ];

  for (const ch of CHANNELS) {
    const id = ch["tvg-id"] || "";
    const name = ch["channel-name"] || "";
    const logo = ch["tvg-logo"] || "";
    const group = `JioTV - ${ch["group-title"] || "Entertainment"}`;
    const key = ch["license_key"] || "";
    const mpd = ch["mpd_url"] || "";
    if (!id || !name) continue;

    lines.push(
      `#EXTINF:-1 tvg-id="${id}" tvg-name="${name}" tvg-logo="${logo}" group-title="${group}",${name}`
    );
    lines.push("#KODIPROP:inputstream=inputstream.adaptive");
    lines.push("#KODIPROP:inputstream.adaptive.manifest_type=mpd");
    if (key) {
      lines.push("#KODIPROP:inputstream.adaptive.license_type=clearkey");
      lines.push(`#KODIPROP:inputstream.adaptive.license_key=${key}`);
    }
    lines.push("#EXTVLCOPT:http-user-agent=plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0");
    lines.push("#EXTVLCOPT:http-referrer=https://www.jiotv.com/");
    if (token) {
      lines.push(`#EXTVLCOPT:http-cookie=${token}`);
      lines.push(`#EXTHTTP:{"User-Agent": "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0", "Origin": "https://www.jiotv.com/", "Referer": "https://www.jiotv.com/", "Cookie": "${token}"}`);
      lines.push(`${mpd}?${token}`);
    } else {
      lines.push(`https://${host}/live/${id}.m3u8`);
    }
    lines.push("");
  }

  return lines.join("\n").trim() + "\n";
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const p = url.pathname.replace(/\/+$/, "") || "/";
    const host = url.host;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    let creds = null;
    if (env.JIOTV_CREDS) {
      try { creds = JSON.parse(env.JIOTV_CREDS); } catch {}
    }

    // 1. Root / or /data or /channels.json -> Clean JSON channel array
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
      return Response.json({
        ok: true,
        service: "jtv",
        status: "healthy",
        channels: CHANNELS.length,
        personal_account_active: Boolean(creds && creds.authToken),
        endpoints: {
          data_json: `https://${host}/`,
          live_m3u: `https://${host}/live.m3u`,
          playlist_m3u: `https://${host}/playlist.m3u`,
          stream_resolver: `https://${host}/live/{id}.m3u8`
        },
        ts: new Date().toISOString()
      }, { headers: CORS });
    }

    // 3. Direct Personal Playback Proxy (/live/:id.m3u8 or /play/:id)
    const playMatch = p.match(/^\/(?:play|live)\/(\d+)(?:\.m3u8)?$/);
    if (playMatch) {
      const channelId = playMatch[1];
      try {
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

    // 4. M3U Playlists (/live.m3u, /playlist.m3u, /personal.m3u, /jiotv.m3u)
    if (p === "/live.m3u" || p === "/playlist.m3u" || p === "/personal.m3u" || p === "/jiotv.m3u" || url.searchParams.has("m3u")) {
      try {
        let token = "";
        if (creds && creds.authToken) {
          token = await mintJioLiveToken(creds);
        }
        const playlistText = buildJioPlaylist(host, token || "");
        return new Response(playlistText, {
          status: 200,
          headers: {
            ...CORS,
            "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
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
