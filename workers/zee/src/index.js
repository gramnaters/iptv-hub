import { CHANNELS } from "./channels.js";

const USER_AGENT = "com.graymatrix.did;Android TV;5.82.6(203230929);Android(10);Xiaomi(Redmi Note 8 Pro)";
const CDN_HOST = "z5ak-cmaflive.zee5.com";
const CDN_BASE = `https://${CDN_HOST}/cmaf/live`;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

function formatIST(date) {
  try {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: "Asia/Kolkata",
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    }).format(date) + " IST";
  } catch (e) {
    return date.toISOString();
  }
}

function buildPlaylist(host, token = "") {
  const tokenQuery = token ? (token.startsWith("?") ? token : (token.startsWith("hdnts=") ? `?${token}` : `?hdnts=${token}`)) : "";
  const lines = [
    "#EXTM3U",
    "# ZEE5 Direct Stream Playlist v2.5",
    `# Total Channels: ${CHANNELS.length}`,
    `# Generated: ${formatIST(new Date())}`,
    `# Source: https://${host}`,
    ""
  ];

  for (const ch of CHANNELS) {
    const cid = (ch.id || "").trim();
    const name = (ch.name || "").trim();
    const logo = (ch.logo || "").trim();
    const genre = (ch.genre || "Entertainment").trim();
    const group = (ch.group || "ZEE5 India").trim();
    if (!cid || !name) continue;

    lines.push(
      `#EXTINF:-1 tvg-id="${cid}" tvg-name="${name}" tvg-logo="${logo}" tvg-category="${genre}" group-title="${group}" group-logo="https://upload.wikimedia.org/wikipedia/commons/5/5a/Zee5-official-logo.jpeg",${name}`
    );
    lines.push(`#EXTVLCOPT:http-user-agent=${USER_AGENT}`);
    lines.push(`#EXTVLCOPT:http-referrer=https://www.zee5.com/`);
    lines.push(`#EXTHTTP:{"User-Agent":"${USER_AGENT}","Referrer":"https://www.zee5.com/","Origin":"https://www.zee5.com"}`);
    if (tokenQuery) {
      lines.push(`${CDN_BASE}/${cid}/master.m3u8${tokenQuery}`);
    } else {
      lines.push(`https://${host}/live/${cid}.m3u8`);
    }
    lines.push("");
  }

  return lines.join("\n").trim() + "\n";
}

function buildDataJson(host, token = "") {
  const tokenQuery = token ? (token.startsWith("?") ? token : (token.startsWith("hdnts=") ? `?${token}` : `?hdnts=${token}`)) : "";
  const channelsData = CHANNELS.map(ch => ({
    name: ch.name,
    slug: ch.id,
    group: ch.group || ch.genre || "ZEE5 India",
    genre: ch.genre || "Entertainment",
    language: ch.language || "hi",
    logo: ch.logo || "",
    url: tokenQuery ? `${CDN_BASE}/${ch.id}/master.m3u8${tokenQuery}` : `https://${host}/live/${ch.id}.m3u8`,
    cdn_direct: `${CDN_BASE}/${ch.id}/master.m3u8`,
    headers: {
      "User-Agent": USER_AGENT,
      "Referer": "https://www.zee5.com/",
      "Origin": "https://www.zee5.com"
    }
  }));

  return {
    ok: true,
    version: "2.5",
    generated_at: formatIST(new Date()),
    timezone: "Asia/Kolkata",
    total_channels: CHANNELS.length,
    download_m3u: `https://${host}/playlist.m3u?download=1`,
    view_m3u: `https://${host}/playlist.m3u`,
    cdn: {
      host: CDN_HOST,
      path_base: "/cmaf/live",
      pattern: `${CDN_BASE}/{channel_id}/master.m3u8`,
      note: "Streams resolve directly via official ZEE5 CMAF CDN"
    },
    cookie: {
      name: "hdnts",
      type: "Akamai Dynamic Token",
      active: Boolean(token)
    },
    channels: channelsData
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const host = url.host;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    const token = env.ZEE5_TOKEN || "";

    // Serve raw M3U playlist if ?m3u or /playlist.m3u or /live.m3u or ?download=1
    if (url.searchParams.has("m3u") || path === "/playlist.m3u" || path === "/live.m3u") {
      const isDownload = url.searchParams.has("download") || url.searchParams.get("download") === "1";
      return new Response(buildPlaylist(host, token), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
          "Content-Disposition": isDownload ? 'attachment; filename="zee5.m3u"' : 'inline; filename="zee5.m3u"',
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    // Root / or /channels or /data.json -> Structured JSON API
    if (path === "/" || path === "/channels" || path === "/data.json") {
      return new Response(JSON.stringify(buildDataJson(host, token), null, 2), {
        headers: {
          ...CORS,
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=300",
        },
      });
    }

    if (path === "/channels.json") {
      return new Response(JSON.stringify(CHANNELS, null, 2), {
        headers: {
          ...CORS,
          "Content-Type": "application/json; charset=utf-8",
          "Cache-Control": "public, max-age=600",
        },
      });
    }

    if (path === "/status" || path === "/health") {
      return Response.json({
        ok: true,
        service: "zee-worker",
        clean_url: `https://${host}`,
        channels: CHANNELS.length,
        status: "active",
        token_configured: Boolean(token),
        timestamp: new Date().toISOString()
      }, { headers: CORS });
    }

    // Handle channel stream resolution: /live/:id or /live/:id.m3u8 or /:id.m3u8
    const match = path.match(/(?:^\/live\/|^\/)([0-9a-zA-Z\-_]+)(?:\.m3u8)?$/);
    if (!match) {
      return new Response("Invalid channel path. Use /live/:channel_id.m3u8\n", { status: 400, headers: CORS });
    }

    const channelId = match[1];
    const tokenQuery = token ? (token.startsWith("?") ? token : (token.startsWith("hdnts=") ? `?${token}` : `?hdnts=${token}`)) : "";
    const directStreamUrl = `${CDN_BASE}/${channelId}/master.m3u8${tokenQuery}`;

    return new Response(null, {
      status: 302,
      headers: {
        ...CORS,
        "Location": directStreamUrl,
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    });
  },
};
