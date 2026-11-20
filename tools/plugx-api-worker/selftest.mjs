import worker from "./src/index.js";
const env = {};
const base = "https://plugx-api.example.workers.dev";
const req = p => worker.fetch(new Request(base + p), env, {});
let fails = 0;
const ok = (n, c, e = "") => { console.log(`${c ? "PASS" : "FAIL"}  ${n}${e ? "  " + e : ""}`); if (!c) fails++; };

let r = await req("/health");
const h = await r.json();
ok("/health ok", h.ok === true && h.channels > 0, `src=${h.source} ch=${h.channels} pl=${h.playlists}`);

r = await req("/");
const idx = await r.text();
ok("index lists all playlists", (idx.match(/<li>/g) || []).length >= 17);

r = await req("/all.m3u");
let body = await r.text();
ok("all.m3u has channels", body.includes("#EXTINF") && body.includes("group-title="), `ch=${r.headers.get("x-plugx-channels")}`);
ok("all.m3u grouped by playlist", body.includes("JioHotstar |") && body.includes("JIOSTB+ |"));
ok("all.m3u has EPG", body.includes("x-tvg-url"));

r = await req("/jiostb.m3u");
body = await r.text();
ok("/jiostb.m3u by slug", r.status === 200 && body.includes("#EXTINF"), `ch=${r.headers.get("x-plugx-channels")}`);

r = await req("/p/8.m3u");
body = await r.text();
ok("/p/8.m3u by id", r.status === 200 && body.includes("#EXTINF"), `ch=${r.headers.get("x-plugx-channels")}`);

r = await req("/p/1.m3u");
body = await r.text();
ok("Hotstar header auth", body.includes("#EXTVLCOPT:http-cookie=") && body.includes("#EXTHTTP:"));
ok("Hotstar ClearKey", body.includes("license_type=clearkey"));

r = await req("/nope.m3u");
ok("unknown slug 404", r.status === 404);

console.log(fails ? `\n${fails} FAILED` : "\nALL TESTS PASSED");
process.exit(fails ? 1 : 0);
