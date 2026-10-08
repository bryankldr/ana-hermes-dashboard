# AUDIT STT & TTS — ANNA HERMES DASHBOARD

## Peran

Bertindak sebagai **Senior Voice AI / Real-Time Audio Engineer** yang melakukan audit teknis terhadap implementasi **STT (Speech-to-Text)** dan **TTS (Text-to-Speech)** pada project:

```text
~/PROYEK_2026/ana-hermes-dashboard
```

Project ini adalah dashboard AI **Anna** berbasis Hermes Agent.

Tujuan utama audit:

> Membuat interaksi suara Anna terasa seperti asisten AI real-time yang natural, responsif, tidak kaku, tidak terasa menunggu proses backend, dan mampu melakukan percakapan dua arah secara fluid.

Jangan langsung melakukan perubahan kode.

**Audit terlebih dahulu, pahami implementasi aktual, ukur bottleneck, kemudian berikan rekomendasi dan rencana implementasi.**

---

# 1. PRIORITAS UTAMA

Urutkan prioritas audit berdasarkan:

1. **Perceived latency**
2. **Time-to-first-audio**
3. **Streaming**
4. **Barge-in / interruption**
5. **Voice Activity Detection**
6. **STT latency**
7. **LLM first-token latency**
8. **TTS first-audio latency**
9. **Natural conversational behavior**
10. **Resource utilization**
11. **Reliability**
12. **Scalability**

Jangan hanya mengevaluasi apakah STT/TTS "berfungsi".

Evaluasi apakah sistem:

> terasa cepat bagi manusia.

---

# 2. AUDIT ARSITEKTUR AKTUAL

Telusuri seluruh pipeline voice dari browser sampai audio output.

Petakan implementasi aktual:

```text
Microphone
    ↓
Audio Capture
    ↓
Audio Buffer
    ↓
VAD
    ↓
STT
    ↓
Transcript
    ↓
Anna / Hermes Agent
    ↓
Tool / Business Data Engine
    ↓
LLM Response
    ↓
Text Streaming
    ↓
TTS
    ↓
Audio Streaming
    ↓
Speaker
```

Temukan implementasi sebenarnya di source code.

Identifikasi:

* file;
* class;
* function;
* endpoint;
* WebSocket;
* WebRTC;
* browser API;
* worker;
* subprocess;
* external service;
* local model;
* queue;
* buffer;
* cache;
* audio format;
* codec;
* sample rate;
* chunk size;
* timeout;
* retry mechanism.

Buat diagram arsitektur aktual.

---

# 3. AUDIT STT

Periksa secara khusus:

## Audio Capture

Audit:

* `MediaRecorder`
* Web Audio API
* AudioWorklet
* microphone stream
* sample rate
* channel count
* PCM format
* resampling
* buffering

Tentukan apakah implementasi sekarang menunggu:

```text
user selesai bicara
        ↓
rekam seluruh audio
        ↓
upload seluruh audio
        ↓
STT
```

Jika iya, tandai sebagai:

> HIGH LATENCY ARCHITECTURE

Evaluasi apakah seharusnya menggunakan streaming/near-real-time processing.

---

# 4. VAD — VOICE ACTIVITY DETECTION

Audit apakah sistem menggunakan VAD.

Periksa:

* speech start detection;
* speech end detection;
* silence threshold;
* minimum speech duration;
* minimum silence duration;
* false positive;
* false negative;
* noise handling;
* keyboard noise;
* fan noise;
* outdoor noise.

Target perilaku:

```text
User mulai bicara
       ↓
deteksi speech
       ↓
STT mulai bekerja
```

bukan:

```text
User bicara
       ↓
User selesai
       ↓
baru mulai STT
```

Evaluasi kandidat VAD yang sesuai untuk browser/local deployment.

---

# 5. STREAMING STT

Audit apakah STT dapat menghasilkan partial transcript:

```text
"Anna..."
        ↓
"Anna, bagaimana..."
        ↓
"Anna, bagaimana produksi..."
        ↓
"Anna, bagaimana produksi Mei?"
```

Jika sekarang STT hanya menghasilkan final transcript:

```text
audio selesai
    ↓
STT
    ↓
final transcript
```

identifikasi sebagai bottleneck.

Evaluasi kemungkinan menggunakan:

* streaming STT;
* chunked audio;
* incremental transcription;
* partial hypothesis;
* final hypothesis.

Jangan mengorbankan akurasi secara berlebihan hanya demi latency.

---

# 6. STT MODEL

Identifikasi model STT yang digunakan saat ini.

Catat:

* model;
* parameter size;
* quantization;
* runtime;
* CPU/GPU;
* VRAM;
* RAM;
* language;
* Indonesian support;
* inference backend.

Jika menggunakan Whisper/faster-whisper atau model lain, ukur:

```text
audio duration
vs
processing duration
```

Hitung:

```text
RTF = processing_time / audio_duration
```

Target:

```text
RTF << 1.0
```

Semakin rendah semakin baik.

Evaluasi apakah model sekarang terlalu besar untuk kebutuhan voice assistant.

---

# 7. INDONESIAN LANGUAGE

Karena Anna digunakan dalam bahasa Indonesia, audit:

* Indonesian speech recognition;
* angka;
* nama lokasi;
* nama KPH;
* BKPH;
* RPH;
* TPG;
* istilah getah pinus;
* istilah SIMOGE;
* singkatan;
* nama tabel;
* nama metric;
* istilah teknis.

Periksa apakah terdapat post-processing transcript.

Contoh:

```text
"KPH Banyuwangi Barat"
```

jangan berubah menjadi:

```text
"KPH Banyuwangi Barat?"
```

atau:

```text
"banyuwangi barat"
```

yang menyebabkan tool selection salah.

Evaluasi kebutuhan:

```text
STT
 ↓
Transcript normalization
 ↓
Business terminology correction
 ↓
Hermes
```

Tetapi jangan memasukkan business knowledge besar ke STT.

---

# 8. END-OF-SPEECH DETECTION

Ini sangat penting untuk membuat Anna terasa natural.

Audit berapa lama Anna menunggu setelah user berhenti bicara.

Target awal:

```text
speech ends
    ↓
~200–500 ms
    ↓
Anna mulai memproses
```

Hindari:

```text
speech ends
    ↓
1–2 detik silence
    ↓
STT
```

Namun jangan terlalu agresif sehingga Anna memotong user.

Cari keseimbangan:

```text
Fast response
       ↕
Natural conversation
```

---

# 9. AUDIT TTS

Identifikasi:

* TTS engine;
* model;
* voice;
* runtime;
* CPU/GPU;
* audio format;
* sample rate;
* streaming capability;
* chunk size;
* buffering;
* first-audio latency.

Ukur:

```text
text received
     ↓
TTS processing
     ↓
first audio generated
```

Metric utama:

> **TTFA — Time To First Audio**

Target:

```text
TTFA < 500 ms
```

dan ideal:

```text
TTFA ~200–400 ms
```

sesuaikan dengan model/hardware aktual.

---

# 10. TTS STREAMING

Audit apakah TTS menunggu seluruh response.

Buruk:

```text
Hermes generates entire answer
             ↓
          TTS entire text
             ↓
         play audio
```

Target:

```text
Hermes
 ↓
sentence/chunk
 ↓
TTS
 ↓
🔊 PLAY

Hermes continues
 ↓
next sentence
 ↓
TTS
 ↓
🔊 PLAY
```

Dengan demikian user tidak menunggu seluruh jawaban.

---

# 11. SENTENCE-LEVEL TTS BUFFERING

Implementasikan atau evaluasi mekanisme:

```text
LLM token stream
       ↓
text accumulator
       ↓
sentence boundary
       ↓
TTS chunk
       ↓
audio queue
       ↓
speaker
```

Contoh:

```text
"Produksi Mei mencapai 52,6 persen.
Penyebab utamanya adalah penurunan produksi P2.
Masih terdapat 132 petak bongkor."
```

TTS jangan menunggu seluruh paragraf.

Ideal:

```text
Chunk 1:
"Produksi Mei mencapai 52,6 persen."

        ↓ TTS

Chunk 2:
"Penyebab utamanya adalah penurunan produksi P2."

        ↓ TTS

Chunk 3:
"Masih terdapat 132 petak bongkor."
```

---

# 12. BARGE-IN / INTERRUPTION

Ini adalah fitur wajib untuk voice assistant yang terasa realistis.

Audit apakah user dapat memotong Anna ketika Anna sedang berbicara.

Perilaku yang diinginkan:

```text
Anna:
"Produksi Mei mencapai lima puluh dua..."

User:
"Stop, bukan Mei, April."

Anna:
[STOP AUDIO]

        ↓

STT:
"Stop, bukan Mei, April."

        ↓

Hermes:
memproses instruksi baru
```

Saat user mulai berbicara:

1. hentikan playback TTS;
2. flush audio queue;
3. cancel TTS generation jika memungkinkan;
4. cancel response generation jika memungkinkan;
5. cancel tool call yang aman untuk dibatalkan;
6. mulai STT baru;
7. jangan menunggu response sebelumnya selesai.

---

# 13. FULL-DUPLEX BEHAVIOR

Audit apakah sistem mendukung:

```text
Anna speaking
       +
microphone listening
```

secara bersamaan.

Jika belum, jelaskan batasan arsitektur.

Target ideal:

```text
┌─────────────────────────┐
│ Anna Audio Output       │
│       ↓                 │
│       🔊                │
└────────────┬────────────┘
             │
             │ simultaneous
             ▼
┌─────────────────────────┐
│ Microphone Input        │
│       🎤                │
└─────────────────────────┘
```

Gunakan echo cancellation jika tersedia.

---

# 14. ECHO CANCELLATION

Audit apakah suara Anna sendiri masuk kembali ke microphone.

Periksa:

* Acoustic Echo Cancellation;
* noise suppression;
* auto gain control;
* browser constraints;
* WebRTC audio processing.

Pastikan:

```text
Anna speaks
      ↓
speaker
      ↓
microphone
      ↓
STT
```

tidak menyebabkan Anna mendengar dirinya sendiri.

Jika browser WebRTC audio processing tersedia, evaluasi penggunaannya.

---

# 15. AUDIO QUEUE

Audit apakah terdapat audio queue.

Target:

```text
TTS chunk 1
     ↓
PLAY

TTS chunk 2
     ↓
QUEUE

TTS chunk 3
     ↓
QUEUE
```

Bukan:

```text
generate entire audio
       ↓
play
```

Tetapi juga jangan membuat terlalu banyak buffering karena akan meningkatkan latency.

Cari ukuran queue optimal.

---

# 16. LLM → TTS PIPELINE

Audit pipeline Hermes → TTS.

Ideal:

```text
Hermes token stream
        ↓
"Produksi"
        ↓
"Produksi Mei"
        ↓
"Produksi Mei mencapai"
        ↓
sentence complete
        ↓
TTS
```

Jangan menunggu:

```text
Hermes selesai 100%
```

sebelum TTS dimulai.

Target:

> **TTFT Hermes + sentence formation + TTFA TTS harus seminimal mungkin.**

---

# 17. FAST PATH vs ANALYSIS PATH

Anna harus memiliki dua jalur.

## FAST PATH

Untuk:

* pertanyaan sederhana;
* greetings;
* factual lookup;
* simple tool call.

```text
STT
 ↓
Hermes
 ↓
Tool
 ↓
short response
 ↓
TTS
```

Tidak perlu reasoning panjang.

## ANALYSIS PATH

Untuk:

* analisis;
* diagnosis;
* multi-tool;
* report;
* complex reasoning.

```text
STT
 ↓
Hermes
 ↓
Business Data Engine
 ↓
Pandas
 ↓
reasoning
 ↓
analysis
 ↓
TTS
```

Jangan memaksa semua voice query melewati reasoning panjang.

---

# 18. RESPONSE STYLE UNTUK VOICE

Audit prompt/system instruction Anna agar voice response:

* pendek;
* langsung;
* conversational;
* tidak membaca markdown;
* tidak membaca tabel;
* tidak membaca JSON;
* tidak membaca citation;
* tidak mengucapkan simbol;
* tidak mengulang pertanyaan;
* tidak memberikan disclaimer panjang.

Contoh:

Buruk:

```text
"Berikut adalah analisis berdasarkan tiga parameter..."
```

Lebih baik:

```text
"Produksi Mei hanya 52,6 persen dari target."
```

Kemudian:

```text
"Penyebab utamanya penurunan P2 dan 132 petak bongkor."
```

---

# 19. NUMBER / DATE / UNIT NORMALIZATION

Sebelum TTS, evaluasi text normalization.

Contoh:

```text
52.6%
```

menjadi:

```text
52,6 persen
```

```text
1,540 ton
```

menjadi:

```text
seribu lima ratus empat puluh ton
```

```text
2026-05
```

menjadi:

```text
Mei 2026
```

Tetapi jangan mengubah angka bisnis secara semantik.

TTS normalization hanya mengubah representasi pengucapan.

---

# 20. VOICE PERSONA ANNA

Audit apakah TTS voice sesuai persona Anna.

Target:

* natural;
* profesional;
* tidak terdengar seperti robot;
* artikulasi bahasa Indonesia jelas;
* pace conversational;
* tidak terlalu cepat;
* tidak terlalu lambat;
* pause natural;
* sentence emphasis natural.

Evaluasi:

```text
Speed
Pitch
Pause
Prosody
Pronunciation
Emotion
Consistency
```

Jika engine mendukung SSML atau equivalent, evaluasi penggunaan secara ringan.

Jangan berlebihan menggunakan expressive markup karena dapat meningkatkan latency.

---

# 21. LATENCY INSTRUMENTATION

Tambahkan telemetry internal untuk mengukur:

```text
T0 = microphone speech detected
T1 = speech ended
T2 = STT started
T3 = first partial transcript
T4 = final transcript
T5 = Hermes request started
T6 = Hermes first token
T7 = first tool call
T8 = tool result
T9 = first complete sentence
T10 = TTS started
T11 = first audio
T12 = audio playback
```

Hitung:

```text
STT latency
STT final latency
LLM TTFT
Tool latency
TTS TTFA
End-to-end latency
```

Metric utama:

```text
T1 → T11
```

yaitu:

> user selesai bicara → Anna mulai bersuara.

---

# 22. TARGET LATENCY

Gunakan target awal berikut sebagai benchmark engineering:

| Metric                  |                  Target |
| ----------------------- | ----------------------: |
| Speech-end detection    |            < 300–500 ms |
| STT final               |            < 500–800 ms |
| Hermes TTFT             |            < 300–700 ms |
| Local tool call         |            < 100–500 ms |
| First sentence ready    | < 1 s setelah LLM mulai |
| TTS TTFA                |            < 300–500 ms |
| End-to-end simple query |          **~1–2 detik** |
| Barge-in response       |            **< 300 ms** |

Target harus diuji, bukan diasumsikan.

Jika hardware tidak mampu mencapai target, laporkan angka aktual.

---

# 23. RESOURCE PROFILING

Audit:

```text
CPU
RAM
VRAM
GPU utilization
GPU memory
network
disk I/O
```

Identifikasi apakah STT, LLM, dan TTS saling berebut GPU.

Buat tabel:

| Component | CPU | RAM | GPU | VRAM | Latency |
| --------- | --: | --: | --: | ---: | ------: |
| STT       |   ? |   ? |   ? |    ? |       ? |
| Hermes    |   ? |   ? |   ? |    ? |       ? |
| TTS       |   ? |   ? |   ? |    ? |       ? |

Cari bottleneck aktual.

---

# 24. LOCAL-FIRST

Prioritaskan:

```text
Local inference
```

dibanding API cloud jika kualitas masih memadai.

Tujuan:

* latency rendah;
* privacy;
* biaya rendah;
* tidak tergantung internet;
* predictable performance.

Namun jangan mengganti implementation yang sudah stabil tanpa bukti benchmark.

---

# 25. MODEL EVALUATION

Identifikasi model STT dan TTS yang digunakan sekarang.

Jika ada alternatif yang lebih cocok, bandingkan minimal:

### STT

* faster-whisper;
* Whisper variants;
* distil-whisper;
* model STT Indonesia yang relevan.

### TTS

* Piper;
* Kokoro;
* model TTS Indonesia yang relevan;
* engine streaming lokal lain yang kompatibel.

Bandingkan:

```text
Latency
Quality
Indonesian pronunciation
RAM
VRAM
CPU
GPU
Streaming
Licensing
Integration complexity
```

Jangan mengganti model hanya berdasarkan popularitas.

---

# 26. FAILURE HANDLING

Audit:

* microphone permission denied;
* STT timeout;
* TTS timeout;
* model unavailable;
* GPU OOM;
* network failure;
* malformed audio;
* empty transcript;
* transcript confidence rendah;
* user berhenti terlalu cepat;
* user berbicara ketika Anna sedang berbicara.

Pastikan voice UI tidak masuk keadaan:

```text
Loading...
Loading...
Loading...
```

tanpa recovery.

---

# 27. UX STATE MACHINE

Audit atau desain state machine:

```text
IDLE
 │
 ▼
LISTENING
 │
 ▼
TRANSCRIBING
 │
 ▼
THINKING
 │
 ▼
TOOL_EXECUTING
 │
 ▼
SPEAKING
 │
 ├──── user interrupts ────► LISTENING
 │
 └──── finished ───────────► IDLE
```

Tambahkan:

```text
ERROR
CANCELLED
```

State harus terlihat jelas pada UI.

---

# 28. PERCEIVED HUMAN BEHAVIOR

Anna jangan terasa seperti:

```text
User
 ↓
[WAIT 5 seconds]
 ↓
Anna response
```

Target:

```text
User finishes
      ↓
short natural pause
      ↓
Anna starts speaking
      ↓
continues streaming
```

Pertimbangkan micro-feedback seperti:

* subtle listening indicator;
* speaking indicator;
* short natural pause;
* audio streaming;
* visual waveform;
* partial transcript.

Hindari fake loading animation yang tidak merepresentasikan proses sebenarnya.

---

# 29. JANGAN MERUSAK DASHBOARD

Perubahan harus:

* non-destructive;
* backward compatible;
* tidak mengganggu chat text;
* tidak mengganggu chart;
* tidak mengganggu map;
* tidak mengganggu report;
* tidak mengubah Business Data Engine;
* tidak mengubah Hermes Gateway tanpa alasan;
* tidak mengubah SPATIAL MAP panel kecuali diperlukan;
* tidak menghilangkan existing functionality.

Pisahkan voice pipeline dari business data pipeline.

Prinsip:

```text
Voice Layer
     ↓
Anna Runtime
     ↓
Business Data Engine
```

Voice layer tidak boleh mengetahui detail database.

---

# 30. AUDIT OUTPUT

Setelah audit, berikan laporan dengan struktur:

## A. Current Architecture

Diagram implementasi aktual.

## B. Current STT

* engine;
* model;
* pipeline;
* latency;
* bottleneck.

## C. Current TTS

* engine;
* model;
* pipeline;
* latency;
* bottleneck.

## D. End-to-End Voice Pipeline

Diagram lengkap.

## E. Latency Breakdown

```text
Speech end
 ↓
STT
 ↓
LLM
 ↓
Tool
 ↓
TTS
 ↓
Audio
```

dengan angka aktual.

## F. Critical Bottlenecks

Gunakan severity:

```text
CRITICAL
HIGH
MEDIUM
LOW
```

## G. Recommended Architecture

Berikan architecture baru yang paling optimal.

## H. Model Recommendation

Bandingkan model STT/TTS aktual dengan kandidat alternatif.

## I. Implementation Plan

Urutkan:

```text
Phase 1 — instrumentation
Phase 2 — VAD
Phase 3 — streaming STT
Phase 4 — streaming LLM
Phase 5 — streaming TTS
Phase 6 — barge-in
Phase 7 — optimization
Phase 8 — stress testing
```

## J. Expected Performance

Berikan estimasi berdasarkan benchmark aktual.

Jangan mengklaim angka yang belum diuji.

---

# 31. ACCEPTANCE CRITERIA

Audit dianggap berhasil apabila dapat menjawab secara konkret:

1. Berapa latency STT sekarang?
2. Berapa latency TTS sekarang?
3. Berapa Hermes TTFT?
4. Berapa end-to-end latency?
5. Apakah STT streaming?
6. Apakah TTS streaming?
7. Apakah VAD digunakan?
8. Apakah end-of-speech optimal?
9. Apakah Anna dapat di-interrupt?
10. Apakah audio queue dapat dibatalkan?
11. Apakah echo cancellation tersedia?
12. Apakah STT dan TTS berebut GPU dengan Hermes?
13. Apa bottleneck terbesar?
14. Apa perubahan dengan impact terbesar?
15. Berapa latency setelah optimasi yang realistis?

---

# 32. ATURAN PENTING

**Jangan langsung coding.**

Urutan kerja:

```text
INSPECT
   ↓
UNDERSTAND
   ↓
MEASURE
   ↓
IDENTIFY BOTTLENECK
   ↓
DESIGN
   ↓
PROPOSE
   ↓
ONLY THEN IMPLEMENT
```

Jangan melakukan refactor besar tanpa bukti bahwa bagian tersebut merupakan bottleneck.

Jangan mengganti STT/TTS yang sudah ada sebelum membandingkan latency dan kualitasnya.

Jangan mengoptimalkan benchmark sintetis jika perceived latency pengguna justru tetap buruk.

Prioritas akhir:

> **Anna harus terasa cepat bagi manusia, bukan sekadar cepat menurut benchmark.**

---

# HASIL AKHIR YANG DIINGINKAN

Setelah audit, berikan satu rekomendasi final:

> **"Untuk ana-hermes-dashboard, konfigurasi STT + TTS + voice pipeline yang paling tepat adalah ..."**

sertakan:

* STT engine;
* STT model;
* VAD;
* audio transport;
* LLM streaming;
* TTS engine;
* TTS model;
* buffering strategy;
* barge-in strategy;
* GPU/CPU placement;
* latency target;
* perubahan kode yang diperlukan.

Jika ada beberapa pilihan, prioritaskan:

1. **Best latency**
2. **Best quality**
3. **Best cost/performance**

Tujuan akhirnya adalah:

```text
🎤 User speaks
      ↓
   STT cepat
      ↓
 Hermes Agent
      ↓
 Tool / Business Engine
      ↓
 response streaming
      ↓
   TTS streaming
      ↓
🔊 Anna speaks

Target:
Natural
Fast
Interruptible
Low latency
Stable
```
