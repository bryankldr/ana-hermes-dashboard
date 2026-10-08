# Natural Conversational Voice Engine — Anna

## Tujuan

Audit dan tingkatkan sistem voice conversation pada `ana-hermes-dashboard` agar interaksi suara Anna terasa seperti percakapan manusia yang natural, bukan pola:

```text
USER SPEAK
→ STT
→ LLM
→ TTS
→ END
```

VAD **sudah terimplementasi**. Jangan mengganti VAD secara keseluruhan kecuali ditemukan masalah teknis yang nyata.

Fokus utama adalah membangun **interruptible, turn-aware, streaming conversational loop** yang mampu menangani:

* jeda alami ketika user berbicara
* user melanjutkan kalimat setelah jeda
* user mengoreksi perkataan sebelumnya
* user berbicara ketika Anna sedang berpikir
* user menyela ketika Anna sedang berbicara
* pause/resume TTS
* cancel/restart response
* penggabungan beberapa utterance menjadi satu turn
* streaming STT
* streaming LLM
* streaming TTS
* low-latency interruption
* conversational grace period
* continuous conversation tanpa harus selalu mengulang wake word

---

# 1. Prinsip Utama

Anna harus diperlakukan sebagai **continuous conversational agent**, bukan request-response chatbot.

Target perilaku:

```text
USER
  │
  │ berbicara
  ▼
STT streaming
  │
  │ partial transcript
  ▼
Conversation Manager
  │
  │ menentukan apakah user masih berbicara
  ▼
Anna / Hermes
  │
  │ streaming response
  ▼
TTS streaming
  │
  ▼
SPEAKER
  │
  │ user dapat menyela kapan saja
  ▼
INTERRUPTION
  │
  ├── pause TTS
  ├── cancel generation jika diperlukan
  └── kembali mendengarkan user
```

Jangan menggunakan asumsi:

```text
speech ended
=
user finished talking
```

Speech pause dan conversational turn adalah dua konsep berbeda.

---

# 2. Arsitektur yang Diinginkan

Pertahankan arsitektur aplikasi yang sudah ada.

Saat ini pipeline Anna kurang lebih:

```text
main.js  (chatbox + voice STT/VAD → transmit)
  ↓  POST /api/run  SSE  (server.py _stream_run)
server.py  (import runtime_gateway as runtime)
  ↓  runtime.run(message, sid, system)
runtime_gateway.py  (_discover_gateway_url → _get_gateway → _run_hermes_locked)
  ↓  submit_prompt_stream
gateway_client.py  (WS $ANA_GATEWAY_URL → /api/ws)
  ↓  JSON-RPC  session.create / prompt.submit / message.delta|complete
Hermes Gateway  (hermes serve --host 127.0.0.1 --port 0 → 127.0.0.1:$SPORT, WS /api/ws)
  ↓
ANNA
```

> **Operasional WS (anti-recur Errno 111):** Hermes Gateway WS **bukan** `ws://localhost:37521/api/ws`. Port `hermes serve` adalah **ephemeral** (`--port 0` → mis. `35405`) dan token per-proses `__HERMES_SESSION_TOKEN__`.
> Discovery tunggal: `start.sh:108-122` → `ss -ltnp | grep '"hermes"'` → `SPORT` → `curl http://127.0.0.1:$SPORT/ | grep __HERMES_SESSION_TOKEN__` → `export ANA_GATEWAY_URL="ws://127.0.0.1:$SPORT/api/ws"` + `ANA_GATEWAY_TOKEN`.
> `runtime_gateway._discover_gateway_url()` melakukan hal yang sama saat `ANA_GATEWAY_URL` kosong (fallback discovery, bukan fallback `:37521`). `gateway_client` **wajib** `gateway_url` (dari env atau arg) — tidak ada default `:37521`. Jika tidak discoverable, `runtime_gateway` fail-fast dengan pesan `Run via ./start.sh or export ANA_GATEWAY_URL=...` alih-alih diam-diam `ConnectionRefused [Errno 111] ('127.0.0.1', 37521)`.

Tambahkan atau refactor layer realtime conversation menjadi:

```text
                    USER
                     │
                     ▼
                   VAD
                     │
                     ▼
              Streaming STT
                     │
                     ▼
          ┌──────────────────────┐
          │ Conversation Manager │
          │                      │
          │ turn buffer          │
          │ timing               │
          │ interruption        │
          │ aggregation          │
          │ revision detection   │
          └──────────┬───────────┘
                     │
                     ▼
                Hermes / Anna
                     │
               token streaming
                     │
                     ▼
              Response Chunker
                     │
                     ▼
              Streaming TTS
                     │
                     ▼
                Audio Output
                     │
                     │
                USER SPEAKS
                     │
                     ▼
                 INTERRUPT
                     │
                     └──────► Conversation Manager
```

Conversation Manager harus menjadi **orchestrator realtime**.

Jangan memindahkan tanggung jawab timing/interruption ke LLM.

---

# 3. State Machine

Implementasikan atau refactor menjadi state machine yang eksplisit.

Minimal:

```text
IDLE
LISTENING
USER_PAUSED
THINKING
SPEAKING
INTERRUPTED
WAITING_FOR_CONTINUATION
CANCELLED
```

State transition:

```text
IDLE
 ↓ voice detected
LISTENING
 ↓ speech pause
USER_PAUSED
 ├── user continues
 │      ↓
 │   LISTENING
 │
 └── grace period expired
        ↓
     THINKING
        ↓ first response
     SPEAKING
        │
        ├── user speaks
        │      ↓
        │  INTERRUPTED
        │      ↓
        │  LISTENING
        │
        └── response finished
               ↓
        WAITING_FOR_CONTINUATION
               │
               ├── user continues
               │      ↓
               │   LISTENING
               │
               └── timeout
                      ↓
                     IDLE
```

State harus dapat diamati melalui debug logging.

Contoh:

```text
[VOICE] LISTENING
[VOICE] PARTIAL_STT: "Anna coba lihat..."
[VOICE] USER_PAUSED
[VOICE] USER_CONTINUES
[VOICE] PARTIAL_STT: "...produksi bulan Mei"
[VOICE] END_OF_TURN
[VOICE] THINKING
[VOICE] FIRST_TOKEN
[VOICE] TTS_START
[VOICE] SPEAKING
[VOICE] USER_INTERRUPTION
[VOICE] TTS_CANCEL
[VOICE] LLM_CANCEL
[VOICE] LISTENING
```

---

# 4. Speech Pause ≠ End Of Turn

Ini adalah requirement paling penting.

Jangan langsung mengakhiri turn hanya karena VAD mendeteksi silence.

Contoh:

```text
User:
"Anna, coba lihat produksi bulan Mei..."

[1.2 detik silence]

User:
"...dibanding April."
```

Harus menghasilkan:

```text
Satu conversational turn:

"Anna, coba lihat produksi bulan Mei dibanding April."
```

Bukan:

```text
Turn 1:
"Anna, coba lihat produksi bulan Mei"

Turn 2:
"dibanding April"
```

Implementasikan **end-of-turn grace period**.

Gunakan configurable parameters, misalnya:

```text
speech_start_threshold
speech_end_threshold
end_of_turn_grace_ms
continuation_window_ms
```

Jangan hardcode angka tanpa alasan.

Mulai dengan kisaran:

```text
end_of_turn_grace_ms = 500–900
continuation_window_ms = 1500–3000
```

Kemudian lakukan tuning berdasarkan hasil pengujian.

---

# 5. Utterance Aggregation

Buat buffer percakapan sementara.

Contoh:

```text
utterance_1:
"Anna coba lihat produksi Mei"

pause

utterance_2:
"eh dibanding April"

pause

utterance_3:
"maksud saya produksi P2"
```

Conversation Manager harus dapat menghasilkan:

```text
CURRENT TURN:

"Anna coba lihat produksi Mei,
eh dibanding April,
maksud saya produksi P2."
```

Namun jangan selalu mengirim raw transcript tersebut ke LLM.

Gunakan tahap:

```text
RAW UTTERANCES
      ↓
TURN AGGREGATION
      ↓
CONVERSATIONAL NORMALIZATION
      ↓
FINAL USER INTENT
      ↓
ANNA
```

Tujuannya adalah mempertahankan konteks tanpa membuat transcript menjadi kacau.

---

# 6. User Revision / Self-Correction

User sering mengubah maksud di tengah kalimat.

Contoh:

```text
"Anna, kenapa produksi Mei..."
"eh bukan Mei..."
"maksud saya April."
```

Jangan memproses:

```text
"kenapa produksi Mei"
```

kemudian langsung menghasilkan jawaban final jika masih berada dalam continuation window.

Tunggu sampai turn benar-benar committed.

Hasil akhir:

```text
"Anna, kenapa produksi April?"
```

Prioritaskan **latest correction**.

Pattern yang perlu dikenali:

```text
eh
bukan
maksud saya
maksudku
tunggu
sebentar
salah
koreksi
yang saya maksud
```

Tidak perlu membuat classifier kompleks terlebih dahulu.

Gunakan heuristik sederhana sebagai sinyal interruption/revision.

---

# 7. User Berbicara Saat Anna THINKING

Kasus:

```text
USER:
"Anna, berapa produksi Mei?"

STT
 ↓
Anna THINKING

USER:
"sekalian bandingkan dengan April."
```

Jangan menganggap utterance kedua sebagai query baru yang terpisah.

Cancel pending generation/tool execution jika memang belum menghasilkan output yang berguna.

Gabungkan:

```text
"Anna, berapa produksi Mei?
sekalian bandingkan dengan April."
```

Kemudian jalankan ulang.

Prioritas:

```text
NEW USER INPUT
>
PENDING RESPONSE
```

Jika user memberikan informasi baru yang mengubah intent, **new input harus menang**.

---

# 8. User Menyela Saat Anna SPEAKING

Kasus:

```text
ANNA:
"Produksi Mei mencapai 820 ton dan—"

USER:
"Tunggu, itu produksi total atau P2?"
```

Respons Anna harus:

```text
1. Detect speech
2. Stop/pause audio output secepat mungkin
3. Stop generating unnecessary TTS audio
4. Cancel LLM stream jika response belum selesai
5. Preserve conversation context
6. Continue listening
7. Aggregate interruption utterance
8. Process new intent
```

Target interruption latency:

```text
< 200 ms
```

Target ideal:

```text
~100 ms
```

Jangan menunggu TTS selesai.

---

# 9. Pause vs Cancel

Jangan selalu kill response.

Bedakan:

### Soft interruption

Contoh:

```text
User:
"iya..."
```

atau:

```text
"sebentar..."
```

Jika konteks menunjukkan user masih ingin Anna melanjutkan, response dapat dipause.

```text
SPEAKING
   ↓
PAUSE
   ↓
LISTENING
   ↓
"lanjut"
   ↓
RESUME
```

### Hard interruption

Contoh:

```text
"bukan itu yang saya tanyakan."
```

atau:

```text
"tunggu, maksud saya..."
```

Maka:

```text
CANCEL TTS
CANCEL LLM
DISCARD REMAINING RESPONSE
LISTEN
BUILD NEW TURN
PROCESS AGAIN
```

Implementasikan cancellation secara nyata jika stack saat ini memungkinkan.

Jangan hanya menghentikan playback sementara tetapi membiarkan backend tetap menghasilkan response yang sudah tidak relevan.

---

# 10. Streaming STT

Jika STT yang digunakan mendukung streaming/partial transcript, manfaatkan.

Contoh:

```text
0.2s
"Anna"

0.5s
"Anna kenapa"

0.8s
"Anna kenapa produksi"

1.1s
"Anna kenapa produksi Mei"
```

Conversation Manager harus dapat menerima:

```text
partial
final
speech_start
speech_end
```

Jangan menunggu final transcript untuk mendeteksi interruption.

---

# 11. Streaming LLM

Jangan:

```text
WAIT FULL LLM RESPONSE
        ↓
SEND TO TTS
```

Gunakan:

```text
LLM token stream
      ↓
sentence/chunk detector
      ↓
TTS
```

Contoh:

```text
LLM:
"Produksi Mei turun dibanding April."

→ TTS

LLM:
"Penurunan terutama terlihat pada P2."

→ TTS
```

TTS dapat mulai sebelum seluruh response selesai.

---

# 12. TTS Sentence Buffer

Implementasikan buffer:

```text
TTS_BUFFER
```

Jangan mengirim setiap token ke TTS.

Gunakan boundary:

```text
.
?
!
,
```

serta batas panjang tertentu.

Contoh:

```text
LLM:
"Produksi Mei turun."

→ TTS segera

LLM:
"Penurunan terbesar terjadi pada P2."

→ TTS segera
```

Tujuan:

```text
TTFA rendah
+
intonasi tetap natural
+
interruptible
```

---

# 13. TTS Harus Interruptible

TTS output harus berupa audio chunks.

```text
TTS
 │
 ├── chunk 1
 ├── chunk 2
 ├── chunk 3
 ├── chunk 4
 └── chunk 5
```

Audio player harus dapat menerima:

```text
pause()
resume()
cancel()
flush()
```

Jika user berbicara:

```text
audio_player.cancel()
tts.cancel()
```

Jangan membiarkan seluruh audio response sudah berada di playback queue.

Idealnya hanya sedikit audio yang sudah buffered.

---

# 14. Audio Buffer Jangan Terlalu Panjang

Jika seluruh TTS response dimasukkan ke queue:

```text
TTS
 ↓
10 detik audio
 ↓
PLAYER
```

interruption akan terasa lambat.

Gunakan small streaming buffer.

Target:

```text
~100–300 ms
```

atau nilai yang sesuai dengan audio engine.

Prinsip:

```text
LOW AUDIO BUFFER
=
LOW INTERRUPTION LATENCY
```

---

# 15. Continuous Conversation Window

Setelah Anna selesai berbicara:

```text
Anna:
"Produksi Mei mencapai 820 ton."
```

jangan langsung:

```text
→ IDLE
```

Masuk ke:

```text
WAITING_FOR_CONTINUATION
```

selama beberapa detik.

Jika user berkata:

```text
"Kalau April?"
```

anggap sebagai continuation.

Tidak perlu:

```text
wake word
```

atau reset conversation.

Contoh:

```text
Anna:
"Produksi Mei 820 ton."

USER:
"Kalau April?"

Anna:
"April mencapai 910 ton."
```

Harus terasa seperti percakapan biasa.

---

# 16. Backchannel

Evaluasi kemungkinan menambahkan short acknowledgement.

Contoh:

```text
USER:
"Anna, coba cek semua BKPH yang produksinya turun..."

ANNA:
"Ya, saya cek."

[tool execution]

ANNA:
"Yang paling signifikan adalah..."
```

Backchannel tidak boleh digunakan berlebihan.

Gunakan hanya ketika:

* tool execution membutuhkan waktu
* query cukup kompleks
* user sedang memberikan konteks panjang
* ada jeda yang terasa terlalu panjang

Jangan menghasilkan:

```text
"Baik..."
"Ya..."
"Oke..."
"Sebentar..."
```

secara berlebihan.

Tujuannya natural, bukan ramai.

---

# 17. Tool Execution Harus Interruptible

Anna menggunakan Business Data Engine/tools.

Kasus:

```text
USER:
"Anna, analisis produksi Mei."

        ↓

Anna memanggil tool

        ↓

USER:
"sebentar, saya maksud April."
```

Jika tool execution masih berjalan dan aman untuk dibatalkan:

```text
CANCEL TOOL
```

Kemudian proses intent baru.

Jika tool sudah selesai, hasilnya dapat dibuang jika sudah tidak relevan.

Jangan meneruskan response berdasarkan intent lama.

---

# 18. Conversation Context

Pisahkan:

```text
conversation_history
```

dari:

```text
current_turn_buffer
```

Contoh:

```text
conversation_history:

User:
"Bagaimana produksi Mei?"

Anna:
"Produksi Mei 820 ton."


current_turn_buffer:

User:
"Kalau dibanding April?"
```

Ketika turn committed:

```text
conversation_history
+
current_turn
```

baru dikirim ke Anna.

Jangan terus-menerus mengirim transcript mentah setiap partial STT ke LLM.

Ini akan:

* meningkatkan token
* meningkatkan latency
* meningkatkan biaya
* membuat reasoning kacau

---

# 19. Cancellation Semantics

Semua request realtime harus memiliki identity.

Contoh:

```text
conversation_id
turn_id
response_id
tts_id
```

Misalnya:

```text
conversation_id = anna-session-42
turn_id         = 17
response_id     = 17-r1
tts_id          = 17-t1
```

Jika user menyela:

```text
turn 17
   ↓
CANCEL response 17-r1
CANCEL TTS 17-t1
```

Kemudian:

```text
turn 18
```

Jangan sampai response lama muncul setelah response baru.

---

# 20. Race Condition

Audit khusus kondisi:

```text
User interruption
+
LLM token arrival
+
TTS chunk arrival
+
audio playback
```

secara bersamaan.

Contoh bug:

```text
User interrupts
       ↓
TTS cancel

tetapi

LLM masih mengirim token
       ↓
TTS membuat audio baru
       ↓
audio lama muncul lagi
```

Harus ada generation/version guard.

Contoh konsep:

```text
generation_id = 42

interrupt
→ generation_id = 43

token dari generation 42
→ DISCARD
```

Hanya generation aktif yang boleh menghasilkan audio.

---

# 21. Jangan Mengorbankan Latency Demi Naturalness

Optimasi harus menjaga:

```text
Time To First Audio
Interruption Latency
End Of Turn Detection
STT latency
TTS latency
```

Instrumentasikan:

```text
speech_start
speech_end
stt_partial
stt_final
turn_commit
llm_start
llm_first_token
tts_start
tts_first_audio
audio_play
interrupt_detected
tts_cancelled
llm_cancelled
```

Kemudian hitung:

```text
STT latency
LLM TTFT
TTS TTFA
interrupt latency
turn detection latency
```

---

# 22. Observability

Tambahkan debug mode khusus:

```text
VOICE_DEBUG=1
```

Contoh log:

```text
21:31:04.102 [VAD] speech_start
21:31:04.210 [STT] partial="Anna"
21:31:04.430 [STT] partial="Anna kenapa"
21:31:05.120 [STT] partial="Anna kenapa produksi Mei"
21:31:05.550 [VAD] speech_end
21:31:05.550 [TURN] waiting continuation
21:31:06.240 [VAD] speech_start
21:31:06.420 [STT] partial="dibanding April"
21:31:06.910 [VAD] speech_end
21:31:07.600 [TURN] commit
21:31:07.601 [LLM] start
21:31:08.120 [LLM] first_token
21:31:08.300 [TTS] start
21:31:08.520 [AUDIO] first_play
```

Untuk interruption:

```text
21:31:11.420 [VAD] speech_start
21:31:11.470 [VOICE] interruption_detected
21:31:11.480 [TTS] cancel
21:31:11.490 [LLM] cancel
21:31:11.500 [AUDIO] flush
21:31:11.510 [VOICE] listening
```

---

# 23. UX Target

Setelah implementasi, percakapan berikut harus bekerja secara natural.

### Test 1 — Natural pause

```text
USER:
"Anna, coba lihat produksi bulan Mei..."

[1–2 detik pause]

"...dibanding April."

ANNA:
langsung memahami satu pertanyaan.
```

### Test 2 — Self correction

```text
USER:
"Kenapa produksi Mei..."
"eh bukan Mei..."
"April."

ANNA:
memproses "Kenapa produksi April?"
```

### Test 3 — Interrupt thinking

```text
USER:
"Anna, analisis produksi Mei."

ANNA:
thinking...

USER:
"sekalian bandingkan dengan April."

ANNA:
membatalkan intent lama jika perlu
dan memproses permintaan gabungan.
```

### Test 4 — Interrupt speaking

```text
ANNA:
"Produksi Mei mencapai 820..."

USER:
"Tunggu, itu P1 atau total?"

ANNA:
STOP SEGERA.

ANNA:
"820 ton itu total produksi..."
```

### Test 5 — Follow-up

```text
ANNA:
"Produksi Mei mencapai 820 ton."

USER:
"Kalau April?"

ANNA:
"April mencapai..."
```

Tidak perlu wake word.

### Test 6 — Pause/resume

```text
ANNA:
"Produksi Mei mengalami..."

USER:
"iya, lanjut."

ANNA:
melanjutkan response.
```

### Test 7 — Hard correction

```text
ANNA:
"Produksi Mei mengalami..."

USER:
"Bukan itu yang saya tanyakan."

ANNA:
STOP.

USER:
"Saya ingin tahu BKPH mana yang turun."

ANNA:
memproses intent baru.
```

---

# 24. Acceptance Criteria

Implementasi dianggap berhasil jika:

* [ ] VAD existing tetap berfungsi
* [ ] silence pendek tidak otomatis mengakhiri conversational turn
* [ ] utterance dapat digabung
* [ ] user dapat melanjutkan kalimat setelah pause
* [ ] user dapat mengoreksi dirinya sendiri
* [ ] user dapat menyela saat Anna THINKING
* [ ] user dapat menyela saat Anna SPEAKING
* [ ] TTS dapat dihentikan <200 ms setelah interruption terdeteksi
* [ ] LLM generation lama dapat dibatalkan
* [ ] TTS generation lama tidak dapat bocor ke response baru
* [ ] audio queue dapat di-flush
* [ ] generation/version guard mencegah race condition
* [ ] streaming STT digunakan jika tersedia
* [ ] streaming LLM dipertahankan
* [ ] TTS menggunakan streaming/chunking
* [ ] response dapat dimulai sebelum seluruh LLM response selesai
* [ ] conversation tetap aktif setelah Anna selesai bicara
* [ ] follow-up tidak membutuhkan wake word
* [ ] tool execution dapat dibatalkan bila relevan dan aman
* [ ] voice latency memiliki instrumentation
* [ ] tidak terjadi response overlap
* [ ] tidak ada duplicate TTS
* [ ] tidak ada stale response setelah interruption

---

# 25. Batasan Penting

Jangan:

* mengganti seluruh voice stack tanpa audit terlebih dahulu
* mengganti VAD hanya karena ingin mengubah conversational behavior
* memasukkan conversation timing ke system prompt LLM
* meminta LLM menentukan kapan audio harus dihentikan
* menunggu full LLM response sebelum memulai TTS
* melakukan full TTS buffering sebelum playback
* menganggap setiap VAD `speech_end` sebagai final turn
* mematikan seluruh session ketika terjadi interruption
* menghapus conversation context ketika user menyela
* membuat wake-word wajib untuk setiap follow-up
* menambahkan acknowledgement berlebihan
* melakukan perubahan destruktif terhadap SPATIAL MAP/dashboard
* mengubah Business Data Engine tanpa alasan yang berkaitan langsung dengan realtime voice

---

# 26. Prioritas Implementasi

Kerjakan bertahap:

## P0 — Critical

```text
1. Conversation state machine
2. End-of-turn grace period
3. Utterance aggregation
4. Barge-in
5. TTS cancellation
6. LLM cancellation
7. Audio queue flush
8. Generation/version guard
```

## P1 — High

```text
9. Streaming STT
10. Streaming LLM → sentence chunking
11. Streaming TTS
12. Continuous conversation window
13. Follow-up detection
14. Self-correction handling
```

## P2 — Enhancement

```text
15. Pause/resume
16. Backchannel
17. Tool cancellation
18. Adaptive timing
19. Voice behavior tuning
```

---

# 27. Prinsip Akhir

Target akhir bukan:

> "Anna menjawab secepat mungkin."

Target akhirnya adalah:

> **Anna memahami kapan harus mendengarkan, kapan harus menunggu, kapan harus mulai menjawab, kapan harus berhenti, kapan harus melanjutkan, dan kapan harus membuang respons yang sudah tidak relevan.**

Naturalness berasal dari orchestration:

```text
             ┌──────────────┐
             │    LISTEN    │
             └──────┬───────┘
                    │
              short pause?
                    │
             ┌──────▼───────┐
             │    WAIT      │
             └──────┬───────┘
                    │
             user continues?
               │          │
              YES         NO
               │          │
               ▼          ▼
            LISTEN      THINK
                           │
                           ▼
                         SPEAK
                           │
                    user interrupts?
                       │         │
                      NO        YES
                       │         │
                       │         ▼
                       │      STOP
                       │         │
                       │      LISTEN
                       │         │
                       └─────────┘
```

**Jadikan Conversation Manager sebagai lapisan realtime utama. VAD hanya mendeteksi aktivitas suara; VAD tidak boleh menentukan keseluruhan logika percakapan.**

Audit implementasi yang ada terlebih dahulu, identifikasi komponen yang sudah memenuhi requirement, kemudian lakukan perubahan sekecil mungkin. Jangan melakukan rewrite besar apabila arsitektur saat ini dapat diperbaiki secara incremental.
