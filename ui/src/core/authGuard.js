// authGuard.js — cek sesi sebelum HUD boot; redirect ke login jika 401 atau TFA belum aktif
// Kirim X-Ana-Device (UUID persisten localStorage) agar cek device_hash
// server deterministik — tanpa ini UA-only dan dua perangkat UA-sama lolos.
function authHeaders() {
  const h = {};
  try {
    const d = localStorage.getItem('ana_device_id') || '';
    if (/^[A-Za-z0-9_=-]{8,64}$/.test(d)) h['X-Ana-Device'] = d;
  } catch {}
  return h;
}
export async function requireAuth() {
  // Coba 2x HANYA untuk gagal jaringan (fetch throw): HTTP yang terjawab
  // (termasuk 401 expired/evicted) = keputusan final server, langsung redirect
  // tanpa retry agar semantik auth tak berubah.
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const r = await fetch('/api/auth/me', { credentials: 'same-origin', cache: 'no-store', headers: authHeaders() });
      if (r.ok) {
        const j = await r.json();
        if (j && j.authenticated) {
          if (j.user && j.user.tfa_enabled === false) {
            // force TFA setup
            const next = encodeURIComponent(location.pathname + location.search);
            location.href = '/login.html?setup2fa=1&next=' + next;
            await new Promise(()=>{});
            return null;
          }
          return j;
        }
      }
      break;
    } catch { if (attempt === 0) { await new Promise(r => setTimeout(r, 400)); continue; } }
  }
  const next = encodeURIComponent(location.pathname + location.search);
  location.href = '/login.html?next=' + next;
  await new Promise(()=>{});
  return null;
}
export function formatWilayah(user){
  if(!user) return '—';
  const divre = user.kode_divre?.divre || user.kode_divre || '';
  const kph = user.kode_kph?.kph || user.kode_kph || '';
  const bkph = user.kode_bkph?.bkph || user.kode_bkph || '';
  const jab = user.jabatan?.nama_jabatan || user.jabatan?.kode_jabatan || user.jabatan || '';
  const parts=[];
  if(jab) parts.push(String(jab));
  if(divre) parts.push(String(divre));
  if(kph) parts.push(String(kph));
  if(bkph) parts.push(String(bkph));
  return parts.join(' · ') || user.email || '—';
}
