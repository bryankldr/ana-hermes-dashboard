# IMPLEMENTATION PROMPT — Intelligent Business Insight Engine untuk Landing Page SIMOGE HUD

## 1. Peran dan Konteks Proyek

Bertindak sebagai **Senior Python Backend Engineer, Database Engineer, dan Business Intelligence Engineer** yang bertanggung jawab mengimplementasikan sistem *Intelligent Business Insight Engine* untuk proyek SIMOGE HUD milik PT Perhutani.

SIMOGE HUD merupakan aplikasi web dengan backend Python/FastAPI dan database MariaDB. Sistem memiliki Business Data Engine yang bertanggung jawab terhadap query, join, agregasi, dan aturan perhitungan bisnis.

Implementasi ini khusus untuk **tiga card insight pada landing page sebelum pengguna login**.

Tujuan utamanya adalah menampilkan tiga insight bisnis yang aktual, dinamis, relevan, dan dapat diperbarui secara otomatis berdasarkan data database internal.

## 2. Tujuan Implementasi

Bangun mekanisme yang dapat:

1. Membaca data bisnis dari database internal menggunakan query yang tervalidasi.
2. Menghitung metrik, tren, perbandingan periode, anomali, dan indikator kinerja berdasarkan aturan bisnis yang terdefinisi.
3. Menghasilkan beberapa kandidat insight secara otomatis.
4. Memilih satu insight terbaik untuk setiap domain menggunakan deterministic ranking engine.
5. Memperbarui konten tiga card secara otomatis sesuai perubahan data sumber.
6. Menyajikan hasil melalui API yang ringan dan aman untuk landing page.
7. Menampilkan data yang dapat ditelusuri ke sumber, periode, dan waktu kalkulasinya.
8. Beroperasi sepenuhnya tanpa LLM pada jalur pemrosesan insight landing page.

**Larangan:** Jangan menggunakan LLM, chatbot, AI generatif, layanan AI eksternal, atau pemanggilan model bahasa untuk membaca database, menentukan insight, menyusun judul, membuat narasi, atau mengisi ketiga card. Semua analisis dan teks card harus dihasilkan menggunakan query, fungsi Python deterministik, aturan bisnis, dan template teks.

## 3. Batasan Ruang Lingkup

Implementasi hanya mencakup:

- Landing page publik sebelum login.
- Tiga card Business Intelligence Highlights.
- Query engine untuk menghasilkan insight.
- Perhitungan metrik dan analisis deterministik.
- Ranking kandidat insight.
- Snapshot hasil insight dan cache.
- API untuk menyajikan hasil.
- Scheduler atau mekanisme pemicu pembaruan.
- Pengujian, keamanan, dan dokumentasi.

Jangan melakukan redesign atau perubahan yang tidak diminta pada:

- Dashboard setelah login.
- Workspace Anna.
- Panel chart dan laporan.
- Spatial Map.
- Manajemen pengguna dan autentikasi.
- Modul operasional yang sudah berjalan.
- Struktur database yang sudah ada, kecuali perubahan benar-benar diperlukan dan telah disetujui.

Pertahankan perilaku aplikasi yang sudah berjalan. Jangan menghapus, mengganti, atau memindahkan modul yang ada hanya demi menyesuaikan rancangan baru.

## 4. Tiga Domain Insight

### Card 1 — Production Intelligence

Fokus: kinerja produksi dan pencapaian target.

Kandidat insight yang dapat dikembangkan sesuai ketersediaan data:

- Realisasi produksi dibandingkan target pada periode berjalan.
- Perubahan produksi terhadap periode sebelumnya yang sebanding.
- Tren produksi berdasarkan hari, minggu, bulan, atau tahun.
- Wilayah dengan peningkatan atau penurunan produksi yang signifikan.
- Peringkat pencapaian produksi antarwilayah.
- Penyimpangan dari baseline historis.

Metrik target dan realisasi hanya boleh digunakan jika definisi serta sumber datanya benar-benar tersedia.

### Card 2 — Field Operations Intelligence

Fokus: aktivitas penyadapan dan kondisi operasional lapangan.

Kandidat insight:

- Perubahan jumlah aktivitas sadap.
- Perubahan cakupan penyadap aktif atau wilayah aktif.
- Petak atau wilayah dengan penurunan aktivitas.
- Perbandingan aktivitas antarwilayah.
- Aktivitas yang menyimpang dari pola historis.
- Data aktivitas yang memerlukan verifikasi berdasarkan aturan kualitas data.

Jangan menyamakan jumlah catatan aktivitas dengan jumlah penyadap aktif tanpa definisi metrik dan metode deduplikasi yang benar.

### Card 3 — Supply Chain Intelligence

Fokus: aliran hasil produksi dari penerimaan hingga pengangkutan dan niaga.

Kandidat insight:

- Volume penerimaan pada periode tertentu.
- Perbandingan volume antartahapan jika datanya tersedia.
- Selisih rekonsiliasi berdasarkan aturan bisnis yang valid.
- Jumlah catatan atau dokumen yang belum cocok.
- Tahapan dengan penumpukan proses.
- Perubahan volume berdasarkan periode atau wilayah.

Pahami relasi database sebelum membuat query. Jangan mengasumsikan bahwa semua tabel memiliki hubungan langsung atau menggunakan kolom penghubung yang sama. Hindari penghitungan ganda akibat join satu-ke-banyak.

## 5. Tahap Pertama — Audit Proyek dan Database

Sebelum menulis kode, lakukan pemeriksaan terhadap repository dan sistem yang ada.

Identifikasi:

- Struktur direktori proyek.
- Framework frontend yang digunakan.
- Implementasi FastAPI yang sudah tersedia.
- Konfigurasi koneksi MariaDB.
- Modul Business Data Engine yang sudah ada.
- Query, service, repository, dan fungsi agregasi yang dapat digunakan kembali.
- Mekanisme autentikasi dan hak akses.
- Cara penyajian static assets dan landing page.
- Scheduler atau cache yang sudah digunakan.
- Tabel, kolom, primary key, foreign key, relasi, indeks, dan volume data yang relevan.
- Definisi metrik bisnis yang sudah disepakati.
- Timestamp pembaruan data dan keterlambatan sinkronisasi.

Prioritaskan penggunaan ulang Business Data Engine yang sudah ada. Jangan membuat query engine kedua yang menduplikasi aturan bisnis apabila kemampuan tersebut sudah tersedia.

Buat pemetaan untuk setiap kandidat metrik dengan format:

| Atribut | Deskripsi |
|---|---|
| `metric_key` | Identifier metrik yang unik |
| `domain` | Domain bisnis pemilik metrik |
| `definition` | Definisi bisnis yang disepakati |
| `source_tables` | Tabel sumber yang benar-benar tersedia |
| `source_fields` | Kolom sumber yang diperlukan |
| `join_rules` | Relasi dan kunci penghubung |
| `aggregation` | SUM, COUNT DISTINCT, AVG, atau metode yang sesuai |
| `time_field` | Kolom tanggal yang digunakan |
| `unit` | Satuan hasil |
| `comparison_rule` | Aturan pembanding periode |
| `freshness_rule` | Batas umur data yang dapat diterima |
| `validation_rule` | Validasi kualitas data |
| `visibility` | Klasifikasi publik atau internal |

Jangan menebak nama tabel, kolom, relasi, ataupun definisi bisnis. Jika informasi belum tersedia, dokumentasikan sebagai gap dan jangan aktifkan metrik tersebut sebelum tervalidasi.

## 6. Tahap Kedua — Rancang Intelligent Query Engine

Implementasikan engine modular dengan komponen berikut. Sesuaikan nama modul dengan struktur repository yang telah diaudit.

### A. Semantic Metric Catalog

Buat katalog metrik yang menyimpan definisi bisnis dan aturan perhitungan.

Setiap metrik harus memiliki:

- Identifier unik.
- Domain.
- Definisi bisnis.
- Query atau query builder yang diizinkan.
- Satuan.
- Periode analisis.
- Metode agregasi.
- Aturan perbandingan.
- Aturan validasi.
- Persyaratan freshness.
- Klasifikasi data.
- Versi definisi metrik.

Katalog merupakan sumber kebenaran untuk pemaknaan dan perhitungan metrik.

### B. Intelligent Query Planner

Bangun query planner deterministik yang memilih query berdasarkan:

- Domain yang sedang dianalisis.
- Metrik yang tersedia.
- Rentang waktu.
- Wilayah analisis yang diizinkan.
- Ketersediaan data.
- Kebutuhan perbandingan historis.
- Prioritas analisis.
- Biaya eksekusi query.

Planner bukan model AI. Planner bekerja berdasarkan katalog metrik, konfigurasi, dependency graph, dan aturan pemilihan query.

Gunakan query yang diregistrasi atau query builder terkontrol. Jangan mengizinkan eksekusi SQL arbitrer dari input pengguna atau string dinamis yang tidak tervalidasi.

### C. Query Executor

Executor bertanggung jawab terhadap eksekusi query ke MariaDB.

Persyaratan:

- Gunakan parameterized queries.
- Gunakan akun database dengan hak baca minimum yang diperlukan.
- Batasi tabel, kolom, dan operasi yang diizinkan.
- Terapkan timeout dan penanganan error.
- Hindari query N+1 dan full table scan yang tidak diperlukan.
- Gunakan indeks yang sesuai untuk filter tanggal, wilayah, dan foreign key.
- Hindari `SELECT *`.
- Jangan mengubah atau menghapus data operasional.
- Jangan menambahkan migrasi database otomatis tanpa persetujuan.

### D. Temporal Analyzer

Implementasikan analisis temporal deterministik.

Kemampuan minimum:

- Membandingkan periode dengan periode sebelumnya yang setara.
- Menghitung perubahan absolut.
- Menghitung perubahan persentase jika penyebut valid.
- Mengidentifikasi tren berdasarkan beberapa periode.
- Menangani periode yang belum lengkap.
- Menangani nilai nol, data kosong, dan denominator nol.
- Menggunakan zona waktu yang konsisten.
- Memilih kolom waktu berdasarkan definisi metrik yang benar.

Jangan menganggap data yang belum tersinkronisasi sebagai penurunan aktivitas bisnis.

### E. Anomaly Detector

Implementasikan deteksi anomali berdasarkan metode statistik atau aturan bisnis yang sesuai.

Metode yang dapat dipertimbangkan:

- Threshold bisnis yang dikonfigurasi.
- Perbandingan terhadap baseline historis.
- Moving average.
- Median dan median absolute deviation.
- Perubahan persentase yang signifikan.
- Aturan konsistensi antarentitas atau antartahapan.

Jangan menerapkan satu threshold universal pada semua metrik. Pilih metode berdasarkan karakteristik metrik, ketersediaan data historis, dan validasi terhadap hasil aktual.

Setiap anomali harus menyimpan nilai observasi, baseline, selisih, metode deteksi, dan alasan mengapa anomali teridentifikasi.

### F. Insight Candidate Generator

Hasil analisis diubah menjadi kandidat insight terstruktur.

Setiap kandidat minimal menyimpan:

- `candidate_id`
- `domain`
- `metric_key`
- `insight_type`
- `current_value`
- `previous_value`, jika relevan
- `absolute_change`, jika relevan
- `percentage_change`, jika valid
- `unit`
- `period_start`
- `period_end`
- `comparison_period`
- `entity_scope`
- `entity_label`, jika aman untuk dipublikasikan
- `severity`
- `confidence_score`
- `freshness_status`
- `data_quality_status`
- `calculated_at`
- `metric_definition_version`
- `evidence`
- `template_key`

Nilai dan bukti harus berasal dari hasil query dan analisis terverifikasi.

## 7. Tahap Ketiga — Deterministic Insight Ranking Engine

Buat ranking engine untuk memilih satu kandidat terbaik per domain.

Sebelum memberikan skor, terapkan hard eligibility checks. Kandidat tidak boleh dipublikasikan apabila:

- Data sumber tidak cukup.
- Data melewati batas freshness.
- Validasi perhitungan gagal.
- Periode pembanding tidak sepadan.
- Definisi metrik belum tervalidasi.
- Klasifikasi data tidak mengizinkan publikasi.
- Nilai atau satuan tidak konsisten.

Setelah kandidat lolos, lakukan ranking berdasarkan faktor yang dapat dikonfigurasi:

1. Dampak bisnis.
2. Tingkat signifikansi perubahan.
3. Kebaruan temuan.
4. Keandalan data.
5. Kualitas perbandingan.
6. Tingkat urgensi.
7. Relevansi terhadap domain.
8. Keragaman tipe insight agar konten tidak repetitif.

Pisahkan nilai `severity` dari `confidence_score`. Anomali yang besar tetapi tidak didukung data berkualitas tidak boleh otomatis menempati posisi pertama.

Setiap domain menghasilkan paling banyak satu insight utama. Jika tidak ada kandidat yang memenuhi syarat, gunakan fallback deterministik seperti ringkasan kondisi terkini atau status data tidak tersedia.

Jangan mengarang insight hanya untuk memastikan card selalu terisi.

## 8. Tahap Keempat — Teks Card Tanpa LLM

Gunakan template teks yang terdaftar dan tervalidasi.

Contoh pola template:

| Kondisi | Template judul |
|---|---|
| Perubahan positif signifikan | `"{metric_label} meningkat"` |
| Perubahan negatif signifikan | `"{metric_label} menurun"` |
| Anomali terdeteksi | `"Penyimpangan {metric_label} terdeteksi"` |
| Capaian memenuhi aturan target | `"Target {metric_label} tercapai"` |
| Tidak ada perubahan signifikan | `"Kondisi {metric_label} relatif stabil"` |
| Data kedaluwarsa | `"Data {metric_label} belum diperbarui"` |

Template hanya digunakan apabila kondisi terkait benar-benar terpenuhi.

Setiap card harus dapat menampilkan:

- Domain dan label metrik.
- Nilai utama.
- Satuan.
- Perubahan atau pembanding.
- Ringkasan singkat.
- Wilayah atau entitas terkait jika relevan.
- Periode analisis.
- Waktu kalkulasi.
- Status freshness.

Gunakan format angka, tanggal, persentase, dan satuan yang konsisten dengan standar aplikasi berbahasa Indonesia.

Jangan menyusun narasi bebas. Semua teks harus berasal dari template deterministik dan nilai hasil analisis.

## 9. Tahap Kelima — Snapshot dan Cache

Buat mekanisme penyimpanan hasil insight agar landing page tidak menjalankan query analitik berat setiap kali halaman dibuka.

Periksa terlebih dahulu apakah proyek sudah memiliki mekanisme snapshot atau cache yang dapat digunakan.

Jika belum, rancang penyimpanan snapshot yang memuat:

- Domain.
- Metrik.
- Nilai dan hasil perbandingan.
- Teks hasil template.
- Periode analisis.
- Status validasi.
- Waktu kalkulasi.
- Waktu data sumber terakhir diperbarui, jika dapat diketahui.
- Versi definisi metrik.
- Identitas kandidat yang dipilih.
- Alasan pemilihan.
- Status publikasi.

Persyaratan:

- Snapshot baru dipublikasikan hanya setelah validasi berhasil.
- Kegagalan kalkulasi tidak boleh menimpa snapshot valid secara tidak sengaja.
- Cegah duplikasi proses kalkulasi bersamaan.
- Pastikan pembaruan ketiga card konsisten sebagai satu batch publikasi.
- Terapkan retention policy.
- Jangan menyimpan informasi sensitif yang tidak diperlukan oleh landing page.
- Jika perlu tabel baru, siapkan migrasi terkontrol dan dokumentasikan sebelum menerapkannya.

Gunakan mekanisme cache yang sesuai dengan infrastruktur yang telah tersedia. Jangan menambahkan dependency baru tanpa alasan yang jelas.

## 10. Tahap Keenam — Scheduler dan Pembaruan Otomatis

Implementasikan pembaruan berkala berdasarkan kebutuhan data sumber.

Scheduler harus:

1. Menentukan domain yang perlu diperbarui.
2. Mengidentifikasi metrik yang relevan.
3. Menjalankan query sesuai dependency.
4. Memvalidasi hasil.
5. Menghitung tren dan anomali.
6. Membentuk kandidat insight.
7. Melakukan ranking.
8. Membuat snapshot baru.
9. Mempublikasikan snapshot secara atomik.
10. Mencatat hasil eksekusi dan error.

Persyaratan tambahan:

- Interval dapat dikonfigurasi.
- Scheduler tidak menjalankan proses yang sama secara bersamaan.
- Retry menggunakan batas yang wajar.
- Kegagalan satu domain tidak boleh merusak hasil valid domain lain.
- Pembaruan tidak boleh membebani database operasional secara berlebihan.
- Gunakan pemicu berbasis perubahan data hanya jika sumber perubahan dapat dipercaya.
- Jangan mengklaim real-time jika sumber data tidak diperbarui secara real-time.

Pilih mekanisme scheduler yang kompatibel dengan infrastruktur saat ini. Dokumentasikan perilaku scheduler ketika aplikasi restart dan ketika terdapat lebih dari satu worker FastAPI.

## 11. Tahap Ketujuh — API Landing Page

Sediakan endpoint baca-saja, misalnya:

`GET /api/public/landing-insights`

Sesuaikan prefix, versi, dan konvensi routing dengan API yang sudah ada.

Endpoint mengembalikan maksimal tiga card, satu per domain, dengan struktur data terstandar. Contoh kontrak ilustratif:

```json
{
  "generated_at": "2026-10-13T00:00:00+07:00",
  "status": "ok",
  "cards": [
    {
      "domain": "production",
      "title": "Judul dari template tervalidasi",
      "metric_label": "Label metrik",
      "value": 0,
      "unit": "unit",
      "change_percent": null,
      "summary": "Ringkasan deterministik",
      "period": {
        "start": "2026-10-01",
        "end": "2026-10-12"
      },
      "calculated_at": "2026-10-13T00:00:00+07:00",
      "freshness": "fresh",
      "status": "valid"
    }
  ]
}
```

Nilai tanggal dan angka di atas hanya ilustrasi format kontrak, bukan hasil database aktual. Jangan menggunakan angka contoh ini sebagai data produksi.

Kontrak akhir harus disesuaikan dengan skema aktual dan kebutuhan frontend.

Persyaratan API:

- Read-only.
- Response ringan.
- Tidak menjalankan query berat pada setiap request.
- Menyediakan status freshness dan waktu kalkulasi.
- Menangani kondisi kosong dan error dengan jelas.
- Tidak mengungkap nama tabel internal, SQL, kredensial, atau detail error database kepada publik.
- Tidak mengembalikan informasi operasional sensitif.
- Menerapkan rate limiting atau perlindungan yang sesuai dengan pola trafik aplikasi.
- Menggunakan cache HTTP secara tepat tanpa menyebabkan data kedaluwarsa ditampilkan sebagai data terkini.

## 12. Tahap Kedelapan — Integrasi Frontend

Integrasikan endpoint ke tiga card landing page yang sudah ada.

Jangan melakukan redesign landing page di luar kebutuhan integrasi data.

Frontend harus:

- Mengambil insight dari API.
- Memetakan setiap domain ke card yang benar.
- Menampilkan nilai dan satuan dengan format yang sesuai.
- Menampilkan perubahan periode jika valid.
- Menampilkan periode dan waktu kalkulasi.
- Menunjukkan status data yang belum diperbarui.
- Memiliki loading state, error state, dan empty state.
- Memperbarui data secara berkala dengan interval yang dapat dikonfigurasi.
- Menghindari request berulang ketika halaman tidak aktif.
- Menghentikan atau mengurangi polling ketika tab tidak terlihat.
- Menangani kegagalan jaringan tanpa menghapus tampilan valid yang masih tersedia.
- Menghindari animasi atau pergantian konten yang mengganggu pembacaan.
- Menghormati preferensi reduced motion.

Konten hanya boleh diperbarui setelah data baru diterima dan lolos validasi frontend yang diperlukan.

## 13. Tahap Kesembilan — Keamanan dan Kinerja

Terapkan prinsip berikut:

- Hak akses database minimum.
- Parameterized queries.
- Allowlist untuk tabel, kolom, metrik, dan operasi yang diizinkan.
- Validasi parameter waktu dan wilayah.
- Batas waktu query.
- Pembatasan ukuran hasil.
- Indeks berdasarkan pola query aktual.
- Penghindaran full table scan yang tidak perlu.
- Audit log untuk proses kalkulasi dan publikasi.
- Tidak menampilkan data sensitif ke endpoint publik.
- Tidak mengungkap detail exception internal.
- Tidak menjalankan query atau kalkulasi berat dari browser.
- Tidak mengandalkan LLM pada seluruh jalur landing page.

Gunakan `EXPLAIN` atau metode evaluasi query yang sesuai untuk memeriksa rencana eksekusi query penting sebelum deployment.

## 14. Tahap Kesepuluh — Pengujian

Buat unit test dan integration test untuk skenario berikut:

### Data dan perhitungan

- Data lengkap dan valid.
- Data kosong.
- Nilai nol.
- Denominator nol.
- Data duplikat akibat join.
- Periode tidak lengkap.
- Perubahan positif dan negatif.
- Perubahan yang tidak signifikan.
- Data terlambat atau kedaluwarsa.
- Data historis tidak cukup.
- Perubahan definisi metrik.

### Insight ranking

- Kandidat dengan prioritas berbeda.
- Kandidat dengan severity tinggi tetapi confidence rendah.
- Tidak ada kandidat yang memenuhi syarat.
- Kandidat duplikat atau repetitif.
- Satu kandidat terbaik per domain.
- Ketiga card tetap mewakili domain berbeda.

### Scheduler dan snapshot

- Kalkulasi berhasil.
- Kalkulasi gagal.
- Retry.
- Proses bersamaan.
- Restart aplikasi.
- Publikasi atomik.
- Snapshot lama tetap tersedia saat pembaruan gagal.

### API dan frontend

- Response valid.
- Data kosong.
- Timeout.
- Cache.
- Polling.
- Data kedaluwarsa.
- Error API.
- Tidak ada kebocoran data sensitif.

Bandingkan hasil engine dengan query referensi yang telah diverifikasi untuk memastikan perhitungan benar.

## 15. Observability dan Audit

Sediakan log terstruktur yang sekurang-kurangnya merekam:

- Waktu mulai dan selesai.
- Domain dan metrik yang diproses.
- Versi definisi metrik.
- Durasi query.
- Jumlah baris hasil.
- Status validasi.
- Jumlah kandidat yang dibuat.
- Kandidat yang dipilih dan alasan ranking.
- Status publikasi snapshot.
- Error dan jumlah retry.

Jangan memasukkan kredensial, data pribadi, atau isi data operasional sensitif ke log.

## 16. Kriteria Penerimaan

Implementasi dinyatakan selesai jika:

1. Ketiga card memperoleh data dari database internal.
2. Tidak ada LLM atau model bahasa yang dipanggil untuk membentuk insight.
3. Ketiga domain memiliki katalog metrik dan aturan yang jelas.
4. Query planner hanya menjalankan query yang diizinkan.
5. Perhitungan dan perbandingan periode telah diuji.
6. Kandidat insight dipilih melalui ranking deterministik.
7. Teks card berasal dari template.
8. Pembaruan otomatis berfungsi.
9. Snapshot tetap konsisten ketika terjadi kegagalan.
10. Landing page tidak mengeksekusi query analitik berat pada setiap kunjungan.
11. Waktu kalkulasi dan status freshness ditampilkan.
12. Tidak ada data sensitif yang bocor ke endpoint publik.
13. Tidak ada regresi pada dashboard internal atau modul lain.
14. Pengujian utama berhasil.
15. Dokumentasi arsitektur, konfigurasi, metrik, dan deployment tersedia.

## 17. Cara Kerja Coding Agent

Lakukan pekerjaan secara bertahap.

**Tahap A — Audit**

Periksa repository, database, API, Business Data Engine, dan frontend. Laporkan temuan serta modul yang dapat digunakan kembali.

**Tahap B — Rancangan**

Buat arsitektur implementasi, katalog metrik awal, daftar query yang dibutuhkan, rancangan snapshot, kontrak API, aturan ranking, dan rencana pengujian.

**Tahap C — Implementasi**

Implementasikan modul secara inkremental. Gunakan kembali komponen yang sudah ada. Jangan mengubah file yang tidak relevan.

**Tahap D — Verifikasi**

Jalankan pengujian, periksa query, evaluasi kinerja, dan pastikan tiga card memperoleh hasil yang dapat ditelusuri ke sumber data.

**Tahap E — Dokumentasi**

Dokumentasikan cara kerja engine, konfigurasi scheduler, definisi metrik, aturan ranking, endpoint API, cara deployment, serta prosedur pemulihan jika pembaruan gagal.

Jangan mengarang hasil audit, hasil query, nama tabel, atau status pengujian. Laporkan secara eksplisit apabila ada komponen yang belum dapat diverifikasi.

Jangan menjalankan migrasi, mengubah konfigurasi produksi, menghapus data, atau melakukan deployment produksi tanpa persetujuan eksplisit.

## 18. Output yang Harus Diserahkan

Setelah implementasi, serahkan:

1. Ringkasan audit kondisi proyek sebelum perubahan.
2. Diagram arsitektur final.
3. Daftar file yang dibuat atau diubah.
4. Katalog metrik yang benar-benar didukung database.
5. Daftar query dan aturan perhitungan.
6. Mekanisme ranking dan fallback.
7. Kontrak API final.
8. Hasil pengujian dan hasil evaluasi kinerja.
9. Dokumentasi konfigurasi dan deployment.
10. Daftar keterbatasan atau metrik yang belum dapat diaktifkan.

**Prinsip akhir:** database menjadi sumber fakta, Business Data Engine menghitung, Insight Engine mendeteksi dan memilih temuan, template membentuk teks, dan landing page menampilkan hasilnya. Seluruh proses harus deterministik, dapat diaudit, hemat resource, dan tidak menggunakan LLM.