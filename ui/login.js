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
      qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=' + encodeURIComponent(secretData.otpauth_url);
    } else if(secretData.secret){
      qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=' + encodeURIComponent('otpauth://totp/ANA:'+encodeURIComponent(emailEl.value||'user')+'?secret='+secretData.secret+'&issuer=ANA');
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
  if(user && user.tfa_enabled === false){
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
    btnLogin.textContent = 'MASUK';
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
    btnLogin.textContent = 'MASUK';
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
    btnLogin.textContent = 'MASUK';
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
    if(j.user.tfa_enabled === false){
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
  emailEl.focus();
})();
