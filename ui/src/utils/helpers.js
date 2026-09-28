// utils/helpers.js — single source for HUD helpers
// Import this instead of redefining now/rid/esc/cleanForSpeech in each component.
// ponytail: keep tiny, no dep; add formatDate etc only when needed.
export const now = () => new Date().toLocaleTimeString('en-GB', { hour12: false });
export const rid = () => 'run_' + (crypto.randomUUID ? crypto.randomUUID().replace(/-/g,'').slice(0,24) : Math.random().toString(16).slice(2,14));
// Quotes matter as much as angle brackets: this is used inside attribute values
// (data-path="…", title="…") and a path is picked up from the filesystem, so a
// directory named x" onmouseover="… would otherwise break out of the attribute.
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export function cleanForSpeech(text){
  return String(text||'').replace(/\x1b\[[0-9;?]*[A-Za-z]/g,'').split(/\r?\n/).map(l=>l.trim())
    .filter(l=> l && !/^(session_id:|session:|duration:|messages:|query:|initializing agent|resume this session|hermes --resume|[-─=]{3,})/i.test(l))
    .join(' ').replace(/```[\s\S]*?```/g,' ').replace(/[*_#>`]/g,'').replace(/\s{2,}/g,' ').trim();
}
