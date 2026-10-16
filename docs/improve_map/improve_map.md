# TASK: Migrasi Rendering Polygon SIMOGE HUD dari GeoJSON ke Vector Tiles

## 1. Peran dan Tujuan

Bertindak sebagai Senior GIS Engineer, Geospatial Backend Engineer, dan Performance Engineer yang bertanggung jawab meningkatkan performa peta pada proyek SIMOGE HUD.

Masalah utama saat ini adalah peta menjadi tidak responsif ketika menampilkan banyak polygon dan koordinat pin point, terutama saat rendering, zoom, pan, dan interaksi dengan fitur peta.

Tujuan utama adalah memigrasikan jalur rendering polygon dari GeoJSON besar ke Vector Tiles dengan pendekatan yang terukur, aman, dan kompatibel dengan arsitektur SIMOGE HUD yang sudah berjalan.

Jangan mengasumsikan bahwa seluruh bottleneck berasal dari rendering. Lakukan profiling untuk membedakan biaya pengambilan data, parsing JSON, pemrosesan geometri, rendering, dan interaksi pengguna.

## 2. Konteks Sistem yang Harus Dipertahankan

SIMOGE HUD merupakan dashboard Business Intelligence untuk kebutuhan operasional PT Perhutani.

Arsitektur aplikasi saat ini menggunakan:

- Backend Python/FastAPI.
- Database MariaDB.
- Frontend web yang memiliki autentikasi dan session management.
- MapLibre GL JS atau library peta yang sudah digunakan dalam implementasi aktual.
- Data polygon petak yang tersimpan pada tabel khusus `petak_polygon`.
- Data operasional yang menggunakan `kode_evapot` sebagai kunci pencocokan logis.

### Struktur data polygon

Tabel `petak_polygon` memiliki kolom `polygon` yang menyimpan data dalam format GeoJSON.

Hubungan polygon dengan tabel operasional dilakukan melalui `kode_evapot`, tanpa foreign key fisik.

Informasi penting:

- `kode_evapot` unik secara global.
- `polygon` merupakan GeoJSON, bukan kolom geometri spasial MariaDB yang sudah terverifikasi.
- Atribut wilayah mencakup `divre`, `kph`, `bkph`, dan `rph`, dengan nama dan tipe aktual yang harus diverifikasi dari skema database.
- `kode_data` dan atribut lainnya hanya boleh digunakan sesuai makna serta keunikan aktualnya.
- Data polygon merupakan sumber geometri utama.
- Tabel operasional harus tetap menjadi sumber data bisnis yang otoritatif.

Jangan mengubah relasi logis yang sudah berjalan. Jangan menambahkan foreign key, mengubah skema produksi, atau memigrasikan database ke PostGIS tanpa justifikasi teknis dan persetujuan terpisah.

## 3. Aturan Keselamatan dan Batasan Perubahan

Sebelum mengubah kode:

1. Audit struktur proyek, entry point, backend API, frontend map initialization, sumber data GeoJSON, layer polygon, layer pin, autentikasi, dan filter wilayah.
2. Identifikasi seluruh file yang terlibat serta dependensi antar-komponen.
3. Cari semua pemanggilan API dan fungsi yang menggunakan `petak_polygon`, `kode_evapot`, atau source/layer peta terkait.
4. Catat perilaku yang harus dipertahankan.
5. Buat baseline performa dan rencana rollback.

Ketentuan wajib:

- Jangan mengubah atau menghapus fitur peta yang sudah ada tanpa analisis dampak.
- Jangan melakukan refactor besar yang tidak diperlukan untuk migrasi.
- Jangan mengubah aturan bisnis, filter wilayah, autentikasi, session management, atau hak akses secara implisit.
- Jangan menulis ulang keseluruhan modul peta jika perubahan lokal sudah memadai.
- Jangan menimpa tileset aktif sebelum tileset baru lolos validasi.
- Jangan mengubah atau menghapus data GeoJSON sumber.
- Jangan menaruh kredensial, token sesi, atau rahasia autentikasi di tileset maupun source code frontend.
- Jangan menganggap filter frontend sebagai mekanisme otorisasi.
- Jangan mengklaim peningkatan performa tanpa hasil pengukuran.
- Jika informasi penting belum diketahui, lakukan inspeksi kode dan konfigurasi terlebih dahulu. Jangan menebak nama kolom, endpoint, file, atau fungsi.

Lakukan perubahan secara bertahap dan pertahankan jalur rollback ke implementasi sebelumnya.

## 4. Tahap I — Audit dan Profiling

Periksa implementasi peta yang sebenarnya sebelum memilih pendekatan final.

### Audit frontend

Identifikasi:

- Library peta dan versinya.
- Proses inisialisasi peta.
- Sumber GeoJSON polygon.
- Jumlah source dan layer.
- Penggunaan `setData()` dan frekuensi pembaruan data.
- Penggunaan marker HTML atau layer titik WebGL.
- Mekanisme filter wilayah dan filter tahun.
- Event handler untuk klik polygon dan pin.
- Proses pemuatan data ketika zoom atau pan.
- Kemungkinan pemrosesan berulang di main thread.
- Cache browser dan perilaku pemuatan ulang source.

### Audit backend dan database

Identifikasi:

- Endpoint yang mengirimkan GeoJSON.
- Query yang membaca `petak_polygon`.
- Format aktual kolom `polygon`.
- Jumlah polygon dan distribusi jumlah vertex.
- Ukuran payload JSON.
- Jumlah pin point yang ditampilkan.
- Filter wilayah yang diterapkan pada backend.
- Sumber otoritatif hak akses pengguna.
- Frekuensi perubahan geometri polygon.
- Mekanisme update dan invalidasi cache yang sudah tersedia.

### Baseline performa

Ukur setidaknya:

- Ukuran respons GeoJSON.
- Waktu request backend.
- Waktu parsing dan pemrosesan data.
- Waktu hingga layer pertama tampil.
- Frame rate saat zoom dan pan.
- Waktu respons klik polygon.
- Penggunaan memori browser.
- Performa ketika polygon dan pin ditampilkan bersama.

Pisahkan bottleneck yang terbukti dari dugaan.

Hasilkan laporan audit sebelum menentukan desain final.

## 5. Tahap II — Rancang Pipeline GeoJSON ke Vector Tiles

Gunakan pipeline terpisah dari request interaktif dashboard agar pembuatan tileset tidak membebani API utama.

Arsitektur awal yang perlu dievaluasi:

`MariaDB → GeoJSON Exporter → Geometry Validation → Tippecanoe → MBTiles → PMTiles → Authorized Delivery → MapLibre`

### 5.1 GeoJSON exporter

Buat exporter yang membaca data dari `petak_polygon` secara bertahap.

Exporter harus:

- Membaca kolom yang benar berdasarkan skema aktual.
- Memvalidasi JSON dan tipe geometri yang didukung.
- Memastikan `kode_evapot` tidak kosong dan tidak duplikat.
- Mempertahankan `kode_evapot` sebagai atribut identifikasi polygon.
- Menyertakan atribut wilayah minimum yang diperlukan.
- Menghindari pemuatan seluruh dataset ke RAM jika ukurannya besar.
- Menghasilkan laporan fitur berhasil, gagal, dan duplikat.
- Menggunakan konsistensi snapshot atau mekanisme yang mencegah hasil ekspor mencampur data dari waktu yang berbeda.

Jangan memperbaiki geometri sumber secara otomatis tanpa laporan dan aturan yang eksplisit.

### 5.2 Geometry validation

Validasi:

- Struktur GeoJSON.
- Tipe geometri.
- Koordinat dan sistem referensi koordinat.
- Geometri kosong atau rusak.
- Polygon dengan jumlah vertex sangat besar.
- Keunikan dan kelengkapan `kode_evapot`.

Jangan menganggap semua geometri berbentuk `Polygon`; periksa apakah `MultiPolygon` juga ada.

Jika ditemukan masalah, catat dan pisahkan dari proses build sampai penanganannya ditentukan.

### 5.3 Pembuatan tileset

Evaluasi Tippecanoe untuk menghasilkan MBTiles dari GeoJSON dan PMTiles CLI untuk konversi ke PMTiles.

Tentukan berdasarkan hasil audit:

- Zoom minimum dan maksimum.
- Layer name di dalam tileset.
- Atribut yang perlu dipertahankan.
- Strategi simplifikasi geometri.
- Batas ukuran tile.
- Kebijakan penanganan fitur kompleks.
- Validasi kelengkapan polygon pada zoom detail.

Jangan menggunakan opsi yang membuang fitur secara diam-diam hanya demi mengecilkan ukuran tile.

Gunakan `kode_evapot` sebagai atribut identifikasi yang stabil. Pastikan nilainya tetap tersedia setelah konversi.

Sebelum memilih PMTiles sebagai mekanisme distribusi final, pastikan kebutuhan otorisasi wilayah dan pola akses tile dapat dipenuhi dengan aman.

## 6. Tahap III — Otorisasi Wilayah Berdasarkan User Login

Ini merupakan persyaratan keamanan wajib.

Hak akses harus ditentukan berdasarkan identitas pengguna yang telah diautentikasi dan aturan otorisasi wilayah yang benar-benar digunakan oleh SIMOGE HUD.

Jangan menebak atau membuat ulang hierarki hak akses. Temukan implementasi yang sudah ada dan gunakan sumber kebenaran yang sama.

### Persyaratan

- Backend menentukan wilayah yang boleh diakses pengguna.
- Frontend tidak boleh menentukan hak akses hanya melalui parameter wilayah.
- Endpoint detail petak harus memvalidasi hak akses, meskipun pengguna memiliki `kode_evapot`.
- Pengguna tidak boleh memperoleh polygon di luar cakupannya melalui URL tile, query parameter, atau endpoint alternatif.
- Cache tidak boleh membocorkan data antar-cakupan akses.
- Perubahan hak akses harus segera diterapkan sesuai mekanisme session dan otorisasi yang berlaku.
- Tileset tidak boleh mengandung atribut sensitif yang tidak diperlukan untuk rendering.

Evaluasi dua strategi:

**Strategi A — PMTiles per cakupan akses**

Gunakan jika cakupan wilayah relatif stabil dan jumlah tileset masih dapat dikelola. Simpan tileset secara privat dan pastikan akses ke seluruh tile dalam arsip dibatasi dengan benar.

**Strategi B — Authorized Tile API**

Gunakan jika hak akses bersifat dinamis, berbeda antar-user, atau tidak cocok dengan pembagian tileset statis.

Jika menggunakan PMTiles melalui HTTP Range Requests, pastikan mekanisme autentikasi, otorisasi, caching, dan akses parsial berkas tetap aman. Jangan menganggap URL yang sulit ditebak sebagai proteksi.

Pilih strategi berdasarkan implementasi autentikasi dan hak akses aktual, lalu dokumentasikan alasan pemilihan.

## 7. Tahap IV — Integrasi MapLibre

Jika aplikasi sudah menggunakan MapLibre GL JS, pertahankan inisialisasi peta dan integrasikan vector source secara lokal.

Jangan mengganti library peta hanya untuk menjalankan migrasi ini.

Integrasi harus mempertahankan:

- Basemap dan konfigurasi peta.
- Center, zoom, dan viewport.
- Filter wilayah.
- Filter tahun.
- Style dan warna polygon.
- Klik polygon dan pembukaan panel detail.
- Layer koordinat aktivitas dan pin.
- Legend, tooltip, popup, serta kontrol peta.
- Loading state dan error handling.
- Perilaku responsive dashboard.

Jika PMTiles dipilih, gunakan versi paket `pmtiles` yang kompatibel dengan MapLibre yang terpasang. Daftarkan protokol satu kali, bukan berulang kali setiap peta dibuat.

Pastikan URL tileset berasal dari backend yang telah memeriksa otorisasi.

### Pemilihan polygon

Ketika polygon diklik:

1. Ambil `kode_evapot` dari properti fitur.
2. Validasi keberadaan nilainya.
3. Panggil endpoint detail yang sesuai dengan implementasi aktual.
4. Validasi otorisasi kembali pada backend.
5. Tampilkan detail di panel yang sudah ada.
6. Jangan mengirim seluruh geometri polygon jika hanya ID yang diperlukan.

Jika `kode_evapot` tidak tersedia pada feature hasil query tile, perbaiki proses ekspor atau konfigurasi atribut tileset.

Jangan membuat endpoint baru jika endpoint yang ada dapat digunakan dengan aman dan efisien.

## 8. Tahap V — Optimasi Koordinat Pin Point

Polygon dan pin harus diperlakukan sebagai sumber data terpisah.

Audit apakah pin saat ini dibuat sebagai elemen HTML/DOM atau dirender melalui source dan layer MapLibre.

Jika jumlah titik besar:

- Prioritaskan layer titik WebGL.
- Gunakan clustering ketika sesuai dengan kebutuhan visual.
- Terapkan filter viewport atau tile-based loading jika diperlukan.
- Jangan memuat detail lengkap setiap pin sebelum diperlukan.
- Pertahankan interaksi klik dan identifikasi objek.
- Jangan menggabungkan seluruh koordinat aktivitas ke dalam GeoJSON polygon.
- Jangan menghilangkan titik yang penting bagi kebutuhan operasional tanpa persetujuan.

Optimasi polygon tidak otomatis menyelesaikan bottleneck pin point. Ukur dan optimalkan keduanya secara independen.

## 9. Tahap VI — Strategi Pembaruan Data

Buat pipeline versioned build yang tidak menimpa tileset aktif selama proses pembuatan.

Alur:

1. Deteksi perubahan geometri yang relevan.
2. Ekspor data secara konsisten.
3. Validasi hasil ekspor.
4. Bangun tileset baru.
5. Validasi metadata, kelengkapan ID, geometri, dan ukuran tile.
6. Jalankan pengujian fungsional.
7. Publikasikan versi baru secara atomik.
8. Perbarui referensi tileset.
9. Invalidasi cache sesuai versi.
10. Simpan versi sebelumnya untuk rollback.

Bedakan perubahan geometri dari perubahan atribut bisnis yang tidak memengaruhi polygon.

Jika frekuensi perubahan geometri rendah, pertimbangkan build terjadwal. Jika perubahan harus segera terlihat, rancang mekanisme pemicu rebuild dan tentukan batas waktu pembaruan yang realistis.

Jangan membangun ulang seluruh tileset pada setiap request pengguna.

## 10. Tahap VII — Benchmark dan Kriteria Penerimaan

Bandingkan implementasi GeoJSON lama dengan vector tiles pada dataset dan perangkat yang sama.

Ukur:

- Ukuran data yang ditransfer.
- Waktu hingga polygon terlihat.
- Waktu pemrosesan di frontend.
- Frame rate saat zoom dan pan.
- Waktu klik polygon sampai detail tampil.
- Penggunaan CPU dan memori.
- Jumlah request dan error.
- Performa saat polygon dan pin aktif bersama.

Gunakan target awal berikut sebagai sasaran pengujian, bukan jaminan:

- Interaksi peta diupayakan merespons dalam kurang dari 100 ms.
- Rendering saat zoom dan pan mendekati 60 FPS pada perangkat uji yang memadai.
- Layer utama tampil dalam kurang dari 2 detik pada kondisi jaringan dan cache yang ditentukan.
- Tidak ada kehilangan polygon pada zoom operasional yang diwajibkan.
- Tidak ada akses lintas wilayah yang tidak diotorisasi.
- Klik polygon tetap membuka detail yang benar.

Catat kondisi pengujian, ukuran dataset, perangkat, jaringan, dan status cache. Jika target tidak tercapai, jelaskan bottleneck yang tersisa.

## 11. Pengujian Regresi

Sebelum rollout, verifikasi:

- Semua filter wilayah tetap bekerja.
- Filter tahun tetap bekerja.
- Jumlah dan identitas polygon sesuai sumber.
- `kode_evapot` selalu mengarah ke detail yang benar.
- Tidak ada duplikasi polygon akibat source lama dan baru aktif bersamaan.
- Layer pin tidak rusak.
- Panel detail tidak kehilangan fungsionalitas.
- Session dan login tetap bekerja.
- Akses tileset mengikuti otorisasi wilayah.
- Cache tidak menampilkan data lintas pengguna.
- Rollback mengembalikan versi tileset dan konfigurasi yang valid.

Lakukan rollout terbatas pada satu cakupan wilayah terlebih dahulu. Pertahankan jalur GeoJSON lama sampai hasil migrasi memenuhi kriteria penerimaan.

## 12. Dokumentasi dan Hasil Kerja

Hasil kerja wajib mencakup:

1. Laporan audit arsitektur peta saat ini.
2. Identifikasi bottleneck berdasarkan pengukuran.
3. Diagram arsitektur target.
4. Daftar file yang akan diubah beserta alasan perubahan.
5. Desain pipeline ekspor dan pembuatan tileset.
6. Desain otorisasi wilayah.
7. Implementasi exporter dan build script yang diperlukan.
8. Integrasi MapLibre.
9. Strategi pembaruan dan rollback.
10. Hasil benchmark sebelum dan sesudah.
11. Hasil pengujian regresi.
12. Instruksi deployment dan pemeliharaan.

Bedakan dengan jelas implementasi yang sudah selesai, yang sudah diuji, yang baru dirancang, dan yang masih memerlukan keputusan.

## 13. Instruksi Pelaksanaan

Mulai dengan audit read-only terhadap proyek yang ada.

Setelah audit, berikan ringkasan:

- Arsitektur peta saat ini.
- Bottleneck yang telah dibuktikan.
- File dan fungsi yang terlibat.
- Strategi tile yang paling sesuai.
- Risiko keamanan dan kompatibilitas.
- Tahapan implementasi yang disarankan.

Setelah itu, implementasikan secara bertahap dengan perubahan sekecil mungkin.

Jangan mengklaim tugas selesai hanya karena tileset berhasil dibuat. Migrasi baru dianggap selesai setelah rendering, pemilihan polygon, filter wilayah, otorisasi, pembaruan data, dan pengujian performa berhasil diverifikasi.

**Prinsip utama: optimalkan jalur rendering spasial tanpa merusak sumber data, aturan bisnis, keamanan akses, maupun fitur SIMOGE HUD yang sudah berjalan.**