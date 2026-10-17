# Wiki Index

> Content catalog. Setiap halaman wiki + ringkasan satu baris.
> Baca ini dulu untuk cari halaman relevan sebelum menjawab pertanyaan domain.
> Last updated: 2026-10-04 | Total pages: 104 (18 entities + 56 concepts + 1 comparison + 26 queries + 3 raw)

## Entities

- [[aktivitas-penyadapan]] — realisasi kegiatan lapangan; bedakan dari rencana
- [[andil]] — garapan penghubung penyadap dan petak; jumlah andil ≠ jumlah petak
- [[bkph]] — unit wilayah di bawah KPH
- [[divre]] — level organisasi/wilayah paling atas
- [[kph]] — unit pengelolaan hutan di bawah Divre; scope analisis utama
- [[mandor]] — aktor lapangan pengelola aktivitas penyadap per TPG; bukan penyadap
- [[operator-lapangan]] — akun directus_users + cakupan wilayah + relasi TPG; tanpa kolom npk di snapshot
- [[panel-dashboard]] — panel HUD inti bisnis + peta intent → panel
- [[panel-spatial-map]] — inventaris 13 komponen SPATIAL MAP + tabel op vs komponen + guard anti-loop
- [[penyadap]] — individu penyadap; bisa punya banyak andil
- [[peran-jabatan]] — hierarki ADM→Asper→Mantri→Mandor→KTS + mapping kode jabatan dan Directus roles
- [[petak]] — unit spasial/areal utama evaluasi lapangan
- [[petak-polygon]] — representasi geografis petak; bukan KPI
- [[produksi]] — realisasi hasil produksi per scope dan periode
- [[rencana-aktivitas]] — rencana kerja; jangan dianggap aktivitas aktual
- [[rph]] — unit wilayah di bawah BKPH
- [[target]] — sasaran produksi/evaluasi; TARGET ≠ REALISASI
- [[tpg]] — unit operasional lapangan di bawah RPH; titik temu wilayah + operasional

## Concepts

- [[arsitektur-skala-peta]] — tile vs GeoJSON vs centroid, spatial index, freshness PMTiles, pagination + cache
- [[alias-wilayah]] — tabel alias operator → filter resmi (jatim/jateng/jabar, licin, glenmore)
- [[aturan-denominator]] — semua ratio memperhatikan denominator
- [[aturan-interpretasi-kpi]] — empat aturan wajib sebelum simpulkan KPI
- [[aturan-summary-eksekutif]] — summary menjawab 7 pertanyaan; tanpa karangan kausal
- [[bank-uji-semantik]] — bank ~24 section pertanyaan uji pemahaman ANNA
- [[batas-data-engine]] — Dashboard owns data, ANNA owns interpretation; tanpa SQL langsung
- [[data-hilang]] — missing ≠ 0 kecuali engine mendefinisikan begitu
- [[dimensi-bisnis]] — dimensi utama untuk slicing dan drill-down
- [[disiplin-evidence]] — lima label FACT/DERIVED/COMPARISON/INTERPRETATION/HYPOTHESIS + contoh baku
- [[distingsi-semantik-kritis]] — pasangan konsep yang dilarang disamakan
- [[drill-down-operasional]] — TPG ↓ Penyadap ↓ Andil ↓ Petak ↓ Aktivitas
- [[drill-down-wilayah]] — DIVRE ↓ KPH ↓ BKPH ↓ RPH ↓ TPG
- [[framework-diagnostik]] — kerangka 11 tahap untuk "kenapa produksi turun?"
- [[gap-produksi]] — Gap = Target − Realisasi
- [[golden-rules]] — 15 larangan/perintah ANNA
- [[laporan-bisnis]] — dokumen N halaman siap cetak via `/api/spatial/report` (Unduh = print, Tutup = visible:false)
- [[growth-produksi]] — Growth = (Current − Previous) / Previous × 100%
- [[interpretasi-status]] — BONGKOR/IDLE tak boleh disamakan tanpa cek rule + periode
- [[inteligensi-spasial]] — peta sebagai analytical presentation
- [[klasifikasi-fakta]] — Fact / Derived / Comparison / Interpretation / Hypothesis
- [[klasifikasi-pertanyaan]] — RETRIEVAL … EXPLORATION per pertanyaan operator
- [[medan-aktivitas]] — cuaca/akses/ketinggian per aktivitas + rantai sadap→penerimaan + matriks sintesis medan × hasil
- [[konteks-target]] — pencapaian dibaca bersama target absolut
- [[konteks-waktu]] — setiap pertanyaan butuh tanggal + comparison period
- [[korelasi-vs-kausasi]] — data observasional bukan bukti sebab-akibat
- [[kualitas-data]] — waspada duplikat, missing, inkonsistensi, stale, efek sinkron
- [[measures]] — measure yang bisa diagregasi sesuai scope valid
- [[metrik-aktivitas]] — aktivitas dianalisis per jumlah/penyadap/periode/wilayah/petak
- [[model-evidence]] — rantai Engine Result ↓ Evidence ↓ ANNA ↓ Statement
- [[model-hipotesis]] — format Hypothesis / Supporting / Missing / How To Test
- [[model-insight-bisnis]] — rantai Observation ↓ Evidence ↓ Comparison ↓ Interpretation ↓ Implication
- [[model-inteligensi]] — alur baku Operator Intent ↓ … ↓ Presentation
- [[model-mental]] — peta model bisnis SIMOGE + alur operator sampai penjelasan
- [[narasi-produksi]] — pertanyaan produksi via answer_production + evidence-nya
- [[operasi-dashboard]] — sesi SESI/TTL, profil anna, error umum + cara pulih
- [[penalaran-spasial]] — alur KPI ↓ Wilayah ↓ Petak ↓ Lokasi
- [[penanganan-ambigu]] — intent tak jelas: pertahankan konteks, lalu klarifikasi
- [[pencapaian-target]] — Pencapaian = Realisasi / Target × 100%
- [[perilaku-terlarang-dan-penilaian]] — daftar FAIL + skala skor 0–5 + bobot dimensi + kriteria lulus
- [[periode]] — P1/P2 + hari/minggu/bulan/tahun/YTD/pembanding
- [[pohon-diagnostik]] — cabang volume/workforce/produktivitas/aktivitas/petak/spasial
- [[pola-nalar-bisnis]] — 15 langkah tiap pertanyaan bisnis + contoh KPH A
- [[population-awareness]] — samakan population sebelum bandingkan angka
- [[presentasi-chart]] — show_spatial_chart untuk comparison/trend/distribution/ranking
- [[presentasi-spasial]] — show_on_map sebagai abstraksi; tanpa raw GeoJSON
- [[preservasi-konteks]] — pertahankan scope/period/filter/entity/KPI/map/thread
- [[produktivitas]] — output relatif; wajib sebut denominator
- [[pronomina-kontekstual]] — itu/di sana/wilayah tersebut dibaca dari konteks
- [[semantik-dashboard]] — intent tampil/sembunyi/filter/drill-down/bandingkan
- [[semantik-chart]] — bar/line/komposisi/map + syarat title-metric-dimensi-scope-periode
- [[semantik-ranking]] — terbaik/terburuk wajib bermetric jelas
- [[status-petak]] — AKTIF / IDLE / BONGKOR + maknanya
- [[struktur-laporan-eksekutif]] — 13 section laporan bisnis lengkap
- [[template-hasil-uji]] — format pencatatan baku setiap test yang dijalankan
- [[tool-bisnis-anna]] — 38 template simoge (P0: `kph_summary_map` agregat centroid+KPI per KPH/BKPH/DIVRE, viewport `bounds`+`zoom`) + chart/review + larangan SQL

## Comparisons

- [[absolut-vs-relatif]] — total produksi vs produksi per penyadap + jebakannya

## Queries

- [[uji-entitas-retrieval]] — E001–E015 + R001–R014: entitas dasar + retrieval
- [[uji-filter-konteks]] — F001–F017: bahasa operator → filter dashboard
- [[uji-ontologi-relasi]] — O001–O015: hubungan antar-entitas
- [[uji-kpi]] — K001–K017: KPI dan derived metrics
- [[uji-jebakan-kpi]] — T001–T013: jebakan interpretasi KPI
- [[uji-temporal]] — TM001–TM012: periode, tren, perubahan waktu
- [[uji-komparasi]] — C001–C010: perbandingan antar dimensi bisnis
- [[uji-diagnostik]] — D001–D012: indikator relevan saat KPI berubah
- [[uji-root-cause]] — RC001–RC010: diagnostic tree tanpa karang kausal
- [[uji-spasial]] — S001–S013: numerik + konteks geografis
- [[uji-drill-down]] — MD001–MD010: pindah antar level ontology
- [[uji-eksekutif]] — EX001–EX015: laporan bisnis
- [[uji-bahasa-ambigu]] — A001–A015: bahasa operator tidak formal
- [[uji-ambiguitas-semantik]] — SA001–SA010: klarifikasi definisi tak jelas
- [[uji-integritas-data]] — DI001–DI012: deteksi data tak layak simpulkan
- [[uji-desain-kpi]] — KD001–KD010: berpikir sebagai BI analyst
- [[uji-nalar-lanjutan]] — AR001–AR010: reasoning lintas KPI
- [[uji-kausalitas]] — CA001–CA006: korelasi vs sebab-akibat
- [[uji-laporan-bisnis]] — BR001–BR015: laporan bisnis lengkap
- [[uji-rantai-percakapan]] — CH001–CH030: konteks lintas giliran
- [[uji-ontologi-akhir]] — ONT001–ONT003: tiga pertanyaan besar model bisnis
- [[uji-prime-final]] — PI001–PI002 + FINAL001: ujian tertinggi analis
- [[intent-ke-template-peta]] — mapping intent user → template show_on_map + param wajib (rogojampi, licin, glenmore, jatim, jateng, jabar)
- [[skala-multi-divre]] — decision tree template skala besar + param viewport + batas multi-value + fallback chain
- [[contoh-laporan-eksekutif-kph-barat]] — golden example laporan 13-section September 2026 KPH Barat
- [[contoh-laporan-tren-bulanan]] — golden example tren Mei vs April 2026 + YoY ditolak (data 2025 kosong)
