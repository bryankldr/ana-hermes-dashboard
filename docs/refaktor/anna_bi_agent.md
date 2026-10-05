ANNA jangan diberi tugas “menulis narasi dari angka”. Itu terlalu bebas dan berisiko menghasilkan interpretasi yang tidak didukung data.

Untuk konteks produksi getah pinus, saya akan membangun ANNA sebagai Business Intelligence Narrator yang bekerja di atas KPI semantic layer.

1. Prinsip utama ANNA

ANNA harus selalu mengikuti rantai:

DATA
  ↓
KPI TERDEFINISI
  ↓
PERBANDINGAN
  ↓
TEMUAN
  ↓
INTERPRETASI
  ↓
NARASI BISNIS

Bukan:

DATA
  ↓
LLM menebak cerita

Contoh:

Produksi aktual   : 82.450 kg
Target            : 95.000 kg
Achievement       : 86,79%
Gap               : -12.550 kg

ANNA boleh mengatakan:

Produksi getah mencapai 82,45 ton atau 86,79% dari target, sehingga masih terdapat gap 12,55 ton terhadap target periode berjalan.

ANNA tidak boleh langsung mengatakan:

Produksi rendah karena penyadap kurang disiplin.

Karena data tersebut belum membuktikan penyebabnya.

Kalau data memang menunjukkan:

421 petak bongkor
→ 380 tidak memiliki penyadap

baru ANNA dapat mengatakan:

Pada dataset yang sedang dianalisis, sebagian besar petak bongkor tidak memiliki penyadap. Kondisi ini menunjukkan adanya keterkaitan antara cakupan penyadap dan status petak, tetapi belum cukup untuk menyimpulkan bahwa ketiadaan penyadap merupakan satu-satunya penyebab rendahnya produksi.

Itulah perbedaan BI narrative dengan sekadar AI-generated text.

2. ANNA harus memiliki 4 tingkat kebenaran

Saya sangat menyarankan setiap narasi internal ANNA memiliki klasifikasi:

LEVEL 1 — FACT

Langsung berasal dari data.

Produksi = 82.450 kg
Target = 95.000 kg
Achievement = 86,79%

Bahasa:

Produksi aktual tercatat sebesar 82,45 ton.

LEVEL 2 — CALCULATION

Dihitung dari data yang tersedia.

Gap = actual - target
     = 82.450 - 95.000
     = -12.550 kg

Bahasa:

Terdapat gap sebesar 12,55 ton terhadap target.

LEVEL 3 — COMPARATIVE FINDING

Hasil membandingkan data.

Misalnya:

September 2026 : 82,45 ton
Agustus 2026   : 74,20 ton

ANNA:

Produksi September meningkat 11,1% dibanding Agustus.

Ini masih objektif karena berasal dari perhitungan.

LEVEL 4 — INTERPRETATION

Penjelasan bisnis berdasarkan hubungan data.

Misalnya tersedia:

Produksi ↑ 11,1%

Aktivitas ↑ 15%

Jumlah penyadap aktif ↑ 4%

Luas aktif relatif tetap

ANNA boleh mengatakan:

Peningkatan produksi berjalan bersamaan dengan peningkatan aktivitas penyadapan. Dalam data periode ini, keduanya bergerak searah.

Tetapi jangan:

Peningkatan aktivitas menyebabkan produksi meningkat.

Karena korelasi bukan kausalitas.

3. KPI jangan diberikan ke ANNA sebagai angka mentah saja

Business Engine sebaiknya menghasilkan KPI semantic object.

Misalnya:

{
  "kpi": "production_achievement",
  "label": "Pencapaian Produksi",
  "value": 86.79,
  "unit": "%",
  "actual": 82450,
  "target": 95000,
  "gap": -12550,
  "period": {
    "month": 9,
    "year": 2026,
    "periode": "P1"
  },
  "scope": {
    "divre": "Jawa Timur",
    "kph": "Banyuwangi Barat"
  },
  "calculation": "actual / target * 100",
  "source": "business_engine",
  "confidence": "direct"
}

ANNA tidak perlu menebak:

"Apa arti angka 86.79?"

Sistem sudah memberitahu bahwa itu:

Pencapaian Produksi = actual / target × 100

Ini sangat penting.

4. KPI produksi getah sebaiknya mempunyai semantic definition

Contoh struktur:

PRODUKSI
│
├── Produksi Aktual
├── Target Produksi
├── Achievement
├── Gap Produksi
│
├── Produktivitas
│   ├── kg/ha
│   ├── kg/penyadap
│   └── kg/petak
│
├── Coverage
│   ├── petak aktif
│   ├── petak bongkor
│   ├── petak idle
│   └── petak tanpa penyadap
│
└── Aktivitas
    ├── rencana
    ├── realisasi
    └── achievement aktivitas

ANNA kemudian dapat menghubungkan KPI tersebut.

5. Presentasi KPI sebaiknya tidak hanya angka

Misalnya dashboard menampilkan:

┌─────────────────────────────────────────────┐
│ PRODUKSI                                     │
│                                              │
│ 82,45 TON                                    │
│ 86,79% TARGET                                │
│                                              │
│ Target 95,00 TON                             │
│ Gap 12,55 TON                                │
└─────────────────────────────────────────────┘

ANNA menghasilkan narasi:

Produksi periode berjalan mencapai 82,45 ton atau 86,79% dari target 95 ton. Masih terdapat gap 12,55 ton terhadap target.

Kemudian jika ada data historis:

Dibanding periode sebelumnya, produksi meningkat 8,4%, sementara pencapaian target masih berada pada 86,79%.

Kemudian jika ada data pendukung:

Peningkatan produksi berlangsung bersamaan dengan kenaikan realisasi aktivitas penyadapan sebesar 6,2%.

Kemudian ANNA dapat melanjutkan:

Area yang perlu diperhatikan berada pada kelompok petak dengan aktivitas rendah, yang menyumbang 31% dari luas petak yang sedang diANNAlisis.

Perhatikan bahwa setiap kalimat punya evidence.

6. Jangan biarkan ANNA membuat "narasi kosong"

Saya akan memberikan aturan keras:

Setiap klaim faktual dalam narasi harus memiliki
nilai atau evidence dari Dashboard Context.

Misalnya ANNA mengatakan:

"Produksi mengalami penurunan."

Harus ada:

current = 82.450
previous = 91.200
change = -9.6%

Jika previous tidak tersedia:

"Produksi saat ini tercatat 82,45 ton. Data pembanding periode sebelumnya tidak tersedia pada konteks saat ini."

Bukan:

"Produksi mengalami penurunan."

7. ANNA sebaiknya memiliki "Evidence Trace"

Ini akan sangat berguna.

Secara internal:

{
  "statement": "Produksi mencapai 86,79% dari target",
  "evidence": [
    "production.actual",
    "production.target"
  ],
  "calculation": "actual / target * 100",
  "type": "calculated_fact"
}

Kemudian:

{
  "statement": "Produksi meningkat dibanding periode sebelumnya",
  "evidence": [
    "production.current",
    "production.previous"
  ],
  "calculation": "(current - previous) / previous",
  "type": "comparative_fact"
}

Dengan demikian ANNA tidak sekadar menghasilkan teks, tetapi menghasilkan:

CLAIM
 ↓
EVIDENCE
 ↓
CALCULATION
 ↓
NARRATIVE

Ini jauh lebih aman.

8. Berikan ANNA "Business Narrative Rules"

Misalnya:

Jika target tersedia
Actual + Target
→ Achievement + Gap

ANNA dapat mengatakan:

"Pencapaian produksi berada pada X% dari target dengan gap Y."

Jika data periode sebelumnya tersedia
Current + Previous
→ Growth / Decline

ANNA dapat mengatakan:

"Produksi berubah X% dibanding periode sebelumnya."

Jika aktivitas tersedia
Production + Activity
→ Relationship analysis

ANNA:

"Produksi dan realisasi aktivitas sama-sama meningkat pada periode ini."

Bukan:

"Aktivitas menyebabkan produksi meningkat."

Jika penyadap tersedia
Production + Active Tapper
→ Productivity per Tapper

ANNA dapat menghitung:

kg / penyadap

jika definisi dan denominator memang tersedia.

9. Narasi sebaiknya memiliki struktur tetap

Saya menyarankan ANNA menggunakan pola:

┌──────────────────────────────────────┐
│ EXECUTIVE SUMMARY                    │
├──────────────────────────────────────┤
│ Apa yang terjadi?                    │
├──────────────────────────────────────┤
│ PERFORMANCE                          │
│ Bagaimana terhadap target?           │
├──────────────────────────────────────┤
│ TREND                                │
│ Bagaimana dibanding periode lain?    │
├──────────────────────────────────────┤
│ DRIVER / ASSOCIATED FACTORS          │
│ Data apa yang bergerak bersamaan?    │
├──────────────────────────────────────┤
│ ATTENTION                            │
│ Area mana yang perlu diperhatikan?   │
├──────────────────────────────────────┤
│ DATA LIMITATION                      │
│ Apa yang belum dapat disimpulkan?    │
└──────────────────────────────────────┘

Tidak semua bagian harus selalu muncul.

ANNA hanya menampilkan bagian yang memiliki data pendukung.

10. Contoh narasi yang saya inginkan untuk ANNA

Misalnya data sebenarnya:

Periode        : P1 September 2026
KPH            : Banyuwangi Barat

Produksi       : 82.450 kg
Target         : 95.000 kg
Achievement    : 86,79%
Gap            : 12.550 kg

Periode lalu   : 76.300 kg
Growth         : +8,06%

Aktivitas      : +5,7%
Penyadap aktif : +2,1%

Petak bongkor  : 734
Luas bongkor   : 481,2 ha

ANNA:

Produksi P1 September mencapai 82,45 ton atau 86,79% dari target 95 ton. Masih terdapat gap sebesar 12,55 ton.

Dibanding periode sebelumnya, produksi meningkat 8,06%. Pada periode yang sama, realisasi aktivitas meningkat 5,7% dan jumlah penyadap aktif meningkat 2,1%. Ketiga indikator tersebut bergerak positif pada periode ini.

Di sisi kondisi petak, terdapat 734 petak berstatus bongkor dengan luas 481,2 ha. Data ini menunjukkan adanya area yang perlu diperhatikan dalam evaluasi operasional.

Berdasarkan data yang tersedia, peningkatan aktivitas dan penyadap terjadi bersamaan dengan peningkatan produksi. Data tersebut belum cukup untuk menetapkan hubungan sebab-akibat.

Ini sudah terasa seperti business intelligence, bukan chatbot yang membaca angka.

11. Bahkan ANNA dapat membuat "Business Insight"

Tetapi insight harus berasal dari rule + evidence.

Contoh:

Production achievement < 90%
AND
Activity achievement < 90%

ANNA:

Perhatian: pencapaian produksi masih di bawah target, sementara realisasi aktivitas juga belum mencapai target. Keduanya merupakan indikator yang perlu dievaluasi secara bersamaan pada periode ini.

Bukan:

"Penyebab produksi rendah adalah aktivitas penyadapan."

12. Untuk kasus petak, ANNA bisa jauh lebih menarik

Misalnya:

12.480 petak

734 bongkor
481,2 ha

421 tanpa penyadap
228 satu penyadap
85 multi penyadap

ANNA dapat menyampaikan:

Dari 12.480 petak yang dianalisis, 734 petak atau 5,88% berstatus bongkor dengan luas 481,2 ha.

Dari kelompok tersebut, 421 petak tidak memiliki penyadap. Artinya, sekitar 57,4% petak bongkor dalam dataset ini berada pada kondisi tanpa penyadap.

Komposisi ini menunjukkan bahwa isu ketersediaan penyadap merupakan karakteristik yang dominan pada kelompok petak bongkor. Namun, data ini belum membuktikan bahwa kondisi tersebut merupakan penyebab tunggal status bongkor.

Ini adalah narasi BI yang kuat karena:

angka → rasio → konteks → interpretasi → batasan.

13. Saya akan membuat "Narrative Engine", bukan membebankan semuanya ke LLM

Arsitekturnya:

              DATABASE
                  │
                  ▼
        BUSINESS DATA ENGINE
                  │
                  ▼
            KPI ENGINE
                  │
                  ▼
       ┌─────────────────────┐
       │ KPI SEMANTIC MODEL  │
       │                     │
       │ value               │
       │ target              │
       │ gap                 │
       │ trend               │
       │ comparison          │
       │ scope               │
       │ evidence            │
       └──────────┬──────────┘
                  │
                  ▼
          NARRATIVE ENGINE
                  │
          ┌───────┴────────┐
          │                │
       FACTS          INTERPRETATION
          │                │
          └───────┬────────┘
                  ▼
                 ANNA
                  │
                  ▼
        NATURAL BUSINESS LANGUAGE

LLM/ANNA berfungsi sebagai natural-language realization layer.

Jadi bukan LLM yang menentukan angka, rumus, atau business rule.

14. Ini juga harus masuk ke SOUL/AGENT rules ANNA

Saya akan menambahkan aturan pendek seperti ini:

## Business Intelligence Integrity

ANNA must never invent data, causes, trends, or business conclusions.

Every factual statement must be supported by the current dashboard
context or an explicitly provided business dataset.

ANNA must distinguish:
- observed facts
- calculated metrics
- comparisons
- interpretations
- hypotheses

ANNA may calculate only when the required inputs and business
definition are explicitly available.

ANNA must never present correlation as causation.

If the available data is insufficient to support a conclusion,
ANNA must say so.

Business rules, KPI definitions, calculations, and data aggregation
belong to the Business Data Engine, not to ANNA.

ANNA's role is to translate verified business data into clear,
natural, decision-oriented business language.
Intinya

Untuk proyek Anda, jangan menjadikan ANNA sebagai "AI yang pintar membuat insight".

Jadikan ANNA sebagai:

AI yang tidak boleh salah terhadap fakta, tetapi sangat pintar menerjemahkan fakta menjadi bahasa bisnis.

Formula yang saya rekomendasikan:

                  VERIFIED DATA
                       │
                       ▼
                KPI SEMANTICS
                       │
                       ▼
                COMPARISON
                       │
                       ▼
                  FINDINGS
                       │
                       ▼
              BUSINESS INTERPRETATION
                       │
                       ▼
                 ANNA NARRATIVE

Dengan pendekatan ini, ketika manajemen bertanya "Bagaimana kondisi produksi getah saat ini?", ANNA tidak akan memberikan jawaban generik. Ia akan membangun narasi dari scope → actual → target → achievement → gap → trend → operational context → relevant relationships → limitation, dan setiap klaim dapat ditelusuri kembali ke data yang mendasarinya.