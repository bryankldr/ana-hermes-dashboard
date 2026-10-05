"""
Text to speech — Microsoft Edge TTS (id-ID), tanpa API key.

Dua timbre id-ID yang tersedia:
  id-ID-GadisNeural (perempuan)  -> agent_name ANNA
  id-ID-ArdiNeural  (laki-laki)  -> agent_name MAX

STT (speech-to-text) tidak ada di sini: transkripsi memakai Web Speech API dari
browser (frontend). Edge TTS hanya sintesis suara, tidak mengenali suara.
"""
import asyncio
import os
import pathlib
import tempfile
import threading

_TTS_SEM = threading.Semaphore(2)

FREE_DEFAULT = "id-ID-GadisNeural"
VOICE_FILE = pathlib.Path(__file__).resolve().parent / ".ana_voice"

# agent_name = nama yang diucapkan, terpisah dari nama voice. Suara laki-laki
# memperkenalkan diri dengan nama laki-laki: timbre dan nama profil tidak harus
# sama, dan sistem (profil Hermes) tidak perlu diubah untuk itu.
FREE_VOICES = [
    {"id": "id-ID-GadisNeural", "name": "Gadis", "gender": "female", "agent_name": "ANNA",
     "desc": "Hangat dan ramah — paling natural untuk bahasa Indonesia"},
    {"id": "id-ID-ArdiNeural", "name": "Ardi", "gender": "male", "agent_name": "MAX",
     "desc": "Friendly dan positif — natural untuk bahasa Indonesia"},
]
_DEFAULT_AGENT_NAME = "ANNA"


def _ids():
    return {v["id"] for v in FREE_VOICES}


def available():
    return True


def has_eleven():
    """Jalur ElevenLabs sudah dihapus; selalu False."""
    return False


def voice_id():
    """Voice aktif. Sumber urutan: file .ana_voice, env ANA_VOICE_ID, default."""
    try:
        v = VOICE_FILE.read_text(encoding="utf-8").strip()
        if v in _ids():
            return v
    except OSError:
        pass
    v = (os.environ.get("ANA_VOICE_ID") or "").strip()
    return v if v in _ids() else FREE_DEFAULT


def set_voice(vid):
    vid = (vid or "").strip()
    if vid not in _ids():
        raise ValueError("voice_id tidak ada di daftar")
    os.environ["ANA_VOICE_ID"] = vid
    try:
        VOICE_FILE.write_text(vid, encoding="utf-8")
    except OSError:
        pass
    return vid


def agent_name(vid=None):
    """Nama yang diucapkan untuk sebuah voice id."""
    hit = next((v for v in FREE_VOICES if v["id"] == (vid or voice_id()).strip()), None)
    return (hit or {}).get("agent_name", _DEFAULT_AGENT_NAME)


def curated_voices():
    return FREE_VOICES


async def _edge_save(text, voice, out_path):
    import edge_tts
    comm = edge_tts.Communicate(text, voice=voice)
    await comm.save(out_path)


# Edge TTS hangs instead of erroring above roughly 6k characters (measured:
# 6000 ok, 8000/10000/12000 all TimeoutError) — one giant request never returns,
# so /api/speak would sit forever. Chunk at sentence boundaries and concatenate
# the MP3 frames: MP3 is a stream of self-contained frames, so byte-concatenating
# whole files plays back correctly (verified: 3.816s + 3.504s -> 7.320s).
# 1200 chars per chunk leaves headroom under the hard limit and under the
# per-request time Edge needs for long input.
_CHUNK_CHARS = 1200
_CHUNK_TIMEOUT = 120.0  # seconds per chunk; whole-file requests ran 69s


def _split_for_speech(text, limit=_CHUNK_CHARS):
    """Split at sentence/clause boundaries, packing up to *limit* chars per chunk.

    Never split mid-word: a chunk boundary inside a token makes Edge mispronounce
    it or drop it. Falls back to whitespace when a single sentence exceeds the
    limit, and to a hard slice only if even one word is longer than the limit.
    """
    import re
    text = text.strip()
    if len(text) <= limit:
        return [text] if text else []

    # Split after . ! ? … followed by space (or end of string).
    parts = re.split(r'(?<=[.!?…])\s+', text)
    chunks, cur = [], ""
    for p in parts:
        if not p:
            continue
        cand = p if not cur else cur + " " + p
        if len(cand) <= limit:
            cur = cand
            continue
        if cur:
            chunks.append(cur)
            cur = ""
        if len(p) <= limit:
            cur = p
        else:
            # One oversized sentence: break on whitespace near the limit.
            words, buf = p.split(), ""
            for w in words:
                # A single token longer than the limit (a URL, a base64 blob) has
                # no split point: emit it as full-width slices rather than
                # truncating, so no characters are silently dropped.
                while len(w) > limit:
                    if buf:
                        chunks.append(buf)
                        buf = ""
                    chunks.append(w[:limit])
                    w = w[limit:]
                cand = w if not buf else buf + " " + w
                if len(cand) <= limit:
                    buf = cand
                else:
                    if buf:
                        chunks.append(buf)
                    buf = w
            cur = buf
    if cur:
        chunks.append(cur)
    return [c for c in chunks if c.strip()]


def _edge_speak_sync(text, voice):
    chunks = _split_for_speech(text)
    if not chunks:
        return b""

    async def synth():
        import edge_tts
        # Synthesize chunks sequentially, not concurrently: Edge rate-limits and a
        # 3-chunk burst is exactly the load pattern that times out.
        parts = []
        with tempfile.TemporaryDirectory() as td:
            for i, c in enumerate(chunks):
                out = os.path.join(td, f"c{i}.mp3")
                comm = edge_tts.Communicate(c, voice=voice)
                await asyncio.wait_for(comm.save(out), timeout=_CHUNK_TIMEOUT)
                parts.append(pathlib.Path(out).read_bytes())
        return b"".join(parts)

    try:
        return asyncio.run(synth())
    except asyncio.TimeoutError as e:
        raise RuntimeError(f"edge tts timed out on a {len(text)}-char request "
                           f"({len(chunks)} chunks)") from e


# Hard ceiling on one /api/speak call. Not an Edge limit — _edge_speak_sync already
# chunks around the real ~6k boundary — but a runaway guard so a pathological
# answer cannot hold an HTTP thread and synthesize for minutes. 30k chars is
# roughly 25 chunks, about 8-10 minutes of speech, far beyond any report answer.
_SPEAK_MAX_CHARS = 30000


def speak(text):
    """Returns mp3 bytes untuk voice aktif.

    Reads the whole answer: no truncation. Long input is chunked in
    _edge_speak_sync so each Edge request stays under the service limit.
    """
    text = (text or "").strip()[:_SPEAK_MAX_CHARS]
    if not text:
        raise ValueError("empty text")
    # Max 2 sintesis Edge bersamaan; selebihnya tolak cepat (503) supaya
    # frontend langsung fallback ke browser speechSynthesis, bukan antre
    # thread HTTP yang menumpuk tiap jawaban panjang dibacakan.
    if not _TTS_SEM.acquire(blocking=False):
        raise RuntimeError("tts busy, fallback browser")
    try:
        return _edge_speak_sync(text, voice_id())
    finally:
        _TTS_SEM.release()


def speak_with_voice(text, vid):
    """Preview dengan voice tertentu tanpa menyimpan pilihan."""
    # Preview is a fixed short sample; no need to chunk it.
    text = (text or "").strip()[:1500]
    if not text:
        raise ValueError("empty text")
    if vid not in _ids():
        raise ValueError("voice_id tidak ada di daftar")
    # Preview ikut semaphore yang sama: tanpa ini 2 speak + 1 preview
    # = 3 sintesis bersamaan, antrean thread HTTP kembali.
    if not _TTS_SEM.acquire(blocking=False):
        raise RuntimeError("tts busy, fallback browser")
    try:
        return _edge_speak_sync(text, vid)
    finally:
        _TTS_SEM.release()