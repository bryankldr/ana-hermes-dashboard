/* ANA PWA service worker — universal (Chrome, Edge, Firefox, Safari, Samsung) */
// Bump versi tiap ada perubahan auth/device agar tablet/HP tak terjebak
// login.js basi (cache-first .js + loop "sesi tidak terbaca").
const CACHE = 'ana-v2-device';
const PRECACHE = [
  '/', '/index.html', '/login.html', '/login.css', '/login.js',
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
  // static assets: cache-first
  if (path.startsWith('/vendor/') || path.startsWith('/styles/') || path.startsWith('/icons/') || path.startsWith('/assets/') || path==='favicon.ico' || path.endsWith('.js') || path.endsWith('.css') || path.endsWith('.png') || path.endsWith('.woff2')) {
    e.respondWith(caches.match(req).then(hit=>hit||fetch(req).then(r=>{
      if (r.ok) { const c = r.clone(); caches.open(CACHE).then(cache=>cache.put(req,c)).catch(()=>{}); }
      return r;
    }).catch(()=>hit)));
  }
});
