/* ANA PWA service worker — universal (Chrome, Edge, Firefox, Safari, Samsung) */
// Bump versi tiap ada perubahan auth/device agar tablet/HP tak terjebak
// login.js basi (cache-first .js + loop "sesi tidak terbaca").
const CACHE = 'ana-v45-header-portrait';
const PRECACHE = [
  '/', '/index.html', '/login.html', '/login.css', '/login.js', '/landing.css',
  'assets/simoge_hero_1.png', 'assets/simoge_hero_2.png',
  'assets/logo.png', 'assets/logo-white.webp',
  'assets/backsound/playlist.json',
  'manifest.webmanifest',
  'styles/tokens.css', 'styles/hud.css', 'styles/map.css', 'vendor/xterm.css', 'vendor/leaflet/leaflet.css',
  'vendor/xterm.js', 'vendor/xterm-addon-fit.js', 'vendor/leaflet/leaflet.js',
  'vendor/protomaps/protomaps-leaflet.min.js', 'vendor/chart.js', 'vendor/pmtiles/pmtiles.js'
];
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(PRECACHE.map(u => new URL(u, self.location).href)).catch(()=>{})).then(()=>self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k=>k!==CACHE).map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
// network-first for navigations & API, cache-first for static vendor
self.addEventListener('fetch', e => {
  const req = e.request;
  const url = new URL(req.url);
  // only handle same-origin GET
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  const path = url.pathname;
  // API & token-status: never cache, pass through
  if (path.startsWith('/api/')) return;
  // HTML navigations: network-first, fallback to cache, then to /index.html
  if (req.mode === 'navigate' || path === '/' || path.endsWith('.html')) {
    e.respondWith(fetch(req).then(r => {
      const copy = r.clone();
      caches.open(CACHE).then(c=>c.put(req, copy)).catch(()=>{});
      return r;
    }).catch(()=>caches.match(req).then(m=>m||caches.match('/index.html')||caches.match('/')).then(m=>m||fetch(req))));
    return;
  }
  // backsound: cache-first + Range 206.
  // <audio> kirim Range; tanpa iris 206 browser anggap cache miss dan
  // download ulang tiap play (= streaming server). Kunci cache = URL polos
  // agar request Range dan biasa berbagi satu entri; sekali unduh = nol
  // byte server selamanya (sampai CACHE bump).
  if (path.startsWith('/assets/backsound/')) {
    e.respondWith((async () => {
      const cache = await caches.open(CACHE);
      const range = req.headers.get('range');
      const m = range && /^bytes=(\d*)-(\d*)$/.exec(range);
      const storeKey = url.href.split('#')[0];
      let full = await cache.match(storeKey);
      if (!full) {
        const res = await fetch(storeKey, { cache: 'no-store' }).catch(() => null);
        if (!res || !res.ok) return res || Response.error();
        try { await cache.put(storeKey, res.clone()); } catch {}
        full = res;
      }
      if (!m) return full;
      const buf = await full.arrayBuffer();
      const total = buf.byteLength;
      const start = m[1] === '' ? Math.max(total - parseInt(m[2] || '0', 10), 0) : parseInt(m[1], 10);
      const end = m[2] === '' ? total - 1 : Math.min(parseInt(m[2], 10), total - 1);
      if (start >= total || end < start) {
        return new Response(null, { status: 416, headers: { 'Content-Range': 'bytes */' + total } });
      }
      return new Response(buf.slice(start, end + 1), {
        status: 206,
        headers: {
          'Content-Type': full.headers.get('Content-Type') || 'audio/mpeg',
          'Content-Range': 'bytes ' + start + '-' + end + '/' + total,
          'Content-Length': String(end - start + 1),
          'Accept-Ranges': 'bytes',
        },
      });
    })());
    return;
  }
  // kode aplikasi /src: network-first + fallback cache. File ini berubah
  // tiap deploy; cache-first bikin browser menjalankan JS basi.
  if (path.startsWith('/src/') || path === '/main.js') {
    e.respondWith(fetch(req).then(r => {
      if (r.ok) { const c = r.clone(); caches.open(CACHE).then(cache=>cache.put(req,c)).catch(()=>{}); }
      return r;
    }).catch(()=>caches.match(req)));
    return;
  }
  // static assets: cache-first
  if (path.startsWith('/vendor/') || path.startsWith('/styles/') || path.startsWith('/icons/') || path.startsWith('/assets/') || path==='favicon.ico' || path.endsWith('.js') || path.endsWith('.css') || path.endsWith('.png') || path.endsWith('.woff2')) {
    e.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(r=>{
      if (r.ok) { const c = r.clone(); caches.open(CACHE).then(cache=>cache.put(req,c)).catch(()=>{}); }
      return r;
    }).catch(()=>hit)));
  }
});
