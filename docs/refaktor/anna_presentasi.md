Yang Aku inginkan sebenarnya bukan lagi ANNA sebagai chatbot, tetapi ANNA sebagai Business Intelligence Presenter untuk meeting evaluasi.

Perbedaannya penting:

Ketika operator mengatakan "Laporkan kondisi bisnis KPH Banyuwangi Barat periode ini", ANNA harus menjalankan sebuah business presentation flow secara lengkap, bukan menunggu pertanyaan satu per satu.

ANNA harus mampu mengorkestrasi narasi + KPI + chart + map + layer + filter + drill-down sebagai satu presentasi.

1. Konsep utama: ANNA memiliki "Presentation Mode"

Saya sarankan menambahkan konsep:

ANNA
│
├── CHAT MODE
│   └── menjawab pertanyaan
│
└── PRESENTATION MODE
    └── menyusun laporan bisnis lengkap

Ketika operator mengatakan:

"Laporkan kondisi bisnis KPH Banyuwangi Barat periode saat ini."

ANNA masuk ke:

BUSINESS REVIEW SESSION

Kemudian ANNA menentukan sendiri urutan presentasinya.

Scope
 ↓
Executive Summary
 ↓
Petak
 ↓
Aktivitas
 ↓
Produksi
 ↓
Matriks / hubungan indikator
 ↓
Area perhatian
 ↓
Kesimpulan

Map dan Chart menjadi media presentasi ANNA, bukan sekadar komponen visual.

2. Contoh pengalaman meeting

Misalnya operator mengatakan:

"ANNA, laporkan kondisi bisnis KPH Banyuwangi Barat periode saat ini."

ANNA tidak menjawab:

"Baik. Produksi saat ini..."

lalu berhenti.

ANNA melakukan:

1. Set filter KPH
2. Set periode
3. Load business context
4. Present KPI
5. Present kondisi petak
6. Animate/filter map
7. Present aktivitas
8. Change map → activity points
9. Present produksi
10. Change map → production layer
11. Present findings
12. Present attention areas
13. Closing summary

Operator cukup mendengarkan dan melihat dashboard.

3. Bagian pertama: Executive Briefing

ANNA mulai dengan scope:

"Saya akan menyampaikan evaluasi kondisi bisnis KPH Banyuwangi Barat untuk periode P1 September 2026."

Kemudian KPI utama:

┌──────────────────────────────────────────────┐
│ BUSINESS REVIEW                              │
│ KPH BANYUWANGI BARAT                         │
│ P1 • SEPTEMBER 2026                          │
│                                              │
│ PETAK       12.480                           │
│ AKTIV       9.821                            │
│ IDLE        1.925                            │
│ BONGKOR       734                            │
│                                              │
│ PRODUKSI    82,45 TON                        │
│ TARGET      95,00 TON                        │
│ ACHIEVEMENT 86,79%                           │
└──────────────────────────────────────────────┘

ANNA membacakan:

"Pada periode P1 September, terdapat 12.480 petak dalam scope evaluasi. Sebanyak 9.821 petak berstatus aktif, 1.925 idle, dan 734 bongkor."

Ini adalah executive snapshot.

4. Kemudian ANNA masuk ke Evaluasi Petak

ANNA mengatakan:

"Kita mulai dari kondisi petak."

Kemudian ANNA mengontrol map:

MAP ACTION

showLayer("petak")
filter("status", "aktif")
fitBounds()

Map menampilkan polygon aktif.

ANNA:

"Petak aktif mencakup 9.821 petak dari total 12.480 petak."

Kemudian:

hideLayer("aktif")
showLayer("idle")
fitBounds()

ANNA:

"Petak idle berjumlah 1.925."

Kemudian:

hideLayer("idle")
showLayer("bongkor")
fitBounds()

ANNA:

"Petak bongkor berjumlah 734 dengan luas total 481,2 hektare."

Jadi ANNA tidak hanya mengatakan "734 bongkor".

Operator melihat 734 polygon bongkor muncul di map.

5. Chart ikut bergerak

Saat ANNA sedang membahas petak:

MAP                    CHART
────                   ─────
Bongkor polygons       Petak Status
                       █████ Active
                       ███ Idle
                       ██ Bongkor

Kemudian ANNA dapat mengatakan:

"Secara komposisi, petak aktif merupakan kelompok terbesar. Petak idle dan bongkor menjadi kelompok yang perlu diperhatikan dalam evaluasi periode ini."

Chart dan map menggunakan scope data yang sama.

6. Masuk ke aktivitas

ANNA:

"Selanjutnya saya melihat realisasi aktivitas penyadapan."

Map berubah dari polygon status menjadi:

ACTIVITY MODE

● aktivitas
● aktivitas
● aktivitas
● aktivitas

Pin point aktivitas ditampilkan.

Kemudian Chart:

RENCANA       100%
REALISASI      87%
GAP            13%

ANNA:

"Realisasi aktivitas pada periode ini mencapai 87% dari rencana."

Kemudian ANNA dapat melakukan spatial analysis.

Misalnya business engine memberikan:

petak:
- activity_achievement < threshold

Map menampilkan petak tersebut.

ANNA:

"Terdapat sejumlah petak dengan realisasi aktivitas di bawah ambang evaluasi yang digunakan sistem. Saya tampilkan lokasinya pada peta."

Perhatikan kalimatnya.

ANNA tidak mengatakan "petak tersebut tidak efektif" tanpa definisi.

Jika Business Engine memang mendefinisikan:

effective_activity = activity_realization >= 90%

maka ANNA boleh mengatakan:

"Berdasarkan definisi efektivitas aktivitas yang digunakan sistem, terdapat 326 petak yang belum memenuhi ambang efektivitas."

Ini jauh lebih aman.

7. Kemudian masuk ke produksi

ANNA:

"Berikutnya saya tampilkan kondisi produksi."

Map berganti:

PRODUCTION LAYER

petak produksi
████
██████
██
████████

Chart berubah menjadi:

        PRODUKSI

Target    ████████████████████ 95 T
Aktual    █████████████████    82 T

ANNA:

"Produksi aktual mencapai 82,45 ton dari target 95 ton atau 86,79%, sehingga terdapat gap 12,55 ton."

Kemudian ANNA dapat melakukan spatial drilldown:

PRODUCTION PERFORMANCE

HIGH
MEDIUM
LOW

Map:

████ high
████ medium
██ low

ANNA:

"Saya tampilkan pada peta kelompok petak yang berada di bawah target atau ambang produktivitas yang digunakan dalam evaluasi."

8. Kemudian ANNA menghubungkan bisnis

Ini bagian yang menurut saya paling penting.

ANNA jangan berhenti di:

Petak:
734 bongkor

Aktivitas:
87%

Produksi:
86,79%

Tetapi masuk ke:

Business Relationship

Misalnya tersedia data:

Bongkor
↓
734 petak

Tanpa penyadap
↓
421 petak

Aktivitas rendah
↓
326 petak

Produksi rendah
↓
218 petak

ANNA bisa mengatakan:

"Dari 734 petak bongkor, 421 tidak memiliki penyadap. Pada kelompok yang sama terdapat 326 petak yang berada di bawah ambang aktivitas dan 218 petak yang berada di bawah ambang produktivitas."

Kemudian Map menampilkan intersection.

BONGKOR
   +
AKTIVITAS RENDAH
   +
PRODUKSI RENDAH

Itu sudah menjadi analisis bisnis spasial, bukan sekadar dashboard.

9. ANNA bisa melakukan "guided map storytelling"

Ini konsep yang sangat cocok untuk aplikasi Anda.

ANNA memiliki timeline presentasi:

STEP 01
PETAK OVERVIEW
      ↓
STEP 02
BONGKOR
      ↓
STEP 03
IDLE
      ↓
STEP 04
AKTIVITAS
      ↓
STEP 05
AKTIVITAS RENDAH
      ↓
STEP 06
PRODUKSI
      ↓
STEP 07
PRODUKSI RENDAH
      ↓
STEP 08
CROSS ANALYSIS
      ↓
STEP 09
EXECUTIVE SUMMARY

Operator melihat dashboard berubah secara bertahap mengikuti narasi ANNA.

10. Jangan membuat ANNA terlalu cepat

Untuk meeting, ANNA sebaiknya memiliki presentation pacing.

Misalnya:

ANNA
│
├── Section: Executive Summary
│
├── Section: Evaluasi Petak
│
├── Section: Evaluasi Aktivitas
│
├── Section: Evaluasi Produksi
│
├── Section: Cross Analysis
│
└── Section: Conclusion

Setiap section punya:

{
  "title": "Evaluasi Petak",
  "narrative": "...",
  "mapAction": "...",
  "chartAction": "...",
  "metrics": [...],
  "evidence": [...]
}

Sehingga ANNA sebenarnya menjalankan presentation plan.

11. Ini memungkinkan operator menyela ANNA

Ini sangat penting dalam meeting.

ANNA sedang mengatakan:

"Terdapat 734 petak bongkor..."

Operator:

"Tampilkan yang di BKPH X."

ANNA tidak perlu menghentikan seluruh sistem.

ANNA mengubah scope:

KPH
 ↓
BKPH X
 ↓
recalculate / use available context
 ↓
update Map
 ↓
update Chart

Kemudian:

"Pada BKPH tersebut terdapat 87 petak bongkor dengan luas 64,3 hektare."

Lalu operator:

"Yang tidak punya penyadap saja."

ANNA:

BONGKOR
+
TANPA PENYADAP

Map langsung berubah.

Ini membuat meeting terasa seperti berinteraksi dengan analis, bukan membaca dashboard.

12. ANNA harus mempunyai "Presentation State"

Saya menyarankan struktur:

PresentationSession
│
├── scope
│   ├── bulan
│   ├── tahun
│   ├── periode
│   ├── divre
│   ├── kph
│   ├── bkph
│   ├── rph
│   └── tpg
│
├── sections
│
├── currentSection
│
├── mapState
│
├── chartState
│
├── metrics
│
├── findings
│
└── evidence

ANNA tidak perlu mengingat semuanya dari percakapan.

Dashboard menyediakan Presentation Context.

13. Ada satu hal yang sangat penting: "Report Scope"

Ketika operator berkata:

"Laporkan kondisi bisnis saat ini."

ANNA harus tahu:

CURRENT DATE
CURRENT PERIOD
CURRENT FILTER
CURRENT KPH
CURRENT BKPH

Kalau scope belum jelas, ANNA harus menggunakan scope dashboard yang aktif.

Misalnya:

Current Context

Tahun    : 2026
Bulan    : September
Periode  : P1
KPH      : Banyuwangi Barat
BKPH     : Semua
RPH      : Semua
TPG      : Semua

ANNA harus menyatakan scope tersebut di awal:

"Saya akan melaporkan kondisi KPH Banyuwangi Barat untuk P1 September 2026 berdasarkan filter yang sedang aktif."

Ini mencegah scope contamination.

14. ANNA harus memiliki "Evidence Ledger"

Ini akan membuat sistem Anda sangat kuat.

Setiap pernyataan yang diucapkan ANNA punya evidence:

STATEMENT
"734 petak berstatus bongkor"

SOURCE
petak.status = BONGKOR

SCOPE
KPH = Banyuwangi Barat
Periode = P1
Tahun = 2026

VALUE
734

UNIT
petak

MAP STATE
bongkor

CHART STATE
petak_status

Kemudian:

STATEMENT
"Gap produksi 12,55 ton"

SOURCE
actual + target

CALCULATION
95 - 82.45

VALUE
12.55 ton

Kalau operator bertanya:

"Dari mana angka itu?"

ANNA dapat menjawab:

"Angka tersebut berasal dari 82,45 ton produksi aktual dibandingkan target 95 ton pada scope evaluasi yang sedang aktif."

Tidak ada angka misterius.

15. Laporan penuh bisa memiliki format seperti ini

ANNA dapat menghasilkan:

BUSINESS REVIEW

Scope

KPH Banyuwangi Barat — P1 September 2026

01 — Executive Summary

Terdapat 12.480 petak dalam scope evaluasi. Sebanyak 9.821 aktif, 1.925 idle, dan 734 bongkor.

Map: tampilkan semua petak.

02 — Kondisi Petak

Petak bongkor mencakup 734 petak dengan luas 481,2 ha.

Map: bongkor.

Chart: komposisi status petak.

03 — Aktivitas

Realisasi aktivitas mencapai 87% dari rencana.

Map: activity points.

Chart: planned vs actual.

04 — Area yang Perlu Diperhatikan

Terdapat 326 petak yang belum memenuhi ambang efektivitas aktivitas berdasarkan definisi evaluasi yang digunakan.

Map: highlight 326 petak.

Chart: distribution by BKPH.

05 — Produksi

Produksi mencapai 82,45 ton atau 86,79% dari target 95 ton.

Map: production performance.

Chart: actual vs target.

06 — Cross Analysis

Dari 734 petak bongkor, 421 tidak memiliki penyadap. Sebanyak 218 petak juga berada pada kelompok produktivitas rendah.

Map: intersection.

07 — Closing

"Secara keseluruhan, kondisi periode ini menunjukkan produksi telah mencapai 86,79% target. Evaluasi lebih lanjut perlu difokuskan pada kelompok petak yang memiliki kombinasi kondisi bongkor, keterbatasan penyadap, dan aktivitas di bawah ambang evaluasi."

Jika data tidak cukup untuk menyatakan sesuatu, ANNA harus mengatakan:

"Data yang tersedia belum cukup untuk menentukan penyebab kondisi tersebut."

16. Ini yang membedakan ANNA dari chatbot

Chatbot:

User:
Bagaimana produksi?

ANNA:
Produksi 82 ton, target 95 ton.

ANNA versi yang Anda inginkan:

USER
"Laporkan kondisi bisnis."

             ↓

ANNA PRESENTATION ENGINE

             ↓

┌──────────────────────────┐
│ EXECUTIVE SUMMARY        │
└────────────┬─────────────┘
             ↓
        MAP + KPI
             ↓
┌──────────────────────────┐
│ EVALUASI PETAK           │
└────────────┬─────────────┘
             ↓
       MAP POLYGONS
       + STATUS CHART
             ↓
┌──────────────────────────┐
│ EVALUASI AKTIVITAS       │
└────────────┬─────────────┘
             ↓
       MAP POINTS
       + ACTIVITY CHART
             ↓
┌──────────────────────────┐
│ EVALUASI PRODUKSI        │
└────────────┬─────────────┘
             ↓
       MAP POLYGONS
       + TARGET CHART
             ↓
┌──────────────────────────┐
│ CROSS ANALYSIS           │
└────────────┬─────────────┘
             ↓
       MAP INTERSECTION
       + MATRIX CHART
             ↓
┌──────────────────────────┐
│ EXECUTIVE CONCLUSION     │
└──────────────────────────┘

Inilah arsitektur yang menurut saya paling cocok untuk ANNA.

Dan yang penting: Business Data Engine tetap menjadi satu-satunya sumber kebenaran. ANNA tidak boleh "berpikir lalu mengarang angka"; ANNA menerima dataset/KPI/evidence yang sudah diverifikasi, kemudian mengorkestrasi visualisasi dan menerjemahkannya menjadi narasi meeting yang natural.

Kalau ini diterapkan, operator cukup mengatakan "ANNA, mulai evaluasi KPH Banyuwangi Barat periode ini", lalu ANNA dapat menjalankan presentasi bisnis dari awal sampai akhir sambil menggerakkan Map dan Chart sesuai bagian yang sedang dibahas.