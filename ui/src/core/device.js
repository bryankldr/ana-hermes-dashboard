// device.js — deteksi perangkat TERPUSAT (single truth).
// Dipakai tablet Android + iPad + desktop (HP jarang). Tier:
// phone <=780px, tablet 781-1180px, desktop >1180px.
// Slot layout server cuma desktop|mobile: phone+tablet = 'mobile'.
// data-device tulis tier penuh (phone|tablet|desktop) agar CSS bisa bedakan
// tablet (header tetap tampil, target sentuh besar) dari phone (drawer ☰).
const MQ_MOBILE = '(max-width: 780px)';
const MQ_TABLET = '(max-width: 1180px)';

let _mq = null;
let _mqTab = null;
try {
  _mq = window.matchMedia ? window.matchMedia(MQ_MOBILE) : null;
} catch (_) { _mq = null; }
try {
  _mqTab = window.matchMedia ? window.matchMedia(MQ_TABLET) : null;
} catch (_) { _mqTab = null; }

export function isMobile() {
  try {
    if (_mq && typeof _mq.matches === 'boolean') return _mq.matches;
  } catch (_) {}
  return window.innerWidth <= 780;
}

// Tier penuh untuk CSS: 'phone' | 'tablet' | 'desktop'.
// iPad portrait 820, landscape 1180 = tablet. Desktop >1180.
export function deviceTier() {
  try {
    if (_mq && typeof _mq.matches === 'boolean') {
      if (_mq.matches) return 'phone';
      if (_mqTab && typeof _mqTab.matches === 'boolean' && _mqTab.matches) return 'tablet';
      return 'desktop';
    }
  } catch (_) {}
  const w = window.innerWidth || 0;
  if (w <= 780) return 'phone';
  if (w <= 1180) return 'tablet';
  return 'desktop';
}

export function isCoarse() {
  try {
    if (window.matchMedia && window.matchMedia('(pointer: coarse)').matches) return true;
  } catch (_) {}
  // Laptop layar sentuh: pointer utama fine tapi maxTouchPoints > 0 —
  // target besar tak merugikan pemakai mouse, jadi hitung coarse juga.
  try {
    return (navigator.maxTouchPoints || 0) > 0;
  } catch (_) { return false; }
}

export function onViewportChange(fn) {
  if (typeof fn !== 'function') return () => {};
  const offs = [];
  try {
    window.addEventListener('resize', fn);
    offs.push(() => window.removeEventListener('resize', fn));
  } catch (_) {}
  try {
    window.addEventListener('orientationchange', fn);
    offs.push(() => window.removeEventListener('orientationchange', fn));
  } catch (_) {}
  try {
    if (window.visualViewport) {
      window.visualViewport.addEventListener('resize', fn);
      offs.push(() => window.visualViewport.removeEventListener('resize', fn));
    }
  } catch (_) {}
  try {
    if (_mq && typeof _mq.addEventListener === 'function') {
      _mq.addEventListener('change', fn);
      offs.push(() => _mq.removeEventListener('change', fn));
    } else if (_mq && typeof _mq.addListener === 'function') {
      _mq.addListener(fn);
      offs.push(() => _mq.removeListener(fn));
    }
  } catch (_) {}
  try {
    if (_mqTab && typeof _mqTab.addEventListener === 'function') {
      _mqTab.addEventListener('change', fn);
      offs.push(() => _mqTab.removeEventListener('change', fn));
    } else if (_mqTab && typeof _mqTab.addListener === 'function') {
      _mqTab.addListener(fn);
      offs.push(() => _mqTab.removeListener(fn));
    }
  } catch (_) {}
  return () => offs.forEach(off => { try { off(); } catch (_) {} });
}

export function applyDeviceFlags() {
  try {
    // Tier penuh untuk CSS; isMobile (phone saja) untuk slot layout.
    document.documentElement.dataset.device = deviceTier();
    document.documentElement.dataset.touch = isCoarse() ? 'coarse' : 'fine';
    // Performance flags untuk optimasi animasi dan polling
    document.documentElement.dataset.lowEnd = isLowEndDevice() ? 'true' : 'false';
    document.documentElement.dataset.reducedMotion = prefersReducedMotion() ? 'true' : 'false';
    document.documentElement.dataset.perfLevel = getPerformanceLevel();
  } catch (_) {}
}

// ═══ DEVICE CAPABILITY DETECTION (Performance Optimization) ═══

// Deteksi low-end device berdasarkan hardwareConcurrency dan memory
// Returns true jika perangkat dianggap low-end (CPU cores <= 4 atau RAM <= 4GB)
export function isLowEndDevice() {
  try {
    // hardwareConcurrency: jumlah logical processors (cores)
    // <= 4 dianggap low-end untuk performa-intensive apps
    const cores = navigator.hardwareConcurrency;
    if (typeof cores === 'number' && cores <= 4) return true;

    // deviceMemory: RAM dalam GB (Chrome-only, experimental)
    // <= 4GB dianggap low-end
    const memory = navigator.deviceMemory;
    if (typeof memory === 'number' && memory <= 4) return true;

    // Fallback: hanya anggap phone sebagai low-end jika tidak ada data hardware
    // Tablet dan desktop tidak dianggap low-end secara default
    if (isMobile() && typeof cores !== 'number' && typeof memory !== 'number') return true;
  } catch (_) {}
  return false;
}

// Deteksi user preference untuk reduced motion (accessibility)
// Returns true jika user minta reduced motion
export function prefersReducedMotion() {
  try {
    return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch (_) {}
  return false;
}

// Deteksi connection type untuk bandwidth-aware loading
// Returns 'slow' untuk 2G/3G, 'fast' untuk 4G+, null jika tidak tersedia
export function getConnectionType() {
  try {
    const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
    if (!conn) return null;
    if (conn.effectiveType === 'slow-2g' || conn.effectiveType === '2g' || conn.effectiveType === '3g') {
      return 'slow';
    }
    if (conn.effectiveType === '4g') return 'fast';
  } catch (_) {}
  return null;
}

// Combined performance level: 'low', 'medium', 'high'
// Digunakan untuk menentukan level animasi/polling
export function getPerformanceLevel() {
  if (prefersReducedMotion()) return 'low';
  if (isLowEndDevice()) return 'low';
  if (getConnectionType() === 'slow') return 'medium';
  return 'high';
}

// Self-check: node --input-type=module --check
if (typeof process !== 'undefined' && process.argv && process.argv[1] && String(process.argv[1]).endsWith('device.js')) {
  console.log('device.js loaded (browser module, no direct test)');
}
