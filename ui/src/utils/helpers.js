// utils/helpers.js — single source for HUD helpers
// Import this instead of redefining now/rid/esc/cleanForSpeech in each component.
// ponytail: keep tiny, no dep; add formatDate etc only when needed.
export const now = () => new Date().toLocaleTimeString('en-GB', { hour12: false });
export const rid = () => 'run_' + (crypto.randomUUID ? crypto.randomUUID().replace(/-/g,'').slice(0,24) : Math.random().toString(16).slice(2,14));
// Quotes matter as much as angle brackets: this is used inside attribute values
// (data-path="…", title="…") and a path is picked up from the filesystem, so a
// directory named x" onmouseover="… would otherwise break out of the attribute.
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
// ── Status-prose stripping (TTS hygiene) ──────────────────────────────────
// Hermes narrates its own work on the thinking channel: a kawaii face plus one
// of the 14 THINKING_VERBS — "(¬‿¬) reasoning...", "( •_•)>⌐■-■ deliberating..."
// (agent/display.py KawaiiSpinner) — plus provider wait notices
// "⏳ waiting on <model> — 60s waiting for the first stream chunk
// (auto-reconnect: stream stale watchdog in 840s)" (chat_completion_wait_notice).
// Both arrive as thinking.delta/reasoning.delta and used to be mapped to `delta`,
// dumping ANA's inner monologue into the RESPONSE panel and feeding it to TTS,
// so she read her own narration aloud before the real answer.
//
// The gateway now routes these to a `thinking` event instead of `delta`, so they
// never reach `answer` at all. The filters below are the second line of defence:
// if any path ever leaks one in again, TTS must not read it.
//
// Discriminator is (face + thinking verb), NOT "starts with punctuation": a broad
// face-glyph or paren-prefix filter also ate real answers — "- 221 petak aktif",
// "(2026) 221 petak", "_221_ petak". Keep the verb list in sync when Hermes adds a
// verb; never widen the match to plain ASCII punctuation.

// Verbs from agent/display.py KawaiiSpinner.THINKING_VERBS (a skin catalog can
// override this list — see KawaiiSpinner.get_thinking_verbs).
const _THINK_VERB = 'pondering|contemplating|musing|cogitating|ruminating|deliberating|mulling|reflecting|processing|reasoning|analyzing|computing|synthesizing|formulating|brainstorming';
// A whole line that is just "<face> verb…" — narration, never an answer.
// Lead-in: KAWAII faces carry a decoration char before the paren or a suffix
// after it — ヾ(＾∇＾), ٩(๑❛ᴗ❛๑)۶, ヽ(>∀<☆)☆, ( ˘▽˘)っ — so allow up to 2
// non-space chars on each side of the parens. The verb after ")" stays the real
// discriminator, so "(2026) 221 petak" still survives.
const _NARRATION_LINE = new RegExp('^\\s*\\S{0,2}[\\(\\uff08][^)\\uff09]*[\\)\\uff09]\\S{0,2}\\s*(?:' + _THINK_VERB + ')\\b[^\\n]*$', 'i');
// Wait notices are stripped as substrings, not whole lines: the reported failure
// was ONE blob "⏳ waiting on …(…840s)The user is asking for…" with the answer
// trailing on the same line, so a line-level filter would eat the answer too.
const _WAIT_NOTICE = new RegExp(
  '(?:\\u23f3\\s*)?waiting on [\\w.\\-]+(?:\\s*[\\u2014-]\\s*\\d+\\s*(?:s|sec|seconds?)\\s*waiting for the first (?:stream chunk|provider event))?' +
  '(?:\\s*\\(auto-reconnect:[^)]*\\))?', 'gi');
export function cleanForSpeech(text){
  return String(text||'').replace(/\x1b\[[0-9;?]*[A-Za-z]/g,'')
    .replace(_WAIT_NOTICE, ' ')
    .split(/\r?\n/).map(l=>l.trim())
    .filter(l=> l && !/^(session_id:|session:|duration:|messages:|query:|initializing agent|resume this session|hermes --resume|[-─=]{3,})/i.test(l))
    .filter(l=> !_NARRATION_LINE.test(l))
    .join(' ').replace(/```[\s\S]*?```/g,' ').replace(/[*_#>`]/g,'').replace(/\s{2,}/g,' ').trim();
}
