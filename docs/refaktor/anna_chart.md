Konsep yang saya sarankan
                    ANNA
                     │
              memahami intent
                     │
                     ▼
            Visualization Engine
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
       KPI          MAP          CHART
        │            │            │
        └────────────┼────────────┘
                     ▼
             Business Narrative
1. KPI utama → gunakan Metric / KPI Card

Untuk pertanyaan seperti:

"Bagaimana produksi saat ini?"

Jangan langsung memakai bar chart.

Gunakan:

┌─────────────────────────────────┐
│ PRODUKSI                         │
│                                 │
│ 82,45 TON                       │
│                                 │
│ Target     95,00 TON            │
│ Achievement 86,79%              │
│ Gap        -12,55 TON            │
└─────────────────────────────────┘

Ini paling cepat dipahami operator.

2. Aktual vs Target → Bullet Chart

Untuk produksi getah, bullet chart sangat cocok.

PRODUKSI

0       25       50       75       95 TON
|--------|--------|--------|--------|
                         ███████████
                         ▲
                       82,45

Target ──────────────────────────────●

Lebih intuitif daripada dua batang yang berdampingan.

Bisa digunakan untuk:

produksi vs target
aktivitas vs target
penyadap aktif vs target
luas aktif vs target
3. Trend produksi → Line Chart

Untuk:

"Bagaimana perkembangan produksi?"

gunakan:

Produksi
  │
95│                         ● Target
  │                    ●
85│              ●─────
  │          ●
75│      ●
  │  ●
  └────────────────────────────
    Jan Feb Mar Apr Mei Jun

Jika ada target:

garis aktual
garis target

Jika ada P1/P2:

dapat menggunakan segmentasi periode.

Jangan gunakan pie chart untuk trend.

4. Struktur status petak → Stacked Bar

Untuk:

"Bagaimana komposisi kondisi petak?"

Lebih baik:

PETAK

████████████████████████████████
Aktif       ███████████████
Idle        █████
Bongkor     ████
Tanpa       ███

Atau horizontal stacked bar.

Ini sangat cocok untuk:

Aktif
Idle
Bongkor
Tanpa penyadap
Multi penyadap

Operator langsung melihat proporsinya.

5. Distribusi antar wilayah → Horizontal Bar

Misalnya:

"KPH mana yang produksinya paling besar?"

Gunakan:

Produksi per KPH

KPH A  █████████████████  82,4 t
KPH B  ██████████████     68,1 t
KPH C  ███████████        54,7 t
KPH D  ███████             31,2 t

Lebih mudah dibanding pie/donut ketika kategorinya banyak.

ANNA kemudian bisa mengontrol Map:

Chart → pilih KPH
        ↓
Map → focus KPH

Ini akan sangat bagus untuk dashboard Anda.

6. Target → Aktual → Gap → Waterfall

Ini salah satu chart yang menurut saya sangat berguna untuk BI produksi.

Misalnya:

TARGET
95,0 t
   │
   ▼
████████████████████████
           -12,55
                    ▼
              AKTUAL
               82,45 t

Kalau nanti Anda memiliki komponen gap berdasarkan faktor yang terukur, waterfall bisa menunjukkan kontribusinya.

Tetapi jangan menggunakan waterfall untuk mengarang "penyebab gap".

7. Petak bermasalah → Pareto

Untuk pertanyaan:

"Masalah apa yang paling banyak terjadi?"

Bisa menggunakan Pareto:

Jumlah
petak
│
│ █████████
│ ████████
│ ██████
│ ████
│ ██
└────────────────────
  Bongkor
  Tanpa penyadap
  Idle
  Multi penyadap

Dengan cumulative percentage.

Ini bagus untuk membantu operator melihat kategori dominan, tanpa ANNA harus memberikan klaim sebab-akibat.

8. Hubungan dua variabel → Scatter Plot

Untuk Evaluasi Matriks, ini jauh lebih berguna daripada bar chart.

Contoh:

Produksi
│                    ●
│             ●
│        ●       ●
│     ●
│  ●
│ ●
└────────────────────────
       Aktivitas

Misalnya:

X = realisasi aktivitas
Y = produksi
size = luas petak

Ini memungkinkan ANNA mengatakan:

"Pada dataset ini terlihat kecenderungan produksi yang lebih tinggi pada kelompok dengan realisasi aktivitas yang lebih tinggi."

Bukan:

"Aktivitas menyebabkan produksi meningkat."

9. Heatmap → sangat cocok untuk evaluasi wilayah

Misalnya:

             P1    P2    P3
KPH A        ██    ███   ████
KPH B        ███   ██    ███
KPH C        █     ██    ████
KPH D        ██    █     ██

Bisa digunakan untuk:

achievement produksi
produktivitas
aktivitas
status petak
performance per wilayah

Ini sangat cepat untuk menemukan pola.

10. Tetapi yang paling menarik: ANNA memilih chart otomatis

Saya justru menyarankan jangan membuat operator memilih jenis chart secara manual.

Operator:

"Bandingkan produksi dengan target."

ANNA:

Intent: comparison
Metric: production
Baseline: target

→ Bullet Chart

Operator:

"Bagaimana trend produksinya?"

ANNA:

Intent: trend
Metric: production
Dimension: time

→ Line Chart

Operator:

"Kondisi petaknya bagaimana?"

ANNA:

Intent: composition
Metric: petak
Dimension: status

→ Stacked Bar

Operator:

"KPH mana yang produksinya paling tinggi?"

ANNA:

Intent: ranking
Metric: production
Dimension: KPH

→ Horizontal Bar
+
Map focus

Operator:

"Apakah aktivitas berhubungan dengan produksi?"

ANNA:

Intent: relationship
X: activity
Y: production

→ Scatter Plot
+
analytical narrative
11. Jadi saya akan mengubah konsep Chart Panel

Jangan:

CHART PANEL
└── satu chart tetap

Tetapi:

CHART PANEL
│
├── Visualization Type
│
├── Metric
│
├── Dimension
│
├── Comparison
│
└── Data

Dan ANNA menjadi controller:

ANNA
 │
 ├── pilih business
 ├── pilih metric
 ├── pilih dimension
 ├── pilih comparison
 ├── pilih visualization
 └── update chart

Misalnya context:

{
  "business": "evaluasi_produksi",
  "intent": "target_comparison",
  "metric": "production",
  "actual": 82450,
  "target": 95000,
  "visualization": "bullet"
}

12. Yang paling penting untuk ANNA

Saya akan menetapkan aturan:

ANNA tidak memilih chart berdasarkan estetika. ANNA memilih visualisasi berdasarkan intent analitis operator.

Mapping sederhananya:

Intent	Visualisasi
KPI / kondisi saat ini	KPI Card
Aktual vs Target	Bullet
Trend	Line
Ranking	Horizontal Bar
Komposisi	Stacked Bar
Distribusi	Bar / Histogram
Perbandingan wilayah	Horizontal Bar
Hubungan dua variabel	Scatter
Intensitas wilayah/periode	Heatmap
Kontribusi terhadap total	Treemap
Perubahan menuju target	Waterfall
Lokasi	Map

Dengan model ini, Map menjawab "di mana", Chart menjawab "berapa/bagaimana", dan ANNA menjawab "apa artinya".