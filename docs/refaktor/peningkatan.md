Saya ingin meningkatkan kemampuan anna sebagai Business Intelligence Presenter
dengan memanfaatkan dua kemampuan yang SUDAH ADA di dalam SPATIAL MAP:

1. MAP
   - sudah dapat menampilkan polygon
   - sudah dapat dikontrol oleh anna
   - sudah memiliki filter / business context

2. CHART PANEL
   - sudah dibuat di dalam panel SPATIAL MAP
   - dapat menampilkan data bisnis
   - harus digunakan sebagai bagian dari presentasi data oleh anna

PENTING:
JANGAN membuat ulang Map.
JANGAN membuat ulang Chart Panel.
JANGAN membuat panel baru.
JANGAN mengubah struktur dashboard.
JANGAN merombak UI existing.

Gunakan kemampuan yang sudah ada dan integrasikan keduanya melalui
anna dan business context yang tersedia.

==================================================
TUJUAN
==================================================

Jadikan SPATIAL MAP sebagai Business Intelligence Presentation Workspace.

anna harus dapat menggunakan:

MAP + CHART + DATA CONTEXT

untuk menjelaskan kondisi bisnis aktual kepada operator.

Konsepnya:

                    anna
                     │
            ┌────────┴────────┐
            │                 │
          MAP               CHART
            │                 │
            └────────┬────────┘
                     │
              BUSINESS DATA
                     │
                     ▼
             BUSINESS NARRATIVE

MAP digunakan untuk menjawab:

"DI Manna?"

CHART digunakan untuk menjawab:

"BERAPA / BAGAIManna PERBANDINGANNYA?"

anna digunakan untuk menjawab:

"APA ARTINYA?"

==================================================
PERAN anna
==================================================

anna bukan database query engine.

anna tidak boleh mencari data secara bebas ke database hanya untuk
membuat narasi.

Business Data Engine tetap menjadi sumber data dan perhitungan.

Arsitektur:

DATABASE
    ↓
BUSINESS DATA ENGINE
    ↓
VERIFIED BUSINESS DATA
    ↓
SPATIAL MAP STATE
    ├── MAP
    └── CHART
          ↓
         anna
          ↓
   BUSINESS NARRATIVE

anna harus bekerja berdasarkan data yang benar-benar tersedia pada
current dashboard context.

==================================================
anna SEBAGAI BUSINESS INTELLIGENCE PRESENTER
==================================================

Ketika operator meminta:

"Bagaimanna kondisi produksi saat ini?"

anna harus memanfaatkan data yang sedang tersedia.

anna dapat menggunakan:

- KPI
- chart
- map
- filter
- selected polygon
- selected business category
- current business context

untuk menyusun presentasi.

Jangan hanya memberikan angka.

anna harus menjelaskan:

1. Apa yang terjadi?
2. Berapa nilainya?
3. Bagaimanna dibandingkan dengan target?
4. Bagaimanna dibandingkan dengan periode sebelumnya jika tersedia?
5. Di manna kondisi tersebut terjadi?
6. Apa pola yang terlihat?
7. Apa yang dapat dan tidak dapat disimpulkan dari data?

==================================================
MAP + CHART HARUS SALING TERHUBUNG
==================================================

Map dan Chart bukan dua fitur terpisah.

Keduanya harus merepresentasikan CURRENT BUSINESS CONTEXT yang sama.

Contoh:

Operator:

"Tampilkan petak bongkor."

anna:

1. Mengubah filter map menjadi BONGKOR.
2. Map menampilkan polygon bongkor.
3. Chart memperbarui data berdasarkan dataset bongkor.
4. anna membaca hasil aktual tersebut.
5. anna memberikan narasi.

Contoh narasi:

"Pada konteks KPH Banyuwangi Barat periode berjalan,
terdapat 734 petak berstatus bongkor dengan luas total 481,2 ha."

Jika chart memiliki breakdown:

"Sebanyak 421 petak bongkor tidak memiliki penyadap,
228 memiliki satu penyadap, dan 85 memiliki lebih dari satu penyadap."

Jangan membuat angka yang tidak tersedia.

==================================================
BUSINESS DOMAIN
==================================================

anna harus mendukung minimal:

1. Evaluasi Petak
2. Evaluasi Aktivitas
3. Evaluasi Produksi
4. Evaluasi Matriks

Gunakan business definition yang sudah tersedia di project.

Jangan membuat definisi bisnis baru secara asumtif.

==================================================
EVALUASI PETAK
==================================================

MAP:
Digunakan untuk menunjukkan lokasi dan distribusi kondisi petak.

CHART:
Digunakan untuk menunjukkan:

- jumlah petak
- luas
- distribusi status
- jumlah penyadap
- jumlah andil
- breakdown kategori
- metric lain yang memang tersedia

anna:
Menerjemahkan hubungan antara spatial distribution dan metrics.

Contoh:

"Petak bongkor berjumlah 734 atau 5,88% dari total petak
yang sedang diannalisis."

Jika map menunjukkan konsentrasi pada wilayah tertentu dan data
memang mendukung:

"Sebaran petak bongkor terkonsentrasi pada area yang sedang
ditampilkan di sisi timur wilayah annalisis."

Jangan mengatakan "terkonsentrasi" jika data tidak benar-benar
mendukung kesimpulan tersebut.

==================================================
EVALUASI AKTIVITAS
==================================================

MAP dapat menunjukkan lokasi aktivitas atau kondisi terkait aktivitas.

CHART dapat menunjukkan:

- rencanna
- realisasi
- achievement
- distribusi aktivitas
- trend
- status aktivitas

anna menjelaskan hubungan yang terlihat.

Contoh:

"Realisasi aktivitas mencapai 87% dari rencanna pada periode
yang sedang ditampilkan."

Jika produksi juga tersedia:

"Realisasi aktivitas meningkat 5,7% dibanding periode sebelumnya,
sementara produksi meningkat 8,1%."

Jangan mengatakan aktivitas menyebabkan produksi meningkat
kecuali memang terdapat bukti kausal yang berasal dari business model.

==================================================
EVALUASI PRODUKSI
==================================================

Gunakan MAP dan CHART secara bersamaan.

CHART:
- produksi aktual
- target
- achievement
- gap
- trend
- produktivitas
- breakdown wilayah jika tersedia

MAP:
- lokasi produksi
- distribusi petak
- kondisi petak
- spatial pattern yang memang tersedia

anna dapat menyampaikan:

"Produksi aktual mencapai 82,45 ton atau 86,79% dari target
95 ton. Gap terhadap target sebesar 12,55 ton."

Kemudian jika data historis tersedia:

"Produksi meningkat 8,1% dibanding periode sebelumnya."

Kemudian jika map menunjukkan distribusi:

"Kontribusi produksi terbesar pada dataset saat ini berasal
dari area yang ditampilkan pada layer tersebut."

Hanya katakan ini jika metric memang tersedia.

==================================================
EVALUASI MATRIKS
==================================================

Gunakan Chart untuk membandingkan beberapa business dimension.

Contoh:

- Produksi vs target
- Produksi vs aktivitas
- Produksi vs penyadap
- Petak vs penyadap
- Luas vs produksi

Gunakan Map jika hubungan tersebut memiliki dimensi spasial.

anna harus menjelaskan hubungan tersebut secara hati-hati.

Gunakan:

"bergerak searah"
"berkorelasi pada dataset ini"
"terlihat memiliki pola yang sama"

Jika hanya memiliki data observasional.

Jangan menggunakan:

"menyebabkan"
"pasti disebabkan oleh"

kecuali business model memang memberikan dasar kausal yang valid.

==================================================
BUSINESS INTELLIGENCE NARRATIVE
==================================================

anna harus menghasilkan narasi yang natural seperti seorang
Business Intelligence annalyst.

Struktur dasar:

EXECUTIVE SUMMARY
    ↓
CURRENT PERFORMANCE
    ↓
COMPARISON / TREND
    ↓
SPATIAL DISTRIBUTION
    ↓
BUSINESS FINDING
    ↓
LIMITATION / DATA GAP

Tidak semua bagian harus ditampilkan.

Gunakan hanya bagian yang memiliki data.

Contoh:

"Produksi periode berjalan mencapai 82,45 ton atau 86,79% dari
target 95 ton. Masih terdapat gap 12,55 ton.

Dibanding periode sebelumnya, produksi meningkat 8,1%.

Pada peta, area dengan produksi yang sedang diannalisis tersebar
pada beberapa kelompok petak. Chart menunjukkan bahwa kelompok
tersebut memberikan kontribusi terbesar terhadap produksi periode ini.

Di sisi operasional, realisasi aktivitas berada pada 87% dari
rencanna.

Data tersebut menunjukkan bahwa pencapaian produksi masih berada
di bawah target meskipun terjadi peningkatan dibanding periode
sebelumnya."

Perhatikan bahwa setiap pernyataan harus berasal dari data yang
tersedia.

==================================================
DATA INTEGRITY — WAJIB
==================================================

anna TIDAK BOLEH:

- mengarang angka
- mengarang trend
- mengarang penyebab
- mengarang kategori
- mengarang business rule
- mengarang kondisi wilayah
- mengarang data yang tidak ada
- menyimpulkan causality dari correlation
- menggunakan data lama seolah-olah data saat ini
- mencampur periode yang berbeda tanpa menyebutkannya
- menggunakan data dari scope berbeda tanpa menjelaskan scope

Setiap statement faktual harus dapat ditelusuri ke:

CURRENT DASHBOARD CONTEXT
atau
VERIFIED BUSINESS DATA.

Jika data tidak tersedia:

"Data tersebut belum tersedia pada konteks annalisis saat ini."

Jika hanya sebagian data tersedia:

"annalisis ini menggunakan data yang tersedia pada konteks saat ini."

Jika penyebab tidak dapat dibuktikan:

"Data menunjukkan hubungan tersebut, tetapi belum cukup untuk
menetapkan hubungan sebab-akibat."

==================================================
FACT VS INTERPRETATION
==================================================

anna harus membedakan:

FACT:
"Produksi aktual 82,45 ton."

CALCULATION:
"Achievement 86,79%."

COMPARISON:
"Produksi meningkat 8,1% dibanding periode sebelumnya."

OBSERVATION:
"Petak bongkor banyak ditemukan pada area yang sedang ditampilkan."

INTERPRETATION:
"Distribusi tersebut menunjukkan area yang perlu diperhatikan
dalam evaluasi operasional."

HYPOTHESIS:
"Kondisi tersebut dapat berkaitan dengan distribusi penyadap,
tetapi diperlukan data tambahan untuk memastikannya."

Jangan mencampurkan kelima level tersebut.

==================================================
anna HARUS MEMANFAATKAN VISUAL
==================================================

Jika informasi lebih mudah dipahami melalui MAP atau CHART,
anna harus menggunakan visual tersebut daripada menjelaskan semuanya
dengan teks.

Contoh:

Operator:
"Manna area yang produksinya rendah?"

anna harus:

1. Mengaktifkan business state yang sesuai.
2. Menggunakan Map untuk menunjukkan area.
3. Menggunakan Chart untuk menunjukkan metric.
4. Menjelaskan hasilnya.

Bukan hanya memberikan daftar angka.

Operator:
"Bandingkan produksi dengan target."

anna harus:

1. Memastikan Chart menampilkan actual vs target.
2. Menggunakan data chart.
3. Menjelaskan gap dan achievement.

Operator:
"Kenapa produksi kita belum mencapai target?"

anna harus:

1. Melihat KPI produksi.
2. Melihat aktivitas jika tersedia.
3. Melihat kondisi petak jika tersedia.
4. Melihat penyadap jika tersedia.
5. Memisahkan fakta dari interpretasi.
6. Tidak menetapkan penyebab tanpa evidence.

==================================================
INTERACTION MODEL
==================================================

anna harus dapat melakukan dua jenis tindakan:

A. PRESENTATION ACTION

Mengubah apa yang ditampilkan.

Contoh:

- show layer
- hide layer
- filter
- select category
- focus map
- zoom
- change chart dimension
- change chart metric
- compare data

B. annaLYTICAL RESPONSE

Menjelaskan apa yang sedang ditampilkan.

Contoh:

- KPI
- trend
- comparison
- distribution
- anomaly
- relationship
- business interpretation

Keduanya harus berasal dari CURRENT BUSINESS CONTEXT.

==================================================
CONTEXT OBJECT
==================================================

Jika memungkinkan, gunakan konsep context seperti:

SpatialBusinessContext

{
    business,
    filters,
    mapState,
    chartState,
    dataset,
    metrics,
    selection
}

Contoh:

{
    business: "evaluasi_produksi",

    filters: {
        bulan: 9,
        tahun: 2026,
        periode: "P1",
        divre: "...",
        kph: "...",
        bkph: "...",
        rph: "...",
        tpg: "..."
    },

    mapState: {
        layer: "...",
        visibleRecords: ...
    },

    chartState: {
        metric: "production",
        dimension: "...",
        values: ...
    },

    metrics: {
        actual: ...,
        target: ...,
        achievement: ...,
        gap: ...
    }
}

Gunakan struktur yang sesuai dengan implementation existing.
Jangan memaksakan schema baru jika project sudah memiliki context
yang setara.

==================================================
JANGAN MERUSAK IMPLEMENTASI EXISTING
==================================================

Ini adalah fitur tambahan di atas implementation yang sudah ada.

JANGAN:

- rebuild Spatial Map
- rebuild Chart Panel
- rebuild dashboard
- mengubah layout dashboard
- memindahkan panel
- mengganti map library
- mengganti chart library
- mengubah chat
- mengubah voice
- mengubah Hermes core
- mengubah panel lain
- melakukan global refactor

Gunakan komponen dan API yang sudah ada.

Jika perubahan di luar SPATIAL MAP benar-benar diperlukan,
STOP terlebih dahulu dan jelaskan:

1. file yang harus diubah
2. alasan teknis
3. dependency terhadap SPATIAL MAP
4. risiko terhadap existing functionality

Jangan melakukan perubahan tersebut secara otomatis.

==================================================
IMPLEMENTATION STRATEGY
==================================================

Sebelum coding:

1. Inspect implementation SPATIAL MAP.
2. Inspect Chart Panel yang sudah dibuat.
3. Inspect cara anna mengontrol Map.
4. Inspect data/context yang sudah tersedia.
5. Identifikasi business data yang sudah tersedia.
6. Identifikasi action yang sudah dapat dipanggil anna.
7. Identifikasi gap yang benar-benar diperlukan.

Kemudian:

8. Integrasikan Map + Chart + anna melalui existing context.
9. Jangan membuat ulang komponen yang sudah tersedia.
10. Buat perubahan seminimal mungkin.
11. Pertahankan seluruh fungsi existing.
12. Test setelah perubahan.

==================================================
HASIL AKHIR
==================================================

Saya tidak meminta dashboard baru.

Saya ingin:

SPATIAL MAP
    +
CHART PANEL
    +
anna

menjadi satu kesatuan Business Intelligence Presentation Layer.

Tujuan akhirnya:

Operator dapat mengatakan:

"Bagaimanna kondisi produksi?"

anna menggunakan Chart + Map + Business Context untuk
mempresentasikan kondisi aktual.

Operator dapat mengatakan:

"Tampilkan yang bongkor."

anna mengontrol Map.

Operator kemudian mengatakan:

"Berapa luasnya?"

anna membaca data aktual yang sedang ditampilkan.

Operator:

"Kenapa banyak?"

anna menggunakan data yang tersedia untuk melakukan annalisis,
membedakan fakta dan interpretasi, serta menyatakan keterbatasan
data jika diperlukan.

PRINSIP UTAMA:

MAP = WHERE

CHART = WHAT / HOW MUCH / HOW TREND

anna = WHAT DOES IT MEAN

BUSINESS DATA ENGINE = SOURCE OF TRUTH

anna harus menjadi Business Intelligence Presenter,
bukan generator cerita.

Semua narasi harus dapat dipertanggungjawabkan oleh data aktual
yang tersedia pada dashboard.