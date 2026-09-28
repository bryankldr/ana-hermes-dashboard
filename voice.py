import pathlib
"""
Text to speech — ElevenLabs (berbayar) bila ada key, fallback gratis edge-tts (id-ID).

Edge-tts gratis via Microsoft: id-ID-GadisNeural (female), id-ID-ArdiNeural (male).
Tanpa API key tetap bunyi, ganti suara di dashboard langsung terdengar.
"""
import asyncio
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

# ElevenLabs
DEFAULT_VOICE = "21m00Tcm4TlvDq8ikWAM"
MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_multilingual_v2")

# Gratis edge-tts
FREE_DEFAULT = "id-ID-GadisNeural"
FREE_VOICES = [
    {"id": "id-ID-GadisNeural", "name": "Gadis", "gender": "female", "desc": "Female warm friendly — gratis, paling natural id (Edge)"},
    {"id": "id-ID-ArdiNeural", "name": "Ardi", "gender": "male", "desc": "Male friendly positive — gratis, natural id (Edge)"},
]

# Curated ElevenLabs Indonesia (tetap ada bila key diisi)
CURATED_ID_VOICES = [
    {"id":"yLyL4E4r0QfLyYpCwPir", "name":"Sikedewi", "gender":"female", "desc":"30-35th, jernih, neutral — narasi & berita"},
    {"id":"o5s6XRBkPSTD4syv6mZg", "name":"Arunika", "gender":"female", "desc":"Professional TV, artikulasi kristal"},
    {"id":"HnnPtoATgzx4ubChwm24", "name":"Zaak", "gender":"female", "desc":"Young friendly, news/IVR"},
    {"id":"GdyFAZdMpKMBHw5pc1Bu", "name":"Livna", "gender":"female", "desc":"Neutral clear mid-range"},
    {"id":"ffTJE9l3Kt2ipEM32UOc", "name":"Aita", "gender":"female", "desc":"Youthful expressive, drama"},
    {"id":"I7sakys8pBZ1Z5f0UhT9", "name":"Putri Maharani", "gender":"female", "desc":"Warm expressive, storytelling"},
    {"id":"eRyKqfgsJAedPgBBSuqA", "name":"Meraki", "gender":"female", "desc":"Middle-aged calm"},
    {"id":"IALUBpQ56gzxhNH8HDDK", "name":"Mizani", "gender":"male", "desc":"Warm baritone, storytelling"},
    {"id":"v70fYBHUOrHA3AKIBjPq", "name":"Mahaputra", "gender":"male", "desc":"Young male clear standard"},
    {"id":"gmnazjXOFoOcWA59sd5m", "name":"Pratama", "gender":"male", "desc":"Young energetic, gaming"},
    {"id":"93hTIgYC2wj4AtGhp6WE", "name":"Ganesh", "gender":"male", "desc":"Warm intimate baritone"},
    {"id":"2vWyCz46C1DzMIf4aE0n", "name":"Youvandra Febrial", "gender":"male", "desc":"Male story/fairy-tale"},
    {"id":"3mAVBNEqop5UbHtD8oxQ", "name":"Zephlyn", "gender":"male", "desc":"Calm neutral Balinese"},
]

def _eleven_available():
    return bool(os.environ.get("ELEVENLABS_API_KEY"))

def has_eleven():
    return _eleven_available()

def available():
    # selalu True setelah edge-tts terpasang
    return True

def voice_id():
    v = os.environ.get("ELEVENLABS_VOICE_ID", "").strip()
    if v:
        return v
    return FREE_DEFAULT

def curated_voices():
    if _eleven_available():
        return CURATED_ID_VOICES
    return FREE_VOICES

def _is_free_id(vid):
    return vid in {v["id"] for v in FREE_VOICES}

async def _edge_save(text, voice, out_path):
    import edge_tts
    comm = edge_tts.Communicate(text, voice=voice)
    await comm.save(out_path)

def _edge_speak_sync(text, voice):
    # mp3 bytes via temp file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        tmp = tf.name
    try:
        asyncio.run(_edge_save(text, voice, tmp))
        return pathlib.Path(tmp).read_bytes()
    finally:
        try:
            pathlib.Path(tmp).unlink(missing_ok=True)
        except: pass

def speak(text):
    """Returns mp3 bytes — gratis edge-tts bila ElevenLabs tidak ada."""
    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")
    vid = voice_id()
    # ElevenLabs bila key ada dan vid bukan free
    if _eleven_available() and not _is_free_id(vid):
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
            data=json.dumps({
                "text": text[:2500],
                "model_id": MODEL,
                "voice_settings": {"stability": 0.36, "similarity_boost": 0.78, "style": 0.32, "use_speaker_boost": True},
            }).encode(),
            method="POST",
            headers={"content-type": "application/json", "accept": "audio/mpeg", "xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    # gratis edge-tts
    voice = vid if _is_free_id(vid) else FREE_DEFAULT
    # map curated -> free fallback (female->Gadis, male->Ardi)
    if not _is_free_id(vid):
        # keep character hint: female curated -> Gadis, male -> Ardi
        female_ids = {v["id"] for v in CURATED_ID_VOICES if v["gender"]=="female"}
        voice = "id-ID-GadisNeural" if vid in female_ids or vid==DEFAULT_VOICE else "id-ID-ArdiNeural"
        # legacy Rachel -> Gadis
        if vid == DEFAULT_VOICE:
            voice = "id-ID-GadisNeural"
    return _edge_speak_sync(text[:1500], voice)

def speak_with_voice(text, vid):
    """Preview dengan voice tertentu tanpa simpan."""
    text = (text or "").strip()[:1500]
    if not text:
        raise ValueError("empty text")
    if _eleven_available() and not _is_free_id(vid):
        req = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
            data=json.dumps({"text": text, "model_id": MODEL, "voice_settings": {"stability": 0.36, "similarity_boost": 0.78, "style": 0.32, "use_speaker_boost": True}}).encode(),
            method="POST",
            headers={"content-type": "application/json", "accept": "audio/mpeg", "xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    voice = vid if _is_free_id(vid) else FREE_DEFAULT
    if not _is_free_id(vid):
        female_ids = {v["id"] for v in CURATED_ID_VOICES if v["gender"]=="female"}
        voice = "id-ID-GadisNeural" if vid in female_ids or vid==DEFAULT_VOICE else "id-ID-ArdiNeural"
    return _edge_speak_sync(text, voice)

def transcribe(audio, mime="audio/webm"):
    if not _eleven_available():
        raise RuntimeError("STT butuh ELEVENLABS_API_KEY (transcribe belum gratis)")
    if not audio:
        raise ValueError("empty audio")
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "mp4", "audio/mpeg": "mp3", "audio/wav": "wav"}.get(mime.split(";")[0], "webm")
    boundary = "----ana" + os.urandom(8).hex()
    b = boundary.encode()
    body = b"".join([
        b"--", b, b"\r\n",
        b'Content-Disposition: form-data; name="model_id"\r\n\r\nscribe_v1\r\n',
        b"--", b, b"\r\n",
        b'Content-Disposition: form-data; name="language_code"\r\n\r\nid\r\n',
        b"--", b, b"\r\n",
        f'Content-Disposition: form-data; name="file"; filename="turn.{ext}"\r\n'.encode(),
        f"Content-Type: {mime}\r\n\r\n".encode(),
        audio, b"\r\n",
        b"--", b, b"--\r\n",
    ])
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/speech-to-text",
        data=body, method="POST",
        headers={"content-type": f"multipart/form-data; boundary={boundary}", "xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
    )
    with urllib.request.urlopen(req, timeout=45) as r:
        return (json.loads(r.read()).get("text") or "").strip()

def voices():
    if not _eleven_available():
        return []
    req = urllib.request.Request("https://api.elevenlabs.io/v2/voices", headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read())
    except Exception:
        return []
    return [dict(id=v.get("voice_id"), name=v.get("name"), labels=v.get("labels", {})) for v in body.get("voices", [])]
