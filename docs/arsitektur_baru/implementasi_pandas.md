# Arsitektur Business Data Engine + Pandas untuk Anna–Hermes

## 1. Tujuan

Menambahkan **Pandas sebagai Analytical Processing Layer** pada arsitektur Anna–Hermes untuk:

* melakukan pemrosesan data secara deterministik di luar LLM;
* mengurangi jumlah data mentah yang masuk ke context LLM;
* mengurangi kebutuhan reasoning LLM untuk kalkulasi;
* mengurangi jumlah query berulang ke database;
* memungkinkan analisis dataset secara iteratif;
* menghasilkan analytical result yang ringkas;
* mengurangi penggunaan input dan output token;
* meningkatkan kecepatan respons;
* meningkatkan konsistensi perhitungan;
* mendukung chart, map, report, dan presentation dari dataset analitis yang sama.

Pandas **bukan pengganti SQL** dan bukan pengganti LLM.

Pembagian tanggung jawab:

> **Database owns raw data.**
> **Business Data Engine owns business facts and rules.**
> **Pandas owns analytical processing.**
> **Anna owns interpretation.**
> **Dashboard owns visualization.**

---

# 2. Masalah Arsitektur Tanpa Pandas

Pada arsitektur sederhana, Anna dapat menerima dataset yang terlalu besar dari Business Data Engine.

Contoh:

```text
User
 ↓
Anna
 ↓
Business Data Engine
 ↓
10.000–50.000 records
 ↓
Hermes / LLM Context
 ↓
LLM melakukan filtering
LLM melakukan grouping
LLM melakukan calculation
LLM melakukan comparison
LLM melakukan reasoning
```

Masalah:

1. Banyak data masuk ke context.
2. Input token meningkat.
3. Context menjadi lebih besar.
4. Reasoning LLM menjadi lebih berat.
5. Output/tool result dapat menjadi panjang.
6. Respons menjadi lebih lambat.
7. Biaya inference dapat meningkat.
8. Risiko kesalahan kalkulasi meningkat.

LLM seharusnya tidak digunakan sebagai mesin dataframe.

---

# 3. Arsitektur Token-Efficient

Arsitektur yang direkomendasikan:

```text
                              USER
                                │
                                ▼
                         ┌─────────────┐
                         │    ANNA     │
                         │     LLM     │
                         └──────┬──────┘
                                │
                         Intent / Plan
                                │
                                ▼
                    ┌───────────────────────┐
                    │ Business Data Engine  │
                    │                       │
                    │ SQL                   │
                    │ JOIN                  │
                    │ Business Rules        │
                    │ KPI Definition        │
                    │ Validation            │
                    └───────────┬───────────┘
                                │
                         Valid Dataset
                                │
                                ▼
                    ┌───────────────────────┐
                    │    Pandas Engine      │
                    │                       │
                    │ Filter                │
                    │ GroupBy               │
                    │ Aggregate             │
                    │ Pivot                 │
                    │ Compare               │
                    │ Ranking               │
                    │ Statistics            │
                    │ Anomaly Detection     │
                    └───────────┬───────────┘
                                │
                       Small Analytical Result
                                │
                                ▼
                         ┌─────────────┐
                         │    ANNA     │
                         │Interpretation│
                         └──────┬──────┘
                                │
                ┌───────────────┼────────────────┐
                ▼               ▼                ▼
              Chart            Map             Report
                │               │                │
                └───────────────┼────────────────┘
                                ▼
                              USER
```

Prinsip utamanya:

```text
RAW DATA
   ↓
Business Data Engine
   ↓
Pandas
   ↓
SMALL RESULT
   ↓
LLM
```

Bukan:

```text
RAW DATA
   ↓
LLM
```

---

# 4. Static Context vs Dynamic Context

Penting untuk membedakan dua sumber penggunaan token.

## 4.1 Static Context

Static context adalah informasi yang selalu atau sering diberikan kepada Anna, misalnya:

```text
SOUL
Business Knowledge
SIMOGE Knowledge
Database Schema
KPI Definitions
Tool Instructions
Dashboard Instructions
Chart Instructions
Map Instructions
```

Jika static prompt terlalu besar, Pandas **tidak otomatis menguranginya**.

Contohnya:

```text
Static Context
≈ 55k token
```

Pandas tidak mengubah angka tersebut secara langsung.

---

## 4.2 Dynamic Context

Dynamic context adalah data yang diperoleh ketika user bertanya:

```text
Database Result
Tool Result
Dataset
Analytical Result
Chart Metadata
Map Metadata
```

Di sinilah Pandas dapat memberikan penghematan besar.

### Sebelum

```text
Database
   ↓
50.000 rows
   ↓
LLM Context
```

### Sesudah

```text
Database
   ↓
50.000 rows
   ↓
Pandas
   ↓
20 rows analytical result
   ↓
LLM Context
```

Dengan demikian:

> **Pandas tidak terutama mengurangi static prompt; Pandas mengurangi dynamic data context yang harus diproses LLM.**

---

# 5. Contoh Penghematan Context

Misalkan Business Data Engine menghasilkan:

```text
20.000 records
```

Tanpa Pandas:

```text
20.000 records
        ↓
LLM
        ↓
Filtering
Grouping
Calculation
Comparison
Ranking
        ↓
Answer
```

Dengan Pandas:

```text
20.000 records
        ↓
Pandas
        ↓
Aggregation
Comparison
Ranking
Anomaly Detection
        ↓
15 analytical records
        ↓
LLM
        ↓
Interpretation
```

LLM hanya menerima informasi yang relevan untuk menjawab pertanyaan.

---

# 6. Contoh Kasus Produksi Getah

User:

> Mengapa produksi Mei tidak mencapai target?

Business Data Engine mengambil dataset:

```text
tanggal
bulan
tahun
kode_kph
kode_bkph
kode_rph
kode_tpg
target
realisasi
periode
produksi_p1
produksi_p2
jumlah_petak
jumlah_petak_bongkor
```

Dataset dapat berisi ribuan record.

Jangan langsung memberikan seluruh dataset kepada Anna.

Gunakan Pandas:

```text
Dataset
   │
   ├── Aggregate target
   ├── Aggregate realisasi
   ├── Calculate achievement
   ├── Compare April vs Mei
   ├── Compare P1 vs P2
   ├── Group by BKPH
   ├── Rank declining BKPH
   └── Analyze bongkor
   │
   ▼
Analytical Result
```

Contoh hasil:

```json
{
  "target": 1600,
  "realisasi": 820,
  "achievement": 51.25,
  "p2_change": -13.4,
  "bongkor": 132,
  "top_declining_bkph": [
    {
      "bkph": "BKPH A",
      "change": -21.4
    },
    {
      "bkph": "BKPH B",
      "change": -18.7
    },
    {
      "bkph": "BKPH C",
      "change": -16.2
    }
  ]
}
```

Anna kemudian menginterpretasikan hasil tersebut.

---

# 7. Penghematan Token

Secara konseptual:

## Tanpa Pandas

```text
Static Context       55k
Raw Data             20k
Tool Result           5k
Reasoning             8k
────────────────────────
Total                ~88k
```

## Dengan Pandas

```text
Static Context       55k
Raw Data              1k
Analytical Result     1k
Reasoning             3k
────────────────────────
Total                ~60k
```

Angka di atas adalah **contoh ilustratif**, bukan pengukuran aktual.

Penghematan aktual bergantung pada:

* ukuran dataset;
* kompleksitas pertanyaan;
* jumlah tool call;
* ukuran output tool;
* panjang prompt;
* model yang digunakan;
* context caching;
* strategi orchestration.

Namun mekanismenya jelas:

```text
lebih sedikit data
       ↓
lebih sedikit dynamic tokens
       ↓
lebih sedikit context processing
       ↓
lebih sedikit reasoning workload
       ↓
potensi biaya inference lebih rendah
```

---

# 8. Pandas Mengurangi Beban Reasoning LLM

Selain mengurangi input token, Pandas juga memindahkan operasi deterministik dari LLM ke Python.

Jangan meminta LLM menghitung:

```text
Hitung total setiap BKPH,
bandingkan dengan bulan sebelumnya,
hitung persentasenya,
urutkan dari yang terbesar,
kemudian cari anomali.
```

Biarkan Pandas melakukan:

```python
result = (
    df.groupby("bkph")
      .agg(
          target=("target", "sum"),
          realisasi=("realisasi", "sum")
      )
)

result["capaian"] = (
    result["realisasi"] /
    result["target"] * 100
)

result = result.sort_values(
    "capaian",
    ascending=True
)
```

LLM menerima hasil:

```text
BKPH A → 48.2%
BKPH B → 51.7%
BKPH C → 55.1%
```

Anna hanya melakukan pekerjaan yang memang membutuhkan LLM:

```text
"What does this mean?"
```

bukan:

```text
"Please calculate everything."
```

---

# 9. Batch Analytical Processing

Hindari terlalu banyak siklus:

```text
Anna
 ↓
Pandas
 ↓
Anna
 ↓
Pandas
 ↓
Anna
 ↓
Pandas
```

Karena setiap siklus dapat menghasilkan tambahan inference dan tool context.

Lebih baik:

```text
Anna
 ↓
Analytical Plan
 ↓
Business Data Engine
 ↓
Pandas
 ├── aggregation
 ├── comparison
 ├── ranking
 ├── percentage change
 ├── pivot
 └── anomaly detection
 ↓
ONE ANALYTICAL RESULT
 ↓
Anna
```

Satu analytical execution dapat menghasilkan semua informasi yang diperlukan.

---

# 10. Dataset Session

Gunakan konsep `dataset_id`.

Contoh:

```text
dataset_id =
production_analysis_2026_05
```

Alur:

```text
Business Data Engine
        │
        ▼
Create Dataset
        │
        ▼
dataset_id
        │
        ▼
Pandas Session
        │
        ├── operation 1
        ├── operation 2
        ├── operation 3
        └── operation 4
        │
        ▼
Final Analytical Result
        │
        ▼
Anna
```

Keuntungannya:

* dataset tidak perlu dikirim ulang;
* operasi dapat dilakukan di luar LLM;
* hasil intermediate tidak perlu masuk context;
* hanya final result yang diberikan ke Anna.

---

# 11. Controlled Pandas Tool

Hermes sebaiknya tidak diberikan akses Pandas tanpa batas.

Gunakan tool khusus:

```text
pandas_analysis
```

Contoh operasi:

```text
pandas_analysis
├── filter
├── group_by
├── aggregate
├── sort
├── rank
├── pivot
├── compare_period
├── percentage_change
├── statistics
├── anomaly_detection
└── describe
```

Contoh request:

```json
{
  "dataset_id": "production_analysis_2026_05",
  "operations": [
    {
      "type": "group_by",
      "columns": ["bkph"]
    },
    {
      "type": "aggregate",
      "metrics": {
        "target": "sum",
        "realisasi": "sum"
      }
    },
    {
      "type": "percentage_change",
      "column": "realisasi"
    },
    {
      "type": "rank",
      "column": "percentage_change",
      "ascending": true,
      "limit": 5
    }
  ]
}
```

Output harus ringkas dan terstruktur.

---

# 12. Jangan Mengirim Intermediate Result ke LLM

Contoh yang tidak efisien:

```text
Pandas
 ↓
Result 1
 ↓
LLM

Pandas
 ↓
Result 2
 ↓
LLM

Pandas
 ↓
Result 3
 ↓
LLM
```

Lebih baik:

```text
Pandas
 ├── Result 1
 ├── Result 2
 ├── Result 3
 ├── Result 4
 └── Result 5
       ↓
  Final Result
       ↓
      LLM
```

Dengan demikian context LLM hanya menerima hasil final.

---

# 13. Fact → Analysis → Interpretation

Output analytical engine sebaiknya dibedakan menjadi:

```json
{
  "facts": [],
  "derived_metrics": [],
  "comparisons": [],
  "rankings": [],
  "anomalies": [],
  "interpretation_inputs": []
}
```

Contoh:

```text
FACT
Realisasi Mei = 820 ton

DERIVED METRIC
Capaian = 51.25%

COMPARISON
Turun 13.4% dibanding periode sebelumnya

RANKING
BKPH A memberikan kontribusi penurunan terbesar

ANOMALY
Produksi P2 mengalami penurunan signifikan
```

Anna tidak menghitung ulang angka tersebut.

Anna menginterpretasikannya.

---

# 14. Business Rules Tetap di Business Data Engine

Pandas tidak boleh menjadi sumber utama business rules.

Contoh business rules:

```text
Status Aktif
Status Idle
Status Bongkor
P1
P2
Definisi KPI
Hierarchy DIVRE → KPH → BKPH → RPH → TPG
Definisi target
Definisi realisasi
Tahun RTT
```

Aturan tersebut harus tetap berada pada:

```text
Business Data Engine
+
Business Knowledge / Ontology
```

Pandas hanya melakukan analytical processing terhadap data dan definisi yang sudah diberikan.

---

# 15. SQL dan Pandas Harus Saling Melengkapi

Gunakan SQL untuk **data reduction sedini mungkin**.

Contoh:

```text
Database
   ↓
WHERE tahun = 2026
AND bulan = 5
AND kode_kph = ...
   ↓
Filtered Dataset
   ↓
Pandas
   ↓
Analytical Processing
```

Jangan:

```text
Database
   ↓
Entire database
   ↓
Pandas
```

Strategi ini memberikan dua lapisan efisiensi:

```text
SQL
 ↓
mengurangi jumlah data
 ↓
Pandas
 ↓
mengurangi kompleksitas data
 ↓
LLM
 ↓
menginterpretasikan hasil
```

---

# 16. Token Optimization Pipeline

Pipeline final:

```text
                         USER
                           │
                           ▼
                        ANNA
                           │
                     Intent Analysis
                           │
                           ▼
                Business Data Engine
                           │
                  SQL Data Reduction
                           │
                           ▼
                    Valid Dataset
                           │
                           ▼
                     Pandas Engine
                           │
          ┌────────────────┼────────────────┐
          │                │                │
       Aggregate        Compare          Rank
          │                │                │
          └────────────────┼────────────────┘
                           ▼
                   Compact Result
                           │
                           ▼
                        ANNA LLM
                           │
                      Interpretation
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
            Chart         Map         Report
```

Target desain:

```text
RAW DATA
   ↓
SQL
   ↓
FILTERED DATA
   ↓
PANDAS
   ↓
ANALYTICAL DATA
   ↓
LLM
```

---

# 17. Hubungan Dengan Prompt Anna yang Besar

Jika static context Anna saat ini sekitar puluhan ribu token, implementasi Pandas **bukan solusi tunggal**.

Optimasi harus dilakukan pada dua sisi:

```text
                    TOKEN BUDGET
                         │
            ┌────────────┴────────────┐
            ▼                         ▼
      Static Context            Dynamic Context
            │                         │
      Prompt Optimization          Pandas
      Context Modularization       Data Reduction
      Skill Loading                Aggregation
      Tool Description             Compression
      Context Caching              Analytical Result
```

Dengan kata lain:

> **Prompt optimization mengurangi instruction tokens.**

> **Pandas mengurangi analytical/data tokens.**

Keduanya harus dilakukan secara bersamaan.

---

# 18. Target Arsitektur Anna

Arsitektur ideal:

```text
┌───────────────────────────────────────────────┐
│                    ANNA                       │
│                                               │
│ Intent • Reasoning • Interpretation            │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
┌───────────────────────────────────────────────┐
│            BUSINESS DATA ENGINE               │
│                                               │
│ SQL • JOIN • KPI • Business Rules • Validation│
└───────────────────────┬───────────────────────┘
                        │
                 Valid Dataset
                        │
                        ▼
┌───────────────────────────────────────────────┐
│                 PANDAS ENGINE                 │
│                                               │
│ Transform • Aggregate • Compare • Rank        │
│ Pivot • Statistics • Anomaly Detection        │
└───────────────────────┬───────────────────────┘
                        │
                 Compact Result
                        │
                        ▼
┌───────────────────────────────────────────────┐
│              CHART / MAP / REPORT             │
└───────────────────────┬───────────────────────┘
                        │
                        ▼
                     USER
```

---

# 19. Prinsip Utama Implementasi

1. **SQL tetap menjadi mekanisme utama data retrieval.**
2. **Business Data Engine tetap menjadi pemilik business facts.**
3. **Business rules tidak dipindahkan ke Pandas.**
4. **Pandas digunakan untuk analytical processing.**
5. **Raw dataset tidak dikirim langsung ke LLM jika tidak diperlukan.**
6. **SQL melakukan data reduction sedini mungkin.**
7. **Pandas melakukan analytical reduction sebelum data masuk LLM.**
8. **Intermediate results tidak perlu masuk context LLM.**
9. **Gunakan dataset session untuk menghindari pengiriman ulang data.**
10. **Batch beberapa operasi Pandas dalam satu analytical execution.**
11. **LLM menerima compact analytical result.**
12. **Anna tidak melakukan kalkulasi deterministik yang dapat dilakukan Python.**
13. **Chart, Map, Report, dan Narrative menggunakan analytical result yang sama.**
14. **Semua angka harus dapat ditelusuri kembali ke dataset sumber.**
15. **Static prompt tetap harus dioptimalkan secara terpisah.**

---

# 20. Kesimpulan

Pandas memberikan keuntungan utama bukan karena membuat LLM lebih pintar, tetapi karena **memindahkan pekerjaan data processing dari LLM ke Python**.

Arsitektur yang diinginkan:

```text
                RAW DATA
                    │
                    ▼
             BUSINESS ENGINE
                    │
               SQL FILTER
                    │
                    ▼
              VALID DATASET
                    │
                    ▼
                 PANDAS
                    │
         ┌──────────┼──────────┐
         │          │          │
      Aggregate  Compare     Rank
         │          │          │
         └──────────┼──────────┘
                    ▼
             SMALL RESULT
                    │
                    ▼
                  ANNA
                    │
              Interpretation
```

Sehingga prinsip efisiensinya adalah:

> **Jangan gunakan token LLM untuk pekerjaan yang dapat dilakukan secara deterministik oleh SQL atau Pandas.**

SQL melakukan **data retrieval dan reduction**.

Pandas melakukan **data processing dan analysis**.

LLM melakukan **reasoning, interpretation, dan natural-language generation**.

Dengan pembagian tersebut, Anna dapat memproses dataset yang jauh lebih besar tanpa harus memasukkan seluruh dataset ke context Hermes. Ini berpotensi menurunkan **dynamic input tokens, tool-result tokens, reasoning workload, latency, dan biaya inference**.

Namun, **static prompt Anna yang besar tetap merupakan masalah terpisah**. Untuk efisiensi maksimum, optimasi Pandas harus berjalan bersamaan dengan modularisasi prompt, pengurangan tool-description yang tidak diperlukan, dan strategi context/caching.
