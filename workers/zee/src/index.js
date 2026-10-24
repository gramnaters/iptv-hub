import { CHANNELS } from "./channels.js";

const USER_AGENT = "com.graymatrix.did;Android TV;5.82.6(203230929);Android(10);Xiaomi(Redmi Note 8 Pro)";
const UPSTREAM_BASE = "http://premiumplug.fun/tee/zee5.php";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

function buildPlaylist(host) {
  const lines = [
    "#EXTM3U",
    `# Total Channels: ${CHANNELS.length}`,
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
    lines.push(`https://${host}/live/${cid}.m3u8`);
    lines.push("");
  }

  return lines.join("\n").trim() + "\n";
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const host = url.host;

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    // Root / or /playlist.m3u or /live.m3u -> Pure M3U playlist (tgaadi style)
    if (path === "/" || path === "/playlist.m3u" || path === "/live.m3u") {
      return new Response(buildPlaylist(host), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl",
          "Content-Disposition": 'inline; filename="zee5.m3u"',
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
        timestamp: new Date().toISOString()
      }, { headers: CORS });
    }

    // Handle channel stream resolution: /live/:id or /live/:id.m3u8 or /:id.m3u8
    const match = path.match(/(?:^\/live\/|^\/)([0-9a-zA-Z\-_]+)(?:\.m3u8)?$/);
    if (!match) {
      return new Response("Invalid channel path. Use /live/:channel_id.m3u8\n", { status: 400, headers: CORS });
    }

    const channelId = match[1];
    const targetUrl = `${UPSTREAM_BASE}/${channelId}.m3u8`;

    try {
      const upstreamRes = await fetch(targetUrl, {
        method: "GET",
        headers: {
          "User-Agent": USER_AGENT,
        },
        redirect: "manual",
      });

      const location = upstreamRes.headers.get("location");
      if (location && (upstreamRes.status === 302 || upstreamRes.status === 301)) {
        return new Response(null, {
          status: 302,
          headers: {
            ...CORS,
            "Location": location,
            "Cache-Control": "no-store, no-cache, must-revalidate",
          },
        });
      }

      const body = await upstreamRes.arrayBuffer();
      const headers = new Headers(upstreamRes.headers);
      for (const [k, v] of Object.entries(CORS)) {
        headers.set(k, v);
      }
      headers.set("Cache-Control", "no-store");
      return new Response(body, {
        status: upstreamRes.status,
        headers,
      });

    } catch (err) {
      return new Response(`Error resolving stream: ${err.message}\n`, {
        status: 502,
        headers: CORS,
      });
    }
  },
};
