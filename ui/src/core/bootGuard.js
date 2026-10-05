// ui/src/core/bootGuard.js — sinkron token server↔frontend tanpa'expose token.
//
// Masalah: server restart → API_TOKEN baru → .ana_token ditulis ulang, tapi Halaman
// masih memegang <meta name="ana-token"> yang lama. Semua fetch kena 401, antrean
// /api/map/queue tak pernah kekuras, peta "diam". Dulu harus hard refresh manual.
//
// Solusi: server punya BOOT_ID (8 hex acak, baru tiap start) yang dicek lewat
// endpoint tanpa-auth /api/token-status. Halaman poll endpoint itu: boot berubah
// = ada proses server baru = token meta di halaman ini sudah basi → reload sekali.
// Token tidak pernah dikirim ke mana pun, dan tidak pernah disimpan di storage.
//
// Keamanan: BOOT_ID bukan rahasia (acak, publik, tak memberi akses apa pun).
// Token asli tetap hanya di dalam HTML render dan header X-Ana-Token.

const POLL_MS = 5000;
let _boot = null;
let _reloading = false;
let _timer = null;

async function _check() {
  let boot = null;
  try {
    const r = await fetch('/api/token-status', { cache: 'no-store' });
    if (r.ok) ({ boot } = await r.json());
  } catch (_) {
    return; // server mati / restart — tunggu poll berikutnya
  }
  if (!boot) return;
  if (_boot === null) {
    _boot = boot;
    return;
  }
  if (boot !== _boot && !_reloading) {
    // boot beda: proses server berganti. Sekali reload, state UI tidak menimpa apa pun.
    _reloading = true;
    location.reload();
  }
}

export function startBootGuard() {
  if (_timer) return;
  _check();
  _timer = setInterval(_check, POLL_MS);
}