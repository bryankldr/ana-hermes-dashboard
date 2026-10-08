Hasil ini sangat berguna. Dari angka yang kamu berikan, masalah utama Anna bukan output token, melainkan input/context bloat dan tool-loop.

Yang paling mencolok:

Static prompt saja: ~55K token
T1: marginal ~197K input
T2: marginal ~206K input
T3: marginal ~978K input
T3 hanya menghasilkan 8.969 output token, tetapi mengonsumsi hampir 1 juta input token.

Artinya, sebelum mengoptimalkan model, kita perlu membedah pipeline context Anna.

Diagnosis
Test	Input marginal	Output	Tool calls	Masalah
T1 bisnis	~197K	811	2	context terlalu besar
T2 chart	~206K	2,357	2	relatif sehat, tapi masih besar
T3 laporan	~978K	8,969	14	critical

T3 adalah red flag.

Dengan static context sekitar 55K token, secara kasar Anna sudah membawa baseline besar ke setiap turn. Kemudian ada:

SOUL
SKILL_simoge
SKILL_hud
simoge_db
ana_chart
ana_simoge_tool
ana_kpi
persona
context_block
wiki_block
tool schema
history
tool results
DB rows

Dan yang lebih serius: tool loop T3 membaca skill/file berulang kali.

Jadi saya tidak akan mulai dengan mengganti model atau quantization.

Saya akan membangun Context Budget untuk Anna.

Target yang saya sarankan

Untuk query bisnis sederhana seperti T1:

Sekarang:       ~197K input
Target:         30–60K

Chart:

Sekarang:       ~206K
Target:         40–70K

Report:

Sekarang:       ~978K
Target:         100–200K

Bahkan untuk laporan kompleks, 1M input per request terlalu mahal secara komputasi, meskipun context window model mendukung 1M.

1. Static prompt 55K harus dipangkas

Ini prioritas nomor satu.

Dari:

223,696 chars
≈ 55K token

Saya akan memecahnya menjadi:

ANNA CORE
~3–5K

SIMOGE CORE
~5–8K

TASK KNOWLEDGE
~2–8K

TOOLS
minimal

DYNAMIC DATA
hasil query saja

Jadi bukan:

Anna
 ↓
load seluruh SIMOGE
 ↓
load seluruh KPI
 ↓
load seluruh DB schema
 ↓
load seluruh chart skill
 ↓
load seluruh HUD skill

tetapi:

User
 ↓
Intent Router
 ↓
"petak effectiveness"
 ↓
ambil knowledge petak effectiveness
 ↓
Business Tool
 ↓
Anna
2. simoge_db 67.8K chars adalah kandidat besar untuk dipangkas

Ini kemungkinan salah satu sumber pemborosan terbesar.

Anna tidak membutuhkan seluruh database knowledge untuk setiap pertanyaan.

Misalnya user:

Berapa total petak efektif 2026?

Anna cukup membutuhkan:

ENTITY
petak

METRIC
efektivitas petak

PERIOD
2026

BUSINESS RULE
efektif = terpenuhi

TOOL
petak_effectiveness

Tidak perlu membaca definisi:

getah_drum
getah_pengangkutan
getah_perni
getah_penerimaan
...

Jadi simoge_db sebaiknya menjadi retrievable knowledge, bukan static prompt.

3. SKILL_simoge 44.6K juga terlalu besar

Skill seharusnya memberi tahu Anna:

KAPAN menggunakan tool
APA input tool
APA output tool
BAGAIMANA interpretasi

Bukan menjadi manual SIMOGE lengkap.

Saya akan targetkan:

SKILL_simoge
44.651 chars
        ↓
~8–15K chars

Sisanya dipindahkan menjadi knowledge/retrieval.

4. ana_chart 65K sangat besar

Untuk membuat chart sederhana, Anna tidak perlu 65K karakter instruksi.

Idealnya chart skill hanya seperti:

Chart task:
1. Identify chart type.
2. Call chart tool.
3. Pass dimension + metric + values.
4. Do not calculate data independently.
5. Return chart state.

Detail seperti:

semua kemungkinan chart
styling
layout
edge cases
frontend implementation
API internals

tidak perlu masuk context setiap kali.

Target:

65K
 ↓
5–10K
5. Yang paling penting: hentikan tool loop T3

Ini menurut saya problem terbesar.

T3:

14 tool calls

dan:

context 113K → 149K

serta marginal:

978,377 input

Ini mengindikasikan kemungkinan pola:

Anna
 ↓
skill_view
 ↓
read_file
 ↓
search
 ↓
terminal
 ↓
execute_code
 ↓
...
 ↓
skill_view
 ↓
read_file
 ↓
...

Untuk tugas:

Buat laporan efektivitas sadap 2026

seharusnya tidak seperti itu.

Target architecture:

User
 │
 ▼
Anna
 │
 ├── identify report intent
 │
 ▼
report tool
 │
 ├── query business engine
 ├── calculate KPI
 ├── generate chart
 ├── generate report state
 │
 ▼
Anna
 │
 ▼
Narrative

Idealnya:

1–3 business/tool calls

bukan 14.

6. Pisahkan "Anna berpikir" dari "Anna mencari dokumentasi"

Ini sangat penting.

Saat ini Anna tampaknya bisa melakukan:

user
 ↓
Anna
 ↓
baca skill
 ↓
baca file
 ↓
search
 ↓
terminal

Padahal knowledge tentang SIMOGE seharusnya sudah tersedia melalui mekanisme retrieval yang lebih deterministik.

Saya lebih menyukai:

                  ┌───────────────┐
                  │ User Question │
                  └───────┬───────┘
                          ↓
                  Intent Classifier
                          ↓
             ┌────────────┴────────────┐
             ↓                         ↓
        Business Query             Knowledge
             ↓                         ↓
       Business Engine             Retriever
             └────────────┬────────────┘
                          ↓
                        Anna
                          ↓
                     Interpretation

Anna tidak perlu membuka file secara manual untuk mengetahui bagaimana menghitung KPI yang sudah terdefinisi.

7. Buat "Business Context Packet"

Ini menurut saya akan sangat cocok dengan arsitektur ana-hermes-dashboard kamu.

Daripada Anna menerima raw data:

{
  "rows": [
    ...
  ]
}

dashboard mengirim:

{
  "intent": "petak_effectiveness",
  "period": {
    "year": 2026
  },
  "scope": {
    "divre": null,
    "kph": null,
    "bkph": null,
    "rph": null
  },
  "kpi": {
    "total_petak": 810,
    "efektif": 492,
    "tidak_efektif": 318,
    "efektivitas_pct": 60.74
  },
  "evidence": {
    "source": "business_engine",
    "rows_used": 810
  }
}

Anna tinggal menjelaskan:

Dari 810 petak, 492 efektif atau 60,74%, sementara 318 belum efektif.

Ini jauh lebih hemat daripada memberi Anna 810 row.

8. Gunakan dua jenis context

Saya sarankan Anna punya:

Persistent context
ANNA_CORE
SIMOGE ontology core
business principles
behavior
Ephemeral context
current user question
current dashboard state
current map state
current KPI
current tool result
current report

Ephemeral context jangan dibawa ke task berikutnya kalau tidak diperlukan.

9. Chart dan report jangan membuat Anna membawa data dua kali

Sekarang T2/T3 kemungkinan ada pola:

Business data
 ↓
Anna
 ↓
execute_code
 ↓
chart
 ↓
result kembali ke Anna

Kalau data besar, terjadi:

data → model
     → tool
     → model

Lebih baik:

Business Engine
      ↓
Chart Engine
      ↓
Chart state
      ↓
Dashboard

Anna hanya menerima:
"chart berhasil dibuat"

Kemudian Anna tidak perlu melihat seluruh chart dataset kecuali user meminta analisis terhadapnya.

10. Buat tiga mode context Anna

Saya akan desain:

ASSET_MODE

Untuk:

tampilkan chart

minimal reasoning
minimal knowledge
minimal output
BI_MODE

Untuk:

berapa produksi?

ontology relevant
KPI
business result
short reasoning
REPORT_MODE

Untuk:

buat laporan efektivitas lengkap

KPI
comparisons
chart
map
narrative
evidence

Dengan demikian query sederhana tidak membawa context report.

Prioritas implementasi

Kalau kita mengerjakan ini di ana-hermes-dashboard, urutannya saya sarankan:

P0 ─────────────────────────────────────

1. ukur token setiap komponen
2. pisahkan static vs dynamic context
3. kurangi static prompt 55K
4. hentikan tool-loop read/search berulang

P1 ─────────────────────────────────────

5. ubah simoge_db menjadi retrieval
6. pecah SKILL_simoge
7. pecah ana_chart
8. buat Business Context Packet

P2 ─────────────────────────────────────

9. report tool menjadi atomic operation
10. chart tool tidak mengembalikan raw data
11. session/context lifecycle
12. compression tuning

P3 ─────────────────────────────────────

13. caching
14. prefix caching
15. model routing
16. token/cost observability
Target akhir

Saya ingin hasil benchmark Anna berubah kira-kira menjadi:

Test	Sekarang	Target
T1 business	197K	20–50K
T2 chart	206K	30–60K
T3 report	978K	80–200K
T1 tool calls	2	1
T2 tool calls	2	1
T3 tool calls	14	2–4

Kalau ini tercapai, performa Anna akan berubah cukup drastis tanpa mengganti model.

Yang paling menarik adalah T3. Saya akan menjadikannya target pertama, karena 978K input / 8.969 output menunjukkan Anna sedang menggunakan LLM sebagai orchestrator + dokumentasi browser + data analyst + report builder sekaligus. Padahal sebagian besar pekerjaan itu seharusnya dilakukan oleh Business Data Engine dan dashboard.

Dengan kata lain:

Jangan membuat Anna lebih pintar dengan memberinya lebih banyak context. Buat dashboard lebih deterministik sehingga Anna membutuhkan lebih sedikit context.

Untuk arsitektur Anna yang kamu bangun, itu akan menjadi optimasi token sekaligus optimasi reliability.