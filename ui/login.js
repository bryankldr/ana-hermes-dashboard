// login.js — Directus login via server proxy (HttpOnly cookie). Enforce 2FA on first login.
const $ = s => document.querySelector(s);
const form = $('#loginForm');
const emailEl = $('#email');
const passEl = $('#password');
const otpEl = $('#otp');
const otpRow = $('#otpRow');
const btnLogin = $('#btnLogin');
const btnShowOtp = $('#btnShowOtp');
const msgEl = $('#msg');
const enrollBanner = $('#enrollBanner');
const qrBox = $('#qrBox');
const qrImg = $('#qrImg');
const qrSecret = $('#qrSecret');
const verifyOtp = $('#verifyOtp');
const btnVerify = $('#btnVerify');

let pendingSecret = null;
let loginPasswordCache = null; // keep password for generate after login
let enrolledMode = false;

function msg(text, cls=''){
  msgEl.textContent = text || '';
  msgEl.className = 'msg' + (cls ? ' ' + cls : '');
}
function showEnrollBanner(text){
  enrollBanner.textContent = text;
  enrollBanner.style.display = text ? 'block' : 'none';
}

btnShowOtp.addEventListener('click', ()=>{
  otpRow.classList.toggle('visible');
  if(otpRow.classList.contains('visible')) otpEl.focus();
});

async function post(path, body){
  let did = '';
  try {
    did = localStorage.getItem('ana_device_id') || '';
    if (!/^[A-Za-z0-9_=-]{8,64}$/.test(did)) {
      did = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + '-' + Math.random().toString(36).slice(2)) + '';
      did = did.replace(/[^A-Za-z0-9_=-]/g, '').slice(0, 64);
      if (did.length < 8) did = 'dev-' + Math.random().toString(36).slice(2, 14);
      localStorage.setItem('ana_device_id', did);
    }
  } catch { did = ''; }
  const headers = {'content-type':'application/json'};
  if (did) headers['X-Ana-Device'] = did;
  const r = await fetch(path, {
    method: 'POST',
    headers,
    credentials: 'same-origin',
    body: JSON.stringify(body),
  });
  let j={};
  try { j = await r.json(); } catch { j = {error: await r.text()}; }
  if (j && j.evicted) {
    try { msg('Sesi dialihkan ke perangkat ini. Chat ANNA dilanjutkan.', 'ok'); } catch {}
  }
  return {ok: r.ok, status: r.status, body: j};
}

// QR 2FA digambar LOKAL (vendor qrcode-generator, offline-first) — tanpa
// API qrserver eksternal yang diblokir adblock/jaringan kantor. Fallback
// remote hanya bila lib lokal gagal dimuat ( nyaris mustahil, same-origin).
function setQrImage(text){
  try {
    if (typeof qrcode === 'function') {
      const qr = qrcode(0, 'M');
      qr.addData(text);
      qr.make();
      qrImg.src = qr.createDataURL(6, 4);
      return;
    }
  } catch (_) {}
  qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=' + encodeURIComponent(text);
}
function enterEnrollMode(secretData){
  enrolledMode = true;
  // hide login action, show enrollment
  btnLogin.style.display = 'none';
  btnShowOtp.style.display = 'none';
  otpRow.classList.remove('visible');
  emailEl.readOnly = true;
  passEl.readOnly = true;
  showEnrollBanner('Wajib aktifkan 2FA — scan QR di Google Authenticator, lalu masukkan 6 digit untuk verifikasi. Kamu belum bisa masuk dashboard sebelum ini selesai.');
  msg('Scan QR lalu verifikasi — sesi sudah aktif tapi dashboard terkunci sampai 2FA selesai.', 'ok');
  if(secretData){
    pendingSecret = secretData.secret;
    qrSecret.textContent = secretData.secret || '';
    if(secretData.otpauth_url){
      setQrImage(secretData.otpauth_url);
    } else if(secretData.secret){
      setQrImage('otpauth://totp/ANA:'+encodeURIComponent(emailEl.value||'user')+'?secret='+secretData.secret+'&issuer=ANA');
    }
    qrBox.classList.add('visible');
    verifyOtp.focus();
  }
}

async function generateTfa(){
  const password = loginPasswordCache || passEl.value;
  if(!password){ msg('Isi password dulu untuk generate 2FA.', 'err'); return null; }
  const {ok, body} = await post('/api/auth/tfa/generate', {password});
  if(!ok){ msg(body.error || 'Gagal generate 2FA — ' + JSON.stringify(body).slice(0,200), 'err'); return null; }
  const data = body.data || body;
  return data;
}

async function handlePostLogin(user){
  // user is sanitized profile from /api/auth/me or login response
  // Bila 2FA dimatikan via env (tfa_enforced=false), enroll dilewati.
  if(user && user.tfa_enabled === false && user.tfa_enforced !== false){
    // force enrollment
    const data = await generateTfa();
    if(data) enterEnrollMode(data);
    else {
      // fallback: still show banner
      showEnrollBanner('Login berhasil tapi 2FA belum aktif — masukkan password lalu tekan AKTIFKAN 2FA.');
      msg('2FA belum aktif — selesaikan setup di bawah.', 'err');
    }
    return false; // do not redirect
  }
  return true; // allow redirect
}

form.addEventListener('submit', async (e)=>{
  e.preventDefault();
  if(enrolledMode){ msg('Selesaikan verifikasi 2FA di bawah dulu.', 'err'); return; }
  const email = emailEl.value.trim();
  const password = passEl.value;
  const otp = otpEl.value.trim() || undefined;
  if(!email || !password){ msg('Email dan password wajib.', 'err'); return; }
  btnLogin.disabled = true;
  btnLogin.textContent = 'MEMPROSES…';
  msg('');
  showEnrollBanner('');
  const {ok, status, body} = await post('/api/auth/login', otp ? {email, password, otp} : {email, password});
  if(!ok){
    if(body.error === 'otp_required' || status === 401 && String(body.message||body.error||'').toLowerCase().includes('otp')){
      otpRow.classList.add('visible');
      msg('Akun ini butuh kode Google Authenticator (6 digit).', 'err');
      otpEl.focus();
    } else {
      const detail = body.error || body.message || JSON.stringify(body).slice(0,300);
      msg(detail, 'err');
    }
    btnLogin.disabled = false;
    btnLogin.textContent = 'Masuk';
    return;
  }
  loginPasswordCache = password;
  msg('Berhasil — mengecek 2FA…', 'ok');
  const _meH = {};
  try {
    const _d = localStorage.getItem('ana_device_id') || '';
    if (/^[A-Za-z0-9_=-]{8,64}$/.test(_d)) _meH['X-Ana-Device'] = _d;
  } catch {}
  const me = await fetch('/api/auth/me', {credentials:'same-origin', headers: _meH});
  if(!me.ok){
    msg('Login berhasil tapi sesi tidak terbaca — coba refresh.', 'err');
    btnLogin.disabled = false;
    btnLogin.textContent = 'Masuk';
    return;
  }
  const meJ = await me.json();
  const user = meJ.user;
  const canEnter = await handlePostLogin(user);
  if(canEnter){
    const _next = new URLSearchParams(location.search).get('next');
    msg('Berhasil — mengalihkan…', 'ok');
    location.href = _next && _next.startsWith('/') ? _next : '/';
  } else {
    btnLogin.disabled = false;
    btnLogin.textContent = 'Masuk';
  }
});

// Verify button
btnVerify?.addEventListener('click', async ()=>{
  if(!pendingSecret){ msg('Generate QR dulu — coba refresh halaman.', 'err'); return; }
  const otp = (verifyOtp.value||'').trim();
  if(!/^\d{6}$/.test(otp)){ msg('OTP harus 6 digit.', 'err'); return; }
  btnVerify.disabled = true;
  btnVerify.textContent = 'MEMVERIFIKASI…';
  const {ok, body} = await post('/api/auth/tfa/enable', {secret: pendingSecret, otp});
  if(!ok){ msg(body.error || 'OTP salah — pastikan jam HP sinkron.', 'err'); btnVerify.disabled=false; btnVerify.textContent='AKTIFKAN'; return; }
  msg('2FA aktif — mengalihkan ke dashboard…', 'ok');
  showEnrollBanner('2FA berhasil diaktifkan. Login berikutnya wajib OTP.');
  pendingSecret=null;
  // small delay then go to dashboard
  setTimeout(()=>{ const _next = new URLSearchParams(location.search).get('next'); location.href = _next && _next.startsWith('/') ? _next : '/'; }, 700);
});

// On load: if already authenticated
// 401 evicted_by_new_device = perangkat ini ditendang login lain →
// TAMPILKAN pesan jelas + tombol ambil alih, BUKAN loop reload buta.
// Tanpa cabang ini tablet yang kena tendang reload selamanya.
(async ()=>{
  try{
    const _h = {};
    try {
      const _d = localStorage.getItem('ana_device_id') || '';
      if (/^[A-Za-z0-9_=-]{8,64}$/.test(_d)) _h['X-Ana-Device'] = _d;
    } catch {}
    const r = await fetch('/api/auth/me', {credentials:'same-origin', cache:'no-store', headers: _h});
    if(!r.ok) {
      try {
        const j = await r.clone().json();
        if (j && j.error === 'evicted_by_new_device') {
          showEnrollBanner('');
          msg('Akun ini login di perangkat lain — sesi tablet ini dialihkan. Login lagi untuk ambil alih.', 'err');
          emailEl.focus();
          return;
        }
      } catch {}
      emailEl.focus(); return;
    }
    const j = await r.json();
    if(!j.user) return;
    if(j.user.tfa_enabled === false && j.user.tfa_enforced !== false){
      // force setup even though already logged in
      emailEl.value = j.user.email || emailEl.value;
      // need password to generate — ask user
      showEnrollBanner('Akun kamu belum mengaktifkan 2FA — wajib setup sekarang. Masukkan password lalu sistem akan tampilkan QR.');
      // if password field already filled, auto-generate; otherwise wait for user to fill and click generate
      // Add helper button if not already
      if(!document.getElementById('btnGenTfa')){
        const b = document.createElement('button');
        b.id='btnGenTfa'; b.type='button'; b.className='btn btn-primary'; b.textContent='TAMPILKAN QR';
        b.style.marginTop='10px'; b.style.width='100%';
        b.onclick = async ()=>{ loginPasswordCache = passEl.value; const d = await generateTfa(); if(d) enterEnrollMode(d); };
        form.appendChild(b);
      }
      // If URL has ?setup2fa or coming from dashboard guard, focus password
      passEl.focus();
      return;
    }
    // already has 2FA and is authenticated -> go to dashboard (unless staying on login for setup)
    const params = new URLSearchParams(location.search);
    if(!params.has('setup2fa') && !enrolledMode){
      const _next = params.get('next');
      location.href = _next && _next.startsWith('/') ? _next : '/';
    }
  }catch{}
  // Tautan switch-QR basi/bekas: beri pesan jujur (bukan diam).
  try {
    if (new URLSearchParams(location.search).get('err') === 'switch') {
      msg('Tautan pindah kedaluwarsa/terpakai — minta QR baru di perangkat asal.', 'err');
    }
  } catch {}
  emailEl.focus();
})();

// ── KULIT LANDING (aturan keras #1: NOL sentuh logika auth di atas) ──
// Murni DOM: toggle lihat password, ingat-email (localStorage, bukan
// password/token), reveal halus, link lupa → pesan admin. Blok ini boleh
// dihapus total tanpa pengaruhi login/OTP/enroll/evict.
try {
  const pwT = document.getElementById('pwToggle');
  pwT?.addEventListener('click', () => {
    const show = passEl.type === 'password';
    passEl.type = show ? 'text' : 'password';
    pwT.textContent = show ? '🙈' : '👁';
    pwT.setAttribute('aria-label', show ? 'Sembunyikan password' : 'Tampilkan password');
    passEl.focus();
  });
  const rem = document.getElementById('rememberEmail');
  try {
    if (rem && localStorage.getItem('ana_remember_email') === '1') {
      rem.checked = true;
      emailEl.value = localStorage.getItem('ana_saved_email') || emailEl.value;
    }
  } catch {}
  rem?.addEventListener('change', () => {
    try {
      localStorage.setItem('ana_remember_email', rem.checked ? '1' : '0');
      if (rem.checked) localStorage.setItem('ana_saved_email', emailEl.value.trim());
      else localStorage.removeItem('ana_saved_email');
    } catch {}
  });
  emailEl?.addEventListener('input', () => {
    try { if (rem?.checked) localStorage.setItem('ana_saved_email', emailEl.value.trim()); } catch {}
  });
  // ── Backsound shuffle hemat (robust, tanpa hardcode, tanpa streaming). Default ON + cache permanen.
  // Sumber: assets/backsound/playlist.json (5 lagu terpanjang, 48kbps mono ~4.4MB).
  // Pola: 1 lagu penuh → jeda acak 90–180 dtk → lagu berikut (tas acak,
  // tak ulang sebelum semua kepakai). preload 'metadata' = cuma header
  // durasi yang diunduh saat antre, full byte hanya lagu berjalan.
  // Hemat: volume 0.5, pause saat tab hidden, OFF = src dikosongkan
  // (buffer dilepas). Nol byte sebelum user nyalakan. Gagal = OFF + pesan.
  // Ratusan user: jitter 0–20 dtk pecah herd jam-masuk + Save-Data = default
  // OFF (tablet kuota tak tersedot).
  try {
    const snd = document.getElementById('bgSound');
    const tgl = document.getElementById('soundToggle');
    const box = tgl?.closest('.ref-sound');
    let bag = [], timer = 0, loading = false, failCount = 0;
    // Default ON (permintaan user); preferensi tersimpan ana_sound (1/0).
    // Save-Data (tablet kuota/metered) = paksa default OFF walau belum pilih.
    let wantOn = true;
    try {
      const saved = localStorage.getItem('ana_sound');
      const saveData = navigator.connection && navigator.connection.saveData;
      wantOn = saved !== null ? saved !== '0' : !saveData;
    } catch {}
    const GAP_MIN = 90, GAP_MAX = 180;
    const gapMs = () => (GAP_MIN + Math.random() * (GAP_MAX - GAP_MIN)) * 1000;
    const shuffle = (a) => {
      for (let i = a.length - 1; i > 0; i--) {
        const k = (Math.random() * (i + 1)) | 0;
        [a[i], a[k]] = [a[k], a[i]];
      }
      return a;
    };
    async function nextTrack() {
      if (!wantOn || !snd) return;
      try {
        if (!bag.length) {
          const r = await fetch('assets/backsound/playlist.json', { cache: 'force-cache' });
          const j = await r.json();
          bag = shuffle((j.tracks || []).slice());
          if (!bag.length) throw new Error('playlist kosong');
        }
        loading = true;
        snd.preload = 'metadata';
        snd.src = 'assets/backsound/lo/' + encodeURIComponent(bag.pop());
        snd.volume = 0.5;
        await snd.play();
        loading = false;
        failCount = 0; // sukses = reset penghitung gagal
      } catch (e) {
        loading = false;
        if (e && e.name === 'NotAllowedError' && wantOn) {
          // Autoplay diblokir browser: toggle tetap ON, mulai di gestur pertama.
          const retry = () => {
            document.removeEventListener('pointerdown', retry);
            document.removeEventListener('keydown', retry);
            if (wantOn) nextTrack();
          };
          document.addEventListener('pointerdown', retry);
          document.addEventListener('keydown', retry);
          return;
        }
        // v5.3: default ON itu janji — gagal = TUNGGU + coba lagi, JANGAN
        // off otomatis. Backoff 30 dtk → 1 → 2 → 5 → 10 mnt (hemat, bukan
        // spam). Hanya OFF bila user mematikan manual via toggle.
        failCount++;
        const backoff = [30000, 60000, 120000, 300000, 600000][Math.min(failCount - 1, 4)];
        clearTimeout(timer);
        timer = setTimeout(() => { if (wantOn) nextTrack(); }, backoff);
      }
    }
    function setOff() {
      wantOn = false;
      clearTimeout(timer);
      try { snd?.pause(); if (snd) { snd.removeAttribute('src'); snd.load(); } } catch {}
      bag = [];
      tgl?.setAttribute('aria-pressed', 'false');
      box?.classList.remove('playing');
    }
    snd?.addEventListener('ended', () => {
      if (!wantOn) return;
      box?.classList.remove('playing');
      clearTimeout(timer);
      timer = setTimeout(() => { if (wantOn) nextTrack(); }, gapMs());
    });
    // Wave = sedang bunyi (bukan sekadar toggle ON): mati saat jeda antar lagu.
    snd?.addEventListener('play', () => box?.classList.add('playing'));
    snd?.addEventListener('pause', () => box?.classList.remove('playing'));
    // Tab disembunyikan = pause hemat (stream lanjut = bandwidth bocor).
    document.addEventListener('visibilitychange', () => {
      if (!wantOn || !snd) return;
      try {
        if (document.hidden && !snd.paused) snd.pause();
        else if (!document.hidden && snd.paused && snd.src && !loading) snd.play().catch(() => {});
      } catch {}
    });
    tgl?.addEventListener('click', async () => {
      if (!snd) return;
      try {
        if (!wantOn) {
          wantOn = true;
          try { localStorage.setItem('ana_sound', '1'); } catch {}
          tgl.setAttribute('aria-pressed', 'true');
          nextTrack();
        } else {
          try { localStorage.setItem('ana_sound', '0'); } catch {}
          setOff();
        }
      } catch { setOff(); }
    });
    // Default ON: coba autoplay saat load (diblokir = tunggu gestur, toggle tetap ON).
    // Jitter 0–20 dtk: ratusan user buka 08:00 tak fetch bareng (= pecah herd).
    if (wantOn && snd && tgl) {
      tgl.setAttribute('aria-pressed', 'true');
      setTimeout(() => { if (wantOn) nextTrack(); }, Math.random() * 20000);
    } else if (snd && tgl) {
      tgl.setAttribute('aria-pressed', 'false');
    }
  } catch {}
  document.getElementById('forgotLink')?.addEventListener('click', (e) => {
    e.preventDefault();
    msg('Minta reset password ke admin KPHBWB — belum ada reset mandiri.', '');
  });
  // ── Insight Engine v2: rotasi slides + live refresh + news dinamis.
  // Tanpa token/sesi (endpoint publik). Gagal = placeholder + note jujur.
  // Blok auth di atas tak tersentuh blok ini.
  // XSS: textContent + createElement untuk semua string server; innerHTML
  // hanya path SVG dari Number() — tak ada string server mentah.
  // Rotasi: tiap kartu ganti slide tiap 8–10 dtk (titik dots), hormati
  // reduced-motion (rotasi mati) + tab hidden (pause, hemat).
  // Live: refresh snapshot tiap 60 dtk bila tab terlihat; ganti DOM hanya
  // bila generated_at berubah (tanpa refresh halaman, ala bursa).
  (() => {
    const note = document.getElementById('insightNote');
    const fmt = (n) => Number(n || 0).toLocaleString('id-ID');
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    const dots = (id, i, n) => {
      const box = document.getElementById(id);
      if (!box) return;
      // v4: dots dibangun dinamis sejumlah slides (tiap card ≥5).
      if (n && box.childElementCount !== n) {
        box.innerHTML = '';
        for (let k = 0; k < n; k++) box.appendChild(document.createElement('i'));
      }
      box.querySelectorAll('i').forEach((d, k) => d.classList.toggle('on', k === i));
    };
    const reduceMotion = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let lastGen = '', rotTimers = [];
    function stopRot() { rotTimers.forEach(clearInterval); rotTimers = []; }
    // Fade halus: tambah .out, ganti isi di tengah, lepas .out.
    function fadeSwap(el, fn) {
      if (!el || reduceMotion()) { fn(); return; }
      el.classList.add('out');
      setTimeout(() => { fn(); el.classList.remove('out'); }, 230);
    }
    // Painter chart SVG generik (tanpa dependensi): line|bar|hbar|donut.
    // XSS-aman: semua angka via Number(), label via textContent <text>.
    const PAL = ['#00D09C', '#0EA5E9', '#F59E0B', '#8B5CF6', '#EF4444', '#64748B', '#14B8A6', '#F97316', '#06B6D4'];
    function escXml(s) { return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
    function paintChart(svg, chart, W, H) {
      if (!svg || !chart) return;
      const labels = chart.labels || [], dss = chart.datasets || [];
      const nums = [];
      dss.forEach((d) => (d.data || []).forEach((v) => nums.push(Number(v) || 0)));
      const max = Math.max(...nums, 1);
      // v4.4: palet bar bermakna + angka pendek — dipakai hbar & bar.
      // Hijau = nilai utama (konsisten), emas = highlight (peringkat 1 /
      // sorotan), abu = muted (sisa/susut). Tanpa keduanya = semua hijau.
      // v5: colors dari engine (warna ambang capaian) mengalahkan ketiganya.
      const COL_MAIN = '#059669', COL_HI = '#D97706', COL_MUT = '#CBD5E1';
      const shortV = (v) => v >= 1e6 ? ((Math.round(v / 1e4) / 100) + ' jt')
        : v >= 1000 ? ((Math.round(v / 100) / 10) + ' rb') : fmt(v);
      const barCol = (i) => ((chart.colors || [])[i])
        || ((chart.highlight === i) ? COL_HI
        : ((chart.muted || []).indexOf(i) >= 0 ? COL_MUT : COL_MAIN));
      let inner = '';
      if (chart.ctype === 'hbar') {
        // v4.4: (1) batang penuh — kolom label ramping 30%, 95% sisa utk
        // bar; (2) satu warna hijau + emas utk peringkat 1 / sorotan;
        // (3) urut besar→kecil dari engine; skala = max aktual.
        const LAB = Math.min(100, Math.round(W * 0.3));
        const n = Math.max(labels.length, 1), bh = (H - 10) / n;
        labels.forEach((lb, i) => {
          const v = Number((dss[0] && dss[0].data[i]) || 0);
          const sv = shortV(v);
          const w = Math.max((v / max) * (W - LAB - 10) * 0.95, 3);
          const lx = Math.min(LAB + 4 + w, W - sv.length * 5.2 - 2);
          const yy = 5 + i * bh;
          inner += '<text x="0" y="' + (yy + bh / 2 + 3).toFixed(1) + '" font-size="8" fill="#475569">' + escXml(String(lb).slice(0, 12)) + '</text>'
            + '<rect x="' + LAB + '" y="' + (yy + 1).toFixed(1) + '" width="' + w.toFixed(1) + '" height="' + Math.max(bh - 2, 5).toFixed(1) + '" rx="2.5" fill="' + barCol(i) + '"/>'
            + '<text x="' + lx.toFixed(1) + '" y="' + (yy + bh / 2 + 3).toFixed(1) + '" font-size="7.5" font-weight="700" fill="#334155">' + escXml(sv) + '</text>';
        });
      } else if (chart.ctype === 'bar') {
        // v4.4: sama — satu warna + sorotan, label nilai di ujung,
        // batang penuh (jarak = 18% slot), urut dari engine.
        const n = Math.max(labels.length, 1), bw = (W - 10) / n;
        inner += '<line x1="5" y1="' + (H - 5).toFixed(1) + '" x2="' + (W - 5).toFixed(1) + '" y2="' + (H - 5).toFixed(1) + '" stroke="#CBD5E1" stroke-width="1"/>';
        [0.5, 1].forEach((f) => {
          const gy = (H - 5 - f * (H - 26)).toFixed(1);
          inner += '<line x1="5" y1="' + gy + '" x2="' + (W - 5).toFixed(1) + '" y2="' + gy + '" stroke="#E2E8F0" stroke-width="0.5" stroke-dasharray="2 2"/>';
        });
        labels.forEach((lb, i) => {
          const v = Number((dss[0] && dss[0].data[i]) || 0);
          const h = Math.max((v / max) * (H - 30), 3);
          const bw2 = Math.max(bw * 0.82, 4), bx = 5 + i * bw + (bw - bw2) / 2;
          inner += '<rect x="' + bx.toFixed(1) + '" y="' + (H - 5 - h).toFixed(1) + '" width="' + bw2.toFixed(1) + '" height="' + h.toFixed(1) + '" rx="2.5" fill="' + barCol(i) + '"><title>' + escXml(lb) + ': ' + fmt(v) + '</title></rect>'
            + '<text x="' + (bx + bw2 / 2).toFixed(1) + '" y="' + (H - 9 - h).toFixed(1) + '" font-size="7" font-weight="700" fill="#334155" text-anchor="middle">' + escXml(shortV(v)) + '</text>';
        });
      } else if (chart.ctype === 'scatter') {
        // Peta scatter nyata v4: titik petak posisi 0-100 + bingkai peta.
        // v5: tiap titik bawa warna ambang capaian wilayahnya (p.c) —
        // merah/kuning/oranye/hijau/biru = arti bisnis langsung.
        const pts = chart.points || [];
        // Legenda ambang = dari backend (chart.legend, sumber tunggal
        // _ach_legend). LEG bawah hanya fallback snapshot lama.
        const LEG = [['0–50', '#DC2626'], ['51–75', '#CA8A04'], ['76–99', '#EA580C'], ['100–110', '#059669'], ['111+', '#2563EB']];
        const leg = (Array.isArray(chart.legend) && chart.legend.length ? chart.legend.map((l) => [l.range, l.color]) : LEG)
          .filter((lg) => typeof lg[0] === 'string' && /^#[0-9A-Fa-f]{6}$/.test(lg[1] || ''));
        inner += '<rect x="2" y="2" width="' + (W - 4) + '" height="' + (H - 4) + '" rx="6" fill="rgba(236,253,245,.6)" stroke="#A7F3D0" stroke-width="1"/>';
        // garis lintang/bujur tipis ala peta
        [0.25, 0.5, 0.75].forEach((f) => {
          inner += '<line x1="' + (2 + f * (W - 4)).toFixed(1) + '" y1="2" x2="' + (2 + f * (W - 4)).toFixed(1) + '" y2="' + (H - 2) + '" stroke="#D1FAE5" stroke-width="0.5"/>';
          inner += '<line x1="2" y1="' + (2 + f * (H - 4)).toFixed(1) + '" x2="' + (W - 2) + '" y2="' + (2 + f * (H - 4)).toFixed(1) + '" stroke="#D1FAE5" stroke-width="0.5"/>';
        });
        pts.forEach((p) => {
          const cx = 2 + (Number(p.x) || 0) / 100 * (W - 4);
          const cy = 2 + (Number(p.y) || 0) / 100 * (H - 4);
          const rr = Math.min(2 + Math.sqrt(Number(p.luas) || 1) / 12, 5);
          const pc = /^#[0-9A-Fa-f]{6}$/.test(p.c || '') ? p.c : '#059669';
          inner += '<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="' + rr.toFixed(1) + '" fill="' + pc + '" opacity="0.8"><title>' + escXml(p.nama || '') + ' · ' + fmt(p.luas) + ' ha</title></circle>';
        });
        leg.forEach((lg, i) => {
          const lx0 = 6 + i * 33;
          inner += '<rect x="' + lx0 + '" y="' + (H - 13) + '" width="6" height="6" rx="1.5" fill="' + lg[1] + '"/><text x="' + (lx0 + 8) + '" y="' + (H - 7) + '" font-size="6" fill="#475569">' + escXml(lg[0]) + '</text>';
        });
        inner += '<text x="' + (W - 6) + '" y="' + (H - 15) + '" font-size="7" fill="#059669" text-anchor="end">' + pts.length + ' petak</text>';
      } else if (chart.ctype === 'donut') {
        const data = (dss[0] && dss[0].data) || [];
        const tot = data.reduce((a, b) => a + (Number(b) || 0), 0) || 1;
        let a0 = -Math.PI / 2;
        const R = 34, cx = 45, cy = H / 2;
        data.forEach((vv, i) => {
          const v = Number(vv) || 0;
          const a1 = a0 + (v / tot) * Math.PI * 2;
          const big = (a1 - a0) > Math.PI ? 1 : 0;
          inner += '<path d="M' + cx + ',' + cy + ' L' + (cx + R * Math.cos(a0)).toFixed(1) + ',' + (cy + R * Math.sin(a0)).toFixed(1)
            + ' A' + R + ',' + R + ' 0 ' + big + ' 1 ' + (cx + R * Math.cos(a1)).toFixed(1) + ',' + (cy + R * Math.sin(a1)).toFixed(1) + ' Z" fill="' + PAL[i % PAL.length] + '" opacity="0.9"><title>' + escXml(labels[i] || '') + ': ' + fmt(v) + '</title></path>';
          a0 = a1;
        });
        labels.forEach((lb, i) => {
          inner += '<rect x="95" y="' + (10 + i * 14) + '" width="8" height="8" rx="2" fill="' + PAL[i % PAL.length] + '"/><text x="107" y="' + (17 + i * 14) + '" font-size="8" fill="#475569">' + escXml(String(lb).slice(0, 18)) + '</text>';
        });
      } else {
        // line (default): tiap dataset satu polyline + titik.
        // v5: colors per-dataset dari engine (mis. "Rencana" = warna
        // ambang capaian) mengalahkan palet generik.
        const n = Math.max(labels.length - 1, 1);
        dss.forEach((d, di) => {
          const col = (chart.colors || [])[di] || PAL[di % PAL.length];
          const pts = (d.data || []).map((v, i) => [(i * (W - 10) / n + 5), H - 8 - (Number(v) || 0) / max * (H - 18)]);
          if (pts.length > 1) {
            inner += '<polyline points="' + pts.map((p) => p[0].toFixed(1) + ',' + p[1].toFixed(1)).join(' ') + '" fill="none" stroke="' + col + '" stroke-width="2"/>';
            pts.forEach((p) => { inner += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="2" fill="' + col + '"/>'; });
          }
        });
      }
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
      svg.innerHTML = inner;
    }
    function rankList(olId, rows) {
      const ol = document.getElementById(olId);
      if (!ol) return;
      ol.innerHTML = '';
      if (!rows || !rows.length) { ol.hidden = true; return; }
      ol.hidden = false;
      // v4: ≤3 baris + "lainnya" datang dari engine (_rank3); tampilkan
      // nilai pendek: "468 rb kg · 35%" agar teks tak kepanjangan.
      const shortKg = (v) => v == null ? '' : (v >= 1000 ? (Math.round(v / 100) / 10 + ' rb') : fmt(v));
      for (const it of rows.slice(0, 4)) {
        const li = document.createElement('li');
        if (it.kg == null) { li.textContent = it.nama || '—'; }
        else {
          li.textContent = (it.nama || '—') + ' ';
          const bb = document.createElement('b');
          bb.textContent = shortKg(it.kg) + ' kg' + (it.pct != null ? ' · ' + it.pct + '%' : '');
          // Warna teks ikut ambang bisnis dari backend (it.c) — tanpa
          // logika ambang di frontend. Tanpa c = hijau default CSS.
          // attn (zona merah/kuning backend) = denyut lembut.
          if (/^#[0-9A-Fa-f]{6}$/.test(it.c || '')) bb.style.color = it.c;
          bb.classList.toggle('attn', it.attn === true);
          li.appendChild(bb);
        }
        ol.appendChild(li);
      }
    }
    async function load() {
      try {
        const r = await fetch('/api/public/landing-insights', { cache: 'no-store' });
        const j = await r.json().catch(() => ({}));
        if (!r.ok || !j || j.status !== 'ok' || !Array.isArray(j.cards)) throw new Error(j?.error || ('HTTP ' + r.status));
        if (j.generated_at && j.generated_at === lastGen) return; // snapshot sama = tanpa sentuh DOM
        lastGen = j.generated_at || '';
        stopRot();
        const by = {};
        for (const c of j.cards) by[c.domain] = c;
        const prod = by.production || {}, sup = by.supply || {}, opt = by.optimization || {};
        set('insVer0', opt.metric_version || '');
        set('insVer1', prod.metric_version || '');
        set('insVer3', sup.metric_version || '');
        set('insNewsPeriode', (opt.period?.start || '').slice(0, 7) + '–' + (opt.period?.end || '').slice(0, 7));
        set('insPeriode', (prod.period?.start || '').slice(0, 7) + '–' + (prod.period?.end || '').slice(0, 7));
        // ── Papan skor hero kanan: YTD + periode + hari ini (GLOBAL, cron) ──
        // Warna soft ambang capaian; nol = data tertunda, tulis jujur.
        try {
          const sb = j.scoreboard || null;
          const box = document.getElementById('heroScore');
          if (sb && box) {
            box.hidden = false;
            // Nilai Ton 2 desimal di <b> saja (satuan "ton" sudah di markup,
            // ala ref: angka putih besar + unit kecil). Tahun/periode dari snapshot.
            const ton = (kg) => (Number(kg || 0) / 1000).toLocaleString('id-ID', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            // Warna = 1 sumber (backend capaian_color dari _ach_color).
            // Tanpa tabel ambang di frontend: YTD pakai --ach, P1/Hari ini
            // volume murni = netral (bukan capaian, tanpa warna semu).
            const isHex = (h) => /^#[0-9A-Fa-f]{6}$/.test(h || '');
            set('sbYtdV', ton(sb.ytd_kg || 0));
            set('sbYtdS', 'capaian ' + (sb.capaian_pct ?? '—') + '%');
            const ytdCard = document.getElementById('sbYtd');
            if (ytdCard && isHex(sb.capaian_color)) {
              ytdCard.style.setProperty('--ach', sb.capaian_color);
            }
            // YTD di bawah 75% (flag backend) = denyut perhatian.
            ytdCard?.classList.toggle('attn', sb.ytd_attention === true);
            const half = sb.periode_half || (/P2/.test(sb.periode_label || '') ? 2 : 1);
            set('sbPerLb', half === 2 ? 'P2' : 'P1');
            // Nol = data tertunda (aturan keras #2): tulis jujur + tandai
            // kartu .is-stale (amber + ⚠ via CSS) + tooltip aksesibilitas.
            const perCard = document.getElementById('sbPerCard');
            const tdCard = document.getElementById('sbTdCard');
            const perStale = !((sb.periode_kg || 0) > 0);
            const tdStale = !((sb.hari_kg || 0) > 0);
            if (perStale) {
              set('sbPerV', 'tertunda');
              set('sbPerS', 'terbaru ' + (sb.data_terbaru || '—'));
            } else {
              set('sbPerV', ton(sb.periode_kg));
              set('sbPerS', fmt(sb.periode_n || 0) + ' terima');
            }
            if (tdStale) {
              set('sbTdV', 'tertunda');
              set('sbTdS', 'terbaru ' + (sb.data_terbaru || '—'));
            } else {
              set('sbTdV', ton(sb.hari_kg));
              set('sbTdS', fmt(sb.hari_n || 0) + ' terima');
            }
            perCard?.classList.toggle('is-stale', perStale);
            tdCard?.classList.toggle('is-stale', tdStale);
            // Tertunda selalu jadi perhatian (denyut amber) — status,
            // bukan ambang capaian, jadi tanpa flag backend.
            perCard?.classList.toggle('attn', perStale);
            tdCard?.classList.toggle('attn', tdStale);
            if (perCard && perStale) perCard.title = 'Data periode tertunda — terbaru ' + (sb.data_terbaru || '—');
            else if (perCard) perCard.removeAttribute('title');
            if (tdCard && tdStale) tdCard.title = 'Data hari ini tertunda — terbaru ' + (sb.data_terbaru || '—');
            else if (tdCard) tdCard.removeAttribute('title');
          }
        } catch {}
        // ── v4: tiap slide WAJIB chart (50/50). Peta lama & insWil dibuang. ──
        const psl = prod.slides || [];
        const paintProd = (i) => {
          const s = psl[i];
          if (!s) return;
          const body = document.getElementById('cardProd')?.querySelector('.ref-card-body');
          fadeSwap(body, () => {
            set('insProdKick', s.title || '');
            set('insProdTitle', s.headline || prod.title || '');
            set('insAktSub', s.sub || '');
            if (s.kind === 'rank') rankList('insRank', s.rows);
            else { const ol = document.getElementById('insRank'); if (ol) ol.hidden = true; }
            // v5: badge + headline ikut warna ambang capaian slide
            // (ach_color) — arti persen langsung terbaca di teks juga.
            // attn (backend, zona merah/kuning) = denyut lembut.
            if (s.ach_color && /^#[0-9A-Fa-f]{6}$/.test(s.ach_color)) {
              const b = document.getElementById('insAkt');
              if (b) { b.style.background = s.ach_color + '22'; b.style.color = s.ach_color; b.classList.toggle('attn', s.attn === true); }
              const h = document.getElementById('insProdTitle');
              if (h) { h.style.color = s.ach_color; h.classList.toggle('attn', s.attn === true); }
            } else {
              const b = document.getElementById('insAkt');
              if (b) { b.style.background = ''; b.style.color = ''; b.classList.remove('attn'); }
              const h = document.getElementById('insProdTitle');
              if (h) { h.style.color = ''; h.classList.remove('attn'); }
            }
            set('insAkt', (prod.value ?? '—') + (prod.unit || '%'));
            if (s.chart) paintChart(document.getElementById('insSpark'), Object.assign({}, s.chart, {highlight: s.highlight, muted: s.muted, colors: s.chart && s.chart.colors, achColor: s.ach_color}), 200, 132);
            dots('insProdDots', i, psl.length);
          });
        };
        // ── Kartu SUPPLY: rotasi [alur, tren 3-seri, efisiensi ×2, rencana ×2] ──
        // ach_color slide (mis. "Rencana vs target") diwarnai sama seperti
        // kartu PRODUKSI: headline + dataset garis pertama. Tanpa ach =
        // netral (volume/rasio, bukan capaian). Tanpa logika ambang di sini.
        const ssl = sup.slides || [];
        const paintSup = (i) => {
          const s = ssl[i];
          if (!s) return;
          const body = document.getElementById('cardSupply')?.querySelector('.ref-card-body');
          fadeSwap(body, () => {
            set('insSupKick', s.title || '');
            set('insSupplyTitle', s.headline || sup.title || '');
            set('insWilSub', s.sub || '');
            set('insPetakSub', 'Dihitung ' + (sup.calculated_at || '—') + ' · ' + (sup.sumber || ''));
            const achOk = /^#[0-9A-Fa-f]{6}$/.test(s.ach_color || '');
            const h = document.getElementById('insSupplyTitle');
            if (h) { h.style.color = achOk ? s.ach_color : ''; h.classList.toggle('attn', s.attn === true); }
            const ch = s.chart ? Object.assign({}, s.chart, {highlight: s.highlight, muted: s.muted, achColor: s.ach_color}) : null;
            if (ch && !ch.colors && achOk) ch.colors = [s.ach_color];
            else if (ch && s.chart && s.chart.colors) ch.colors = s.chart.colors;
            if (ch) paintChart(document.getElementById('insSupChart'), ch, 200, 132);
            dots('insSupDots', i, ssl.length);
          });
        };
        // ── Kartu NEWS: struktur 1:1 kartu PRODUKSI/SUPPLY (head + split + tren).
        // Kicker = judul slide, headline = angka, badge = nilai domain,
        // rank pakai helper rankList yang sama (tanpa bangun <ol> dinamis). ──
        const nsl = opt.slides || [];
        const paintNews = (i) => {
          const s = nsl[i];
          if (!s) return;
          const body = document.getElementById('cardNews')?.querySelector('.ref-card-body');
          fadeSwap(body, () => {
            set('insNewsKick', s.title || '');
            set('insNewsTitle', s.headline || opt.title || '');
            set('insNewsSub', s.sub || '');
            if (s.kind === 'rank') rankList('insNewsRank', s.rows);
            else { const rl = document.getElementById('insNewsRank'); if (rl) rl.hidden = true; }
            set('insNewsBadge', fmt(opt.value ?? 0) + ' ' + (opt.unit || 'petak'));
            set('insNewsMeta', (opt.calculated_at || '—').slice(5) + (opt.freshness === 'stale' ? ' · tertunda' : ' · kini'));
            if (s.chart) paintChart(document.getElementById('insNewsMap'), Object.assign({}, s.chart, {highlight: s.highlight, muted: s.muted, colors: s.chart && s.chart.colors, achColor: s.ach_color}), 200, 132);
            dots('insNewsDots', i, nsl.length);
          });
        };
        // ── Strip bawah: switch otomatis tren ⇄ korelasi (12 dtk) ──
        const k5 = by.kphstrip || {};
        const ksl = k5.slides || [];
        const paintKph = (i) => {
          const s = ksl[i];
          if (!s) return;
          const strip = document.getElementById('kphStrip');
          if (strip) strip.hidden = false;
          set('insVer5', k5.metric_version || '');
          set('insKphKick', s.title || '');
          set('insKphTitle', s.headline || k5.title || '');
          set('insKphSub', (s.sub || '') + ' · Terbaru ' + (k5.data_terbaru || '—') + ' · ' + (k5.sumber || ''));
          if (s.chart) paintChart(document.getElementById('insKphChart'), Object.assign({}, s.chart, {highlight: s.highlight, muted: s.muted, colors: s.chart && s.chart.colors, achColor: s.ach_color}), 600, 110);
          dots('insKphDots', i, ksl.length);
        };
        // Sub tetap (summary + hitung + lapangan).
        set('insAktSub', (prod.summary || '') + ' · ' + (prod.sumber || ''));
        // v4.3: teks footer pendek (MM-DD + status) agar muat penuh tanpa ellipsis.
        set('insGen', (prod.calculated_at || '—').slice(5) + (prod.freshness === 'stale' ? ' · tertunda' : ' · kini'));
        set('insPetakSub', 'Dihitung ' + (sup.calculated_at || '—') + ' · ' + (sup.sumber || ''));
        // (v4.1: kartu produksi murni domain produksi — teks lapangan
        //  insFieldExtra yang dulu nyasar ke sini sudah dibuang.)
        // (sparkline produksi kini digambar via paintChart dari slide.chart —
        //  blok painter lama yang menimpa tiap load sudah dibuang.)
        // Paint awal + rotasi (mati bila reduced-motion).
        let pi = 0, si = 0, ni = 0, ki = 0;
        paintProd(0); paintSup(0); paintNews(0); paintKph(0);
        if (!reduceMotion()) {
          if (psl.length > 1) rotTimers.push(setInterval(() => {
            if (document.hidden) return;
            pi = (pi + 1) % psl.length; paintProd(pi);
          }, 8000));
          if (ssl.length > 1) rotTimers.push(setInterval(() => {
            if (document.hidden) return;
            si = (si + 1) % ssl.length; paintSup(si);
          }, 9000));
          if (nsl.length > 1) rotTimers.push(setInterval(() => {
            if (document.hidden) return;
            ni = (ni + 1) % nsl.length; paintNews(ni);
          }, 10000));
          // Strip bawah: switch otomatis tren ⇄ korelasi tiap 12 dtk.
          if (ksl.length > 1) rotTimers.push(setInterval(() => {
            if (document.hidden) return;
            ki = (ki + 1) % ksl.length; paintKph(ki);
          }, 12000));
        }
        if (note) note.textContent = 'Data operasional live.';
      } catch (e) {
        const b = document.getElementById('insAkt');
        if (b) b.textContent = 'n/a';
        if (note) note.textContent = 'Data operasional belum tersedia — login tetap berfungsi.';
      }
    }
    load();
    // Live refresh 60 dtk bila terlihat (tanpa reload halaman).
    setInterval(() => { if (!document.hidden) load(); }, 60000);
  })();
  // ── Tahap 5: reveal halus + parallax hero (kulit saja).
  // transform/opacity saja; mati bila prefers-reduced-motion (CSS).
  try {
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.querySelectorAll('.ref-reveal').forEach((el) => el.classList.add('in'));
    } else if ('IntersectionObserver' in window) {
      const io = new IntersectionObserver((es) => es.forEach((en) => {
        if (en.isIntersecting) { en.target.classList.add('in'); io.unobserve(en.target); }
      }), { threshold: 0.12 });
      document.querySelectorAll('.ref-reveal').forEach((el) => io.observe(el));
    } else {
      document.querySelectorAll('.ref-reveal').forEach((el) => el.classList.add('in'));
    }
    // Parallax hero: geser latar sangat subtil saat scroll (rAF-throttle).
    let tick = false;
    const bg = document.querySelector('.ref-bg');
    window.addEventListener('scroll', () => {
      if (tick || !bg) return;
      tick = true;
      requestAnimationFrame(() => {
        tick = false;
        if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        bg.style.transform = 'translateY(' + Math.min(window.scrollY * 0.08, 60) + 'px)';
      });
    }, { passive: true });
  } catch {}
} catch {}
