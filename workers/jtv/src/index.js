/**
 * jtv — JioTV playlist built from the premiumplugx per-channel feed.
 *
 * Each feed entry carries its own MPD URL, an Akamai __hdnea__ cookie (wildcard for
 * jiotvmblive, channel-scoped for the premium jiotvpllive streams) and the ClearKey
 * pairs, so the playlist needs no Jio login of its own.
 */

const FEED_URL = "https://premiumplugx.com/gibt/shoebpl.php";
const FEED_CACHE_SECONDS = 300;
const USER_AGENT = "plaYtv/7.1.3 (Linux;Android 13) ygx/824.1 ExoPlayerLib/824.0";
const ORIGIN = "https://www.jiotv.com/";
const EPG_URL = "https://avkb.short.gy/jioepg.xml.gz";
const CLEARKEY_RE = /^[0-9a-f]{32}:[0-9a-f]{32}(,[0-9a-f]{32}:[0-9a-f]{32})*$/i;

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};

function formatIST(date) {
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Kolkata", day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  }).format(date).replace(",", "") + " IST";
}

const expiryOf = (cookie) => {
  const m = cookie && cookie.match(/exp=(\d+)/);
  return m ? Number(m[1]) : 0;
};

async function loadChannels() {
  const res = await fetch(FEED_URL, {
    headers: { "User-Agent": "Mozilla/5.0" },
    cf: { cacheTtl: FEED_CACHE_SECONDS, cacheEverything: true },
  });
  if (!res.ok) throw new Error(`feed HTTP ${res.status}`);
  const items = await res.json();
  if (!Array.isArray(items)) throw new Error("feed is not a list");

  const seen = new Set();
  const channels = [];
  for (const it of items) {
    const id = String(it.id ?? "").trim();
    const url = String(it.mpd_url || "").split("?")[0];
    if (!id || !url || seen.has(id)) continue;
    seen.add(id);
    const cookie = String((it.headers && it.headers.cookie) || "").trim();
    const key = String(it.clearkey || "").trim();
    channels.push({
      id,
      name: String(it.name || "JioTV Channel").trim(),
      group: String(it.group || "General").trim(),
      logo: String(it.logo || "").trim(),
      url,
      cookie,
      key: CLEARKEY_RE.test(key) ? key : "",
      dash: url.toLowerCase().includes(".mpd"),
    });
  }

  // A few feed entries keep months-old cookies; on Jio CDNs the freshest wildcard works instead.
  const now = Date.now() / 1000;
  const wildcard = channels
    .map((c) => c.cookie)
    .filter((c) => c.includes("acl=/*"))
    .sort((a, b) => expiryOf(b) - expiryOf(a))[0] || "";
  if (expiryOf(wildcard) > now) {
    for (const ch of channels) {
      if (ch.cookie && expiryOf(ch.cookie) <= now && /\.cdn\.jio\.com\//.test(ch.url)) ch.cookie = wildcard;
    }
  }
  return channels;
}

const streamUrl = (ch) => (ch.cookie ? `${ch.url}?${ch.cookie}` : ch.url);

function buildPlaylist(channels) {
  const lines = [
    `#EXTM3U x-tvg-url="${EPG_URL}"`,
    `#DATE:- ${formatIST(new Date())}`,
    "# Category: jiotv",
    `# Total Channels: ${channels.length}`,
    "",
  ];
  for (const ch of channels) {
    lines.push(
      `#EXTINF:-1 tvg-id="${ch.id}" tvg-name="${ch.name}" tvg-logo="${ch.logo}" ` +
      `group-title="JioTV - ${ch.group}",${ch.name}`,
    );
    if (ch.dash) {
      lines.push("#KODIPROP:inputstream=inputstream.adaptive");
      lines.push("#KODIPROP:inputstream.adaptive.manifest_type=mpd");
      if (ch.key) {
        lines.push("#KODIPROP:inputstream.adaptive.license_type=clearkey");
        lines.push(`#KODIPROP:inputstream.adaptive.license_key=${ch.key}`);
      }
    }
    lines.push(`#EXTVLCOPT:http-user-agent=${USER_AGENT}`);
    const hdr = { "User-Agent": USER_AGENT, Origin: ORIGIN };
    if (ch.cookie) {
      lines.push(`#EXTVLCOPT:http-cookie=${ch.cookie}`);
      hdr.Cookie = ch.cookie;
    }
    lines.push(`#EXTHTTP:${JSON.stringify(hdr)}`);
    lines.push(streamUrl(ch));
    lines.push("");
  }
  return lines.join("\n");
}

function status(channels) {
  const now = Date.now() / 1000;
  const exps = channels.map((c) => expiryOf(c.cookie)).filter(Boolean);
  const live = exps.filter((e) => e > now);
  const soonest = live.length ? Math.min(...live) : 0;
  return {
    ok: live.length > 0 && live.length >= exps.length * 0.9,
    source: FEED_URL,
    channels: channels.length,
    withClearKey: channels.filter((c) => c.key).length,
    channelScopedTokens: channels.filter((c) => c.cookie.includes("acl=/bpk-tv/")).length,
    liveTokens: live.length,
    expiredTokens: exps.length - live.length,
    earliestTokenExpiry: soonest ? new Date(soonest * 1000).toISOString() : null,
    expiresInHours: soonest ? Number(((soonest - now) / 3600).toFixed(2)) : 0,
  };
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });

    let channels;
    try {
      channels = await loadChannels();
    } catch (e) {
      return new Response(`Upstream feed error: ${(e && e.message) || e}\n`, { status: 502, headers: CORS });
    }

    if (path === "/" || path === "/playlist.m3u" || path === "/live.m3u" || url.searchParams.has("m3u")) {
      const download = url.searchParams.has("download");
      return new Response(buildPlaylist(channels), {
        headers: {
          ...CORS,
          "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
          "Content-Disposition": `${download ? "attachment" : "inline"}; filename="jiotv.m3u"`,
          "Cache-Control": `public, max-age=${FEED_CACHE_SECONDS}`,
        },
      });
    }

    if (path === "/status" || path === "/health") {
      return Response.json(status(channels), { headers: CORS });
    }

    if (path === "/channels.json") {
      return Response.json(channels, { headers: { ...CORS, "Cache-Control": `public, max-age=${FEED_CACHE_SECONDS}` } });
    }

    // Older playlists link channels as /live/<id>.m3u8; keep those resolving.
    const m = path.match(/^\/live\/([^/.]+)(?:\.m3u8|\.mpd)?$/);
    if (m) {
      const ch = channels.find((c) => c.id === m[1]);
      if (!ch) return new Response("Unknown channel\n", { status: 404, headers: CORS });
      return new Response(null, { status: 302, headers: { ...CORS, Location: streamUrl(ch), "Cache-Control": "no-store" } });
    }

    return new Response("Not found. Use /playlist.m3u, /status or /live/<id>.m3u8\n", { status: 404, headers: CORS });
  },
};
