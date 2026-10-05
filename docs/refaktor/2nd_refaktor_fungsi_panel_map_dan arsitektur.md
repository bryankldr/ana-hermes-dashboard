Saya ingin melakukan perubahan TERBATAS pada project anna-hermes-dashboard.

TUJUAN UTAMA:
Tambahkan Business Intelligence / Business Map functionality HANYA pada panel yang sudah ada bernama:

SPATIAL MAP

JANGAN mengubah arsitektur UI dashboard secara keseluruhan.

==================================================
ATURAN PALING PENTING — JANGAN MERUSAK
==================================================

1. Jangan mengubah struktur UI dashboard yang sudah ada.

2. Jangan mengubah, menghapus, memindahkan, mengganti nama,
   memperbesar, memperkecil, atau merombak panel selain SPATIAL MAP.

3. Panel berikut HARUS tetap bekerja dan tampil seperti sekarang:

- PERFORMANCE BRIEFING
- MISSION KANBAN
- VAULT STATUS
- ACTIVE REPOSITORIES
- EVENT STREAM
- INTELLIGENCE SURFACE
- SYSTEM MATRIX
- AGENT PIPELINE
- ANDROID AVD
- CHAT / COMMAND AREA
- seluruh komponen HUD lainnya

4. Jangan melakukan global refactor hanya untuk fitur ini.

5. Jangan mengganti framework, library utama, layout system,
   styling system, atau map implementation yang sudah ada tanpa
   alasan teknis yang benar-benar diperlukan.

6. Jangan membuat dashboard baru.

7. Jangan membuat halaman baru.

8. Jangan memindahkan SPATIAL MAP ke tempat lain.

9. Jangan mengubah fungsi Hermes yang sudah berjalan.

10. Jangan mengubah fungsi chat, voice, terminal, tools, memory,
    repository mannagement, atau fitur agent lainnya.

11. Jangan menghapus fitur existing hanya karena tidak diperlukan
    untuk fitur baru.

12. Gunakan pendekatan incremental:
    EXTEND EXISTING SPATIAL MAP,
    bukan REBUILD DASHBOARD.

==================================================
TUJUAN FITUR SPATIAL MAP
==================================================

SPATIAL MAP akan menjadi Business Map Workspace.

Saat ini SPATIAL MAP sudah memiliki:

- search "cari no petak..."
- map
- zoom control
- layer control
- polygon/map visualization

Pertahankan seluruh komponen tersebut.

Tambahkan kemampuan bisnis di dalam area SPATIAL MAP.

==================================================
GLOBAL MAP FILTER
==================================================

Tambahkan filter di dalam SPATIAL MAP untuk:

- Bulan
- Tahun
- Periode
- DIVRE
- KPH
- BKPH
- RPH
- TPG

Filter tersebut adalah filter khusus SPATIAL MAP.

JANGAN menjadikannya global filter untuk seluruh dashboard.

Perubahan filter hanya boleh mempengaruhi data/map yang ditampilkan
di SPATIAL MAP.

==================================================
BUSINESS CATEGORY
==================================================

Tambahkan business selector di SPATIAL MAP:

- Evaluasi Petak
- Evaluasi Aktivitas
- Evaluasi Produksi
- Evaluasi Matriks

Business selector harus tetap berada di dalam panel SPATIAL MAP.

Jangan membuat panel baru untuk business selector.

==================================================
EVALUASI PETAK
==================================================

Evaluasi Petak berhubungan dengan:

- petak
- polygon
- andil
- penyadap

Kategori/layer yang dapat ditampilkan misalnya:

- Semua Petak
- Bongkor
- Idle
- Tanpa Penyadap
- Multi Penyadap

Kategori harus dapat digunakan untuk memfilter polygon yang terlihat
di map.

==================================================
EVALUASI AKTIVITAS
==================================================

Evaluasi Aktivitas berhubungan dengan aktivitas penyadapan.

Kategori dapat mencakup business state yang memang tersedia dari
Business Data Engine.

Jangan membuat definisi bisnis baru jika belum tersedia di project.

==================================================
EVALUASI PRODUKSI
==================================================

Evaluasi Produksi berhubungan dengan:

- target
- produksi aktual
- produktivitas
- gap
- pencapaian

Gunakan business data yang memang tersedia.

Jangan mengarang nilai atau business rule.

==================================================
EVALUASI MATRIKS
==================================================

Evaluasi Matriks digunakan untuk melihat hubungan antar business
dimension yang sudah tersedia.

Contoh:

- petak vs penyadap
- aktivitas vs produksi
- target vs aktual
- luas vs produksi

Implementasikan hanya berdasarkan data/business logic yang benar-benar
tersedia di project.

==================================================
BUSINESS DATA ARCHITECTURE
==================================================

PENTING:

Hermes/anna TIDAK boleh menjadi database query engine untuk fitur ini.

Gunakan arsitektur:

DATABASE
    ↓
BUSINESS DATA ENGINE
    ↓
PROCESSED BUSINESS DATA
    ↓
SPATIAL MAP STATE
    ↓
MAP / POLYGON
    ↓
anna

Business Data Engine bertanggung jawab atas:

- database query
- join
- aggregation
- business rule
- calculation
- geospatial preparation

anna/Hermes bertanggung jawab atas:

- memahami intent operator
- membaca context SPATIAL MAP
- mengubah filter/map state melalui action yang tersedia
- menjelaskan data yang sedang ditampilkan
- membantu operator memahami business meaning

Jangan menambahkan direct SQL access ke Hermes hanya untuk
menyelesaikan fitur ini.

==================================================
INTERAKSI anna DENGAN SPATIAL MAP
==================================================

anna harus dapat memahami context SPATIAL MAP.

Contoh:

Operator:
"Tampilkan petak bongkor."

anna harus memahami:

business = evaluasi_petak
filter = status:bongkor

Kemudian anna mengubah state SPATIAL MAP menggunakan mekanisme/action
yang memang tersedia.

MAP kemudian menampilkan polygon yang sesuai.

anna tidak perlu melakukan query database secara langsung.

Contoh lain:

Operator:
"Berapa luas petak bongkor yang sedang tampil?"

anna harus membaca metric/context yang tersedia dari SPATIAL MAP.

Jika data tersebut tidak tersedia, jangan mengarang.

==================================================
DASHBOARD STATE
==================================================

Buat atau gunakan state khusus untuk SPATIAL MAP jika memang diperlukan.

Konsepnya:

SpatialMapState
├── business
├── filters
├── dataset
├── layers
├── selection
└── metrics

State ini harus terisolasi dari state panel dashboard lainnya.

Jangan membuat perubahan state SPATIAL MAP menyebabkan panel lain
berubah secara tidak sengaja.

==================================================
UI/UX
==================================================

Pertahankan visual style dashboard yang sekarang.

Jangan membuat desain baru yang bertentangan dengan HUD existing.

Gunakan komponen, typography, spacing, border, color, animation,
dan interaction pattern yang sudah digunakan oleh SPATIAL MAP.

Jangan mengubah ukuran utama panel SPATIAL MAP.

Jika ruang UI terbatas, gunakan mekanisme compact seperti:

- dropdown
- popover
- compact toolbar
- collapsible filter
- overlay

Tetapi tetap berada di dalam batas SPATIAL MAP.

Jangan memperbesar panel dengan mengorbankan panel lain.

==================================================
SAFE IMPLEMENTATION PROCESS
==================================================

Sebelum melakukan perubahan:

1. Inspect project structure.
2. Identifikasi file/component yang bertanggung jawab terhadap
   SPATIAL MAP.
3. Identifikasi map state dan data flow yang sudah ada.
4. Identifikasi Business Data Engine yang sudah tersedia.
5. Identifikasi bagaimanna polygon saat ini dimuat.
6. Identifikasi API/data source yang sudah digunakan.
7. Jangan langsung mengubah kode.

Setelah memahami struktur:

8. Buat perubahan sekecil mungkin.
9. Reuse component dan service existing.
10. Isolasi logic baru pada module/component Spatial Map.
11. Hindari perubahan file yang tidak berkaitan.
12. Jangan melakukan refactor besar.

==================================================
REGRESSION SAFETY
==================================================

Setelah implementasi:

- pastikan dashboard masih dapat dijalankan
- pastikan semua panel existing masih tampil
- pastikan chat tetap bekerja
- pastikan voice tetap bekerja
- pastikan Hermes tetap bekerja
- pastikan map tetap dapat digunakan
- pastikan search petak tetap bekerja
- pastikan zoom tetap bekerja
- pastikan layer control tetap bekerja
- pastikan polygon existing tetap tampil
- pastikan tidak ada error baru pada console
- pastikan tidak ada perubahan layout pada panel lain

Jika suatu perubahan berpotensi merusak fungsi existing,
JANGAN lakukan perubahan tersebut.

==================================================
ATURAN MODIFIKASI
==================================================

Scope perubahan:

ALLOWED:
- SPATIAL MAP component
- SPATIAL MAP state
- SPATIAL MAP data adapter
- Business Map logic yang diperlukan SPATIAL MAP
- Business Data Engine yang memang diperlukan untuk menyediakan
  data SPATIAL MAP

NOT ALLOWED:
- redesign dashboard
- redesign HUD
- perubahan panel lain
- perubahan layout global
- perubahan chat UI
- perubahan voice UI
- perubahan Hermes core
- perubahan memory system
- perubahan repository system
- perubahan terminal
- perubahan unrelated business logic

Jika membutuhkan perubahan di luar scope tersebut,
STOP dan jelaskan terlebih dahulu file apa yang perlu diubah,
mengapa diperlukan, dan apa risiko perubahan tersebut.

Jangan melakukan perubahan tersebut secara otomatis.

==================================================
HASIL YANG DIHARAPKAN
==================================================

Hasil akhir harus tetap terlihat sebagai dashboard yang SAMA seperti
sekarang.

Perbedaannya hanya:

SPATIAL MAP menjadi lebih pintar.

SPATIAL MAP sekarang dapat:

1. memilih business category
2. menggunakan filter:
   Bulan
   Tahun
   Periode
   DIVRE
   KPH
   BKPH
   RPH
   TPG

3. menampilkan polygon berdasarkan business state
4. mengubah layer berdasarkan konteks bisnis
5. menerima perintah natural language dari anna
6. memberikan context kepada anna
7. memungkinkan anna menjelaskan data yang sedang ditampilkan

PRINSIP AKHIR:

DO NOT REBUILD THE DASHBOARD.

DO NOT REDESIGN THE DASHBOARD.

DO NOT REFACTOR UNRELATED CODE.

EXTEND ONLY THE EXISTING SPATIAL MAP.

PRESERVE ALL EXISTING FUNCTIONALITY.

MAKE THE SMALLEST SAFE CHANGE POSSIBLE.
==================================================
PETAK_SIMPLE.JSON — CADANGAN EVALUASI BISNIS HARIAN (AMANAT BARU)
==================================================

Risiko (selesai): petak_simple.json lama 2273 {n,p} tidak sama dengan kondisi sebenarnya (kph_bwb_sandbox2 810 RTT 2026, 1003 polygon, + andil/aktivitas/realisasi/target) — fix: wrapper {meta,features} 999 deduped harian (1003 raw → 999 distinct, 195 orphan tanpa RTT 2026) selaras DB (generate WIB scripts/refresh_petak_simple.py, arsip snapshots/petak_YYYY-MM-DD.json). Business Map tetap DB 100%.

Aturan baru (masuk rencana refaktor + map.js tetap DB 100%):

1. petak_simple.json HARUS berisi sesuai bisnis yang sesungguhnya — bukan dump lama. Format baru {meta, features}:
   - meta: {generated_at (WIB ISO), source:"kph_bwb_sandbox2", tahun_rtt, periode "YYYY-MM-P1/P2", counts{total, with_polygon, rtt_2026}, generator, version}
   - features: [{n, p, tahun_rtt, kode_divre, kode_kph, kode_bkph, kode_rph, kode_tpg, luas_baku, target_rkap, ...polygon}]
   - Backward compat: loader harus terima array lama [{n,p}] maupun wrapper baru {meta, features}.

2. Update HARIAN — setiap hari file di-override dengan snapshot evaluasi hari ini (periode = tanggal hari ini P1 1-15 / P2 16-akhir). Snapshot lama diarsip ke ui/data/snapshots/petak_YYYY-MM-DD.json untuk YOY (ANNA bisa bandingkan tahun_rtt, luas, target, periode).

3. Business Map pakai DB 100% — map.js → businessAdapter → /api/simoge/show_on_map → simoge_db 7 _map → map_store → Leaflet WARNA_STYLE. petak_simple.json TIDAK dipakai untuk warna/filter bisnis, hanya cadangan.

4. ANNA sebagai referensi YOY — bila operator tanya "tahun lalu vs tahun ini" atau koneksi DB lambat, ANNA baca meta+features cadangan (via /api/spatial/stats + /api/spatial/query + file wrapper) dan jelaskan dengan identitas periode yang jelas. Jangan karang — sebut generated_at dan tahun_rtt.

5. Identitas harus terlihat — server /api/spatial/stats kembalikan meta (generated_at, tahun_rtt, periode, counts), dan map.js tidak perlu ubah; spatial_intel yang toleran wrapper. Script generator + cron harian di repo (scripts/refresh_petak_simple.py + docs).

Scope: hanya petak_simple.json + spatial_intel.py + generator. map.js Business Map tetap DB 100% (tidak diubah untuk polygon bisnis). Jangan ubah panel lain.

