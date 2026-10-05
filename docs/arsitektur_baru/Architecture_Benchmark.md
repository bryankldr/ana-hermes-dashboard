# Architecture Benchmark

## Evaluasi `ana-hermes-dashboard` terhadap konsep StarMynd / Infinite Brain

> **Purpose:** Dokumen ini menjadi konteks evaluasi untuk profil `ana` sebagai development agent.
> `ana` bertugas menganalisis, mengembangkan, menguji, dan memperbaiki sistem.
> `anna` adalah agent runtime yang digunakan oleh pengguna melalui `ana-hermes-dashboard`.

---

# 1. Identitas dan Pembagian Peran

## Ana — Development Agent

`ana` adalah agent yang digunakan untuk:

* memahami arsitektur `ana-hermes-dashboard`
* membaca dan menganalisis source code
* mengevaluasi desain sistem
* mengembangkan fitur
* memperbaiki bug
* membuat atau memperbaiki skill
* mengevaluasi pipeline agent
* mengevaluasi knowledge architecture
* mengevaluasi integrasi dashboard
* menguji kualitas reasoning dan business intelligence
* membandingkan arsitektur dengan pendekatan eksternal
* melakukan refactoring apabila diperlukan

`ana` **bukan agent bisnis yang digunakan oleh end-user pada dashboard**.

Dalam konteks ini, `ana` adalah development/engineering authority.

---

## Anna — Runtime Agent

`anna` adalah agent yang berjalan di dalam:

`ana-hermes-dashboard`

Anna digunakan oleh pengguna untuk:

* percakapan bisnis
* analisis SIMOGE
* interpretasi KPI
* membaca konteks dashboard
* memahami peta
* memahami chart
* memberikan insight
* membantu evaluasi operasional
* memberikan briefing
* menjawab pertanyaan berdasarkan knowledge dan data yang diberikan dashboard
* berinteraksi dengan pengguna melalui interface dashboard, termasuk voice apabila tersedia

Anna bukan development agent.

Anna tidak seharusnya melakukan perubahan arsitektur sistem secara mandiri.

---

# 2. Prinsip Utama

Arsitektur `ana-hermes-dashboard` harus mempertahankan prinsip:

> **Dashboard owns data. Anna owns interpretation.**

Artinya:

* Business Data Engine bertanggung jawab atas data.
* Dashboard bertanggung jawab atas query dan kalkulasi bisnis.
* Business rules harus berasal dari sumber yang eksplisit.
* Anna bertanggung jawab atas interpretasi, reasoning, explanation, dan interaction.
* Anna tidak boleh mengarang data.
* Anna tidak boleh mengubah hasil query.
* Anna tidak boleh menggantikan Business Data Engine sebagai sumber data.

Secara konseptual:

```text
                 USER
                  │
                  ▼
                ANNA
                  │
        ┌─────────┼─────────┐
        │         │         │
        ▼         ▼         ▼
    Knowledge   Dashboard  Actions
        │         │
        │         ▼
        │   Business Data
        │      Engine
        │         │
        │         ▼
        │       SIMOGE
        │
        ▼
    Knowledge Base
```

---

# 3. StarMynd / Infinite Brain sebagai Benchmark

StarMynd / Infinite Brain jangan dianggap sebagai sistem yang harus disalin.

Gunakan konsepnya sebagai **architectural benchmark**.

Konsep penting yang perlu dievaluasi:

```text
Knowledge
Rules
Definitions
Decisions
Skills
Agents
Workflows
Runtime
Audit
Governance
Business Data
```

Pendekatan tersebut memperlakukan knowledge sebagai sesuatu yang:

* dapat dibaca agent
* dapat ditelusuri
* memiliki struktur
* memiliki provenance
* memiliki lifecycle
* dapat diperbarui
* tidak harus bercampur dengan live transactional data

Hal ini relevan dengan arsitektur Anna.

---

# 4. Knowledge ≠ Live Data

Salah satu prinsip yang harus dipertahankan:

```text
KNOWLEDGE
    ≠
LIVE BUSINESS DATA
```

Knowledge dapat berisi:

* definisi KPI
* definisi istilah
* business rules
* SOP
* struktur organisasi
* ontology
* hubungan antar-entitas
* definisi status
* cara membaca metric
* cara melakukan analisis
* historical decisions
* dokumentasi sistem
* penjelasan domain

Sedangkan data operasional tetap berasal dari Business Data Engine.

Contoh:

```text
Knowledge:

"Produksi getah adalah total berat produksi
berdasarkan periode yang dipilih."

Live Data:

produksi = 182.391 kg
periode = September 2026
```

Knowledge menjelaskan **apa arti angka tersebut**.

Business Data Engine memberikan **angka aktual**.

Anna menggabungkan keduanya untuk menghasilkan interpretasi.

---

# 5. Jangan Mengubah Obsidian Menjadi Database Transaksi

Knowledge repository dapat menggunakan struktur file/Markdown/YAML dan dapat diakses melalui Obsidian.

Namun jangan menjadikan Obsidian sebagai tempat penyimpanan:

* seluruh record SIMOGE
* live transaction
* data produksi harian
* koordinat seluruh aktivitas
* hasil query yang terus berubah
* angka KPI yang harus realtime

Model yang lebih baik:

```text
Obsidian / Knowledge
        │
        ├── KPI definition
        ├── ontology
        ├── business rules
        ├── SOP
        ├── system knowledge
        ├── domain knowledge
        └── historical decisions
                    │
                    ▼
                  ANNA
                    │
                    ▼
          Business Data Engine
                    │
                    ▼
                 SIMOGE
```

---

# 6. Knowledge harus Memiliki Lifecycle

Knowledge tidak boleh diperlakukan sebagai dokumen statis selamanya.

Pertimbangkan lifecycle:

```text
DRAFT
  │
  ▼
REVIEW
  │
  ▼
APPROVED
  │
  ▼
CANONICAL
  │
  ▼
SUPERSEDED
  │
  ▼
ARCHIVED
```

Contoh:

```text
kpi-produksi-2025.md
        │
        └── superseded by
                    │
                    ▼
kpi-produksi-2026.md
```

Tujuannya adalah mencegah Anna menggunakan aturan lama sebagai aturan aktif.

Jika terdapat dua knowledge yang bertentangan, Anna harus dapat membedakan:

* current
* historical
* deprecated
* superseded
* unknown

Jangan menyelesaikan konflik dengan menebak.

---

# 7. Provenance adalah Persyaratan Penting

Setiap knowledge penting sebaiknya memiliki provenance.

Contoh:

```yaml
title: Produksi Getah
status: canonical
effective_from: 2026-01-01
source: SIMOGE Business Rules
owner: production
```

Untuk data:

```yaml
source: Business Data Engine
refresh: live
```

Untuk hasil analisis:

```yaml
source:
  - dashboard_context
  - production_kpi
  - business_rule_production
```

Anna harus mampu membedakan:

```text
FACT
ANALYSIS
ASSUMPTION
HYPOTHESIS
```

Jangan mencampurkan keempatnya.

---

# 8. Business Data Engine adalah Quantitative Authority

Business Data Engine harus tetap menjadi authority untuk:

* query
* joins
* aggregation
* filtering
* date logic
* KPI calculation
* spatial aggregation
* production calculation
* comparative analysis
* trend calculation
* business-specific transformations

Anna hanya menerima hasil yang telah disiapkan.

Contoh:

```text
User:
"Kenapa produksi turun?"

Anna
  ↓
Dashboard Context
  ↓
Business Data Engine
  ↓
production_current
production_previous
delta
contributors
segments
  ↓
Anna
  ↓
Business explanation
```

Bukan:

```text
User
 ↓
Anna
 ↓
langsung query database
```

---

# 9. Evaluasi terhadap Infinite Entry

Konsep decomposition seperti Infinite Entry dapat digunakan sebagai benchmark untuk kemampuan BI Anna.

Jika:

```text
Produksi:
Periode sebelumnya = 100 ton
Periode sekarang   = 115 ton

Δ = +15 ton
```

Anna idealnya dapat menjelaskan contributor:

```text
+15 ton
│
├── +9 ton  peningkatan volume penyadapan
├── +4 ton  peningkatan produktivitas
├── +3 ton  perubahan komposisi petak
└── -1 ton  penurunan kontribusi area tertentu
────────────
+15 ton
```

Jumlah contributor harus konsisten dengan perubahan metric.

Jangan menghasilkan:

```text
+9
+4
+3
-1
= +15
```

lalu memberikan kesimpulan lain seperti:

```text
"Faktor utama +20 ton."
```

Jika attribution belum tersedia dari Business Data Engine, Anna harus menyatakan bahwa attribution belum tersedia.

---

# 10. Anna bukan RAG Chatbot Sederhana

Evaluasi Anna jangan hanya menggunakan:

> "Apakah Anna bisa menemukan dokumen?"

Pertanyaan yang lebih penting:

```text
Apakah Anna memahami ontology?

Apakah Anna memahami business rules?

Apakah Anna dapat membedakan current vs historical knowledge?

Apakah Anna mengetahui sumber data?

Apakah Anna memahami konteks dashboard?

Apakah Anna dapat membedakan fact dan inference?

Apakah Anna dapat menjelaskan metric?

Apakah Anna dapat mengidentifikasi missing data?

Apakah Anna menolak membuat kesimpulan ketika evidence tidak cukup?
```

Knowledge retrieval hanyalah salah satu komponen.

---

# 11. Runtime Architecture

Evaluasi pipeline Anna sebagai:

```text
USER
 │
 ▼
Dashboard UI
 │
 ▼
Anna
 │
 ├── Knowledge Context
 │
 ├── Dashboard Context
 │
 ├── Map Context
 │
 ├── Chart Context
 │
 ├── Conversation Context
 │
 └── Available Actions
 │
 ▼
Reasoning
 │
 ▼
Response
```

Anna harus memahami apa yang sedang dilihat pengguna.

Misalnya pengguna sedang melihat:

```text
SPATIAL MAP

Filter:
Tahun = 2026
DIVRE = Jatim
KPH = Banyuwangi Barat
BKPH = ...
Periode = P2
```

Kemudian pengguna bertanya:

> "Kenapa area ini banyak bongkor?"

Anna harus menggunakan konteks map/dashboard yang aktif.

---

# 12. Map Context adalah bagian dari Knowledge Runtime

Untuk Anna, peta bukan sekadar visual.

Map dapat menyediakan context:

```text
selected_polygon
selected_petak
selected_region
visible_extent
active_filters
active_year
active_period
selected_entity
```

Sehingga:

```text
User menunjuk area
       │
       ▼
Dashboard
       │
       ├── geometry
       ├── kode_petak
       ├── status
       ├── penyadap
       └── KPI
       │
       ▼
Anna
       │
       ▼
Explanation
```

Anna tidak perlu menebak lokasi yang dimaksud pengguna.

---

# 13. Evaluasi Ontology

Anna harus memahami hubungan domain, bukan sekadar nama tabel.

Contoh ontology SIMOGE:

```text
Penyadap
   │
   └── Andil
          │
          └── Petak
                 │
                 └── Polygon

Rencana Aktivitas
   │
   └── Aktivitas Sadap

Aktivitas Penerimaan
   │
   └── Drum
          │
          └── Pengangkutan
                 │
                 └── Perni
```

Jika Anna ditanya:

> "Berapa produksi penyadap pada petak tertentu?"

Anna harus memahami jalur relasi bisnis yang benar.

Bukan sekadar mencari kata "penyadap" dan "petak".

---

# 14. Evaluasi Governance

Gunakan prinsip:

```text
Agent may propose.
Agent should not silently canonize.
```

Jika Anna menghasilkan knowledge baru:

```text
Anna
  ↓
Proposed Knowledge
  ↓
Review
  ↓
Approval
  ↓
Canonical Knowledge
```

Jangan:

```text
Anna
  ↓
langsung menulis aturan baru
  ↓
aturan dianggap benar
```

Ini penting terutama untuk:

* KPI
* business rules
* SOP
* ontology
* definisi status
* kebijakan periode
* definisi metric

---

# 15. Evaluasi Auditability

Setiap tindakan penting Anna sebaiknya dapat ditelusuri.

Contoh:

```text
Question
   ↓
Context
   ↓
Knowledge used
   ↓
Business data used
   ↓
Calculation
   ↓
Interpretation
   ↓
Answer
```

Tujuan akhirnya:

> Pengguna atau developer dapat memahami mengapa Anna memberikan jawaban tertentu.

Bukan berarti seluruh proses internal harus ditampilkan kepada user.

Yang dibutuhkan adalah **traceability**.

---

# 16. Evaluasi Anna terhadap StarMynd

Gunakan tabel konseptual berikut sebagai benchmark:

| Capability                    | Benchmark |
| ----------------------------- | --------- |
| Structured knowledge          | Ada       |
| Markdown/YAML knowledge       | Ada       |
| Ontology                      | Ada       |
| Business rules                | Ada       |
| Provenance                    | Ada       |
| Knowledge lifecycle           | Ada       |
| Supersession                  | Ada       |
| Live business data separation | Ada       |
| Business Data Engine          | Ada       |
| Agent runtime                 | Ada       |
| Skills                        | Ada       |
| Workflow                      | Ada       |
| Auditability                  | Ada       |
| Approval/governance           | Ada       |
| Context-aware dashboard       | Ada       |
| Spatial context               | Ada       |
| KPI reasoning                 | Ada       |
| Metric decomposition          | Ada       |
| Fact vs inference             | Ada       |
| Missing-data awareness        | Ada       |

Status setiap capability harus dinilai:

```text
IMPLEMENTED
PARTIAL
MISSING
UNNECESSARY
PLANNED
```

Jangan menganggap semua capability StarMynd harus diimplementasikan.

---

# 17. Prinsip Evaluasi Utama

Saat mengevaluasi `ana-hermes-dashboard`, selalu tanyakan:

### A. Architecture

Apakah komponen memiliki responsibility yang jelas?

### B. Knowledge

Apakah Anna memiliki knowledge yang terstruktur dan dapat dipercaya?

### C. Data

Apakah live data tetap berada di Business Data Engine?

### D. Reasoning

Apakah Anna hanya membuat kesimpulan berdasarkan evidence?

### E. Context

Apakah Anna memahami dashboard, chart, map, filter, dan selected entity?

### F. Governance

Apakah perubahan knowledge dapat dikontrol?

### G. Provenance

Apakah sumber informasi dapat ditelusuri?

### H. Lifecycle

Apakah knowledge lama dapat ditandai sebagai obsolete/superseded?

### I. Auditability

Apakah keputusan dan jawaban penting dapat ditelusuri kembali?

### J. Extensibility

Apakah sistem dapat berkembang tanpa membuat Anna menjadi monolithic agent?

---

# 18. Jangan Meniru StarMynd Secara Blind

StarMynd adalah benchmark, bukan specification.

Jika sebuah fitur StarMynd tidak memberikan keuntungan nyata bagi Anna, jangan menambahkannya hanya karena StarMynd memilikinya.

Prioritas harus:

```text
SIMOGE requirement
        ↓
Anna requirement
        ↓
Dashboard architecture
        ↓
Engineering simplicity
        ↓
External benchmark
```

bukan:

```text
StarMynd
   ↓
copy architecture
   ↓
force into Anna
```

---

# 19. Tugas Ana sebagai Development Agent

Ketika melakukan evaluasi terhadap `ana-hermes-dashboard`, `ana` harus:

1. Memetakan arsitektur yang benar-benar sudah ada.
2. Tidak mengasumsikan fitur yang belum diverifikasi.
3. Mengidentifikasi boundary antara Anna, dashboard, knowledge, dan data engine.
4. Membandingkan architecture tersebut dengan benchmark Infinite Brain.
5. Mengidentifikasi gap.
6. Mengelompokkan gap menjadi:

   * critical
   * important
   * useful
   * unnecessary
7. Memberikan rekomendasi berdasarkan kebutuhan sistem.
8. Menghindari perubahan destruktif.
9. Mempertahankan behavior yang sudah bekerja.
10. Memprioritaskan perubahan kecil, terukur, dan dapat diverifikasi.

---

# 20. Output Evaluasi yang Diharapkan

Jika `ana` diminta mengevaluasi sistem, gunakan struktur:

```text
# Architecture Evaluation

## Current Architecture
...

## What Already Works
...

## StarMynd Benchmark
...

## Gap Analysis
...

## Critical Gaps
...

## Recommended Improvements
...

## Risks
...

## Implementation Priority
...

## Verification Plan
...
```

Jangan langsung melakukan implementasi hanya karena menemukan gap.

Pertama:

```text
Observe
  ↓
Understand
  ↓
Compare
  ↓
Evaluate
  ↓
Prioritize
  ↓
Propose
  ↓
Implement
  ↓
Verify
```

---

# 21. Prinsip Akhir

Arsitektur yang ingin dicapai bukan:

```text
LLM + RAG + Dashboard
```

tetapi:

```text
                ANNA
                 │
       ┌─────────┼─────────┐
       │         │         │
       ▼         ▼         ▼
   Knowledge   Context   Actions
       │         │
       ▼         ▼
    Obsidian   Dashboard
                 │
                 ▼
          Business Data
             Engine
                 │
                 ▼
               SIMOGE
```

Dengan governance:

```text
Knowledge
    │
    ├── provenance
    ├── lifecycle
    ├── version
    ├── approval
    └── supersession
```

dan dengan prinsip:

> **Data is authoritative at the data layer.
> Knowledge is authoritative at the knowledge layer.
> Anna owns interpretation, not ownership of the underlying data.
> Ana owns development and evaluation of the system.**

---

# 22. Core Evaluation Statement

Gunakan statement berikut sebagai dasar ketika mengevaluasi sistem:

> **Anna should behave as a context-aware business intelligence agent operating on top of a governed knowledge layer and an authoritative business data layer.**

> **Ana should behave as the development and architecture agent responsible for inspecting, evaluating, improving, testing, and maintaining that system.**

> **StarMynd / Infinite Brain is an architectural reference for knowledge organization, agent runtime, governance, provenance, lifecycle, and business-data separation — not a specification that must be copied.**

> **The objective is not to make Anna more complicated. The objective is to make Anna more reliable, explainable, context-aware, auditable, and useful without violating the responsibility boundaries of the dashboard and Business Data Engine.**
