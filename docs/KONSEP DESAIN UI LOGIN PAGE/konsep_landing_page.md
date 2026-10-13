# SIMOGE HUD — Design Concept

**Project:** SIMOGE HUD  
**Organization:** PT Perhutani  
**Document Type:** UI/UX Design Concept  
**Status:** Design Direction  
**Version:** 1.0

---

## 1. Ringkasan Konsep

SIMOGE HUD dirancang sebagai *modern editorial landing page* dengan karakter **Forest-Tech**: profesional, minimalis, modern, dan merepresentasikan identitas kehutanan Perhutani.

Antarmuka tidak mengikuti pola dashboard konvensional yang dipenuhi panel, kartu statistik, dan widget. Sebaliknya, desain mengutamakan tipografi, ruang kosong, visual lanskap hutan, navigasi editorial, serta business insight yang disajikan secara ringkas.

Halaman berfungsi sebagai pintu masuk menuju ekosistem informasi SIMOGE HUD, autentikasi pengguna, konten informasi, dan wawasan bisnis kehutanan.

### Prinsip utama

- **Minimalist:** hanya elemen yang memiliki tujuan jelas.
- **Professional:** sesuai dengan lingkungan kerja perusahaan.
- **Editorial:** konten dan informasi menjadi bagian penting dari pengalaman halaman.
- **Forest-Tech:** menggabungkan identitas kehutanan dengan teknologi modern.
- **Performance-first:** animasi, visual, dan audio tidak boleh mengganggu fungsi bisnis.
- **Scalable:** mendukung perluasan cakupan data dari satu wilayah ke seluruh DIVRE.

---

## 2. Arah Visual

### 2.1 Gaya desain

Menggunakan pendekatan *Modern Editorial × Forest-Tech*, bukan *Futuristic Command Center* yang padat dan penuh efek visual.

Karakter visual yang diinginkan:

- Tipografi besar dengan hierarki yang tegas.
- Ruang kosong yang cukup untuk meningkatkan keterbacaan.
- Lanskap hutan sebagai visual utama yang subtil.
- Elemen antarmuka sederhana dengan garis dan batas yang minimal.
- Animasi atmosferik yang halus dan tidak berlebihan.
- Identitas Perhutani yang terasa alami, bukan sekadar dekorasi logo.

### 2.2 Palet warna

| Elemen | Arah warna | Fungsi |
|---|---|---|
| Background utama | Warm White | Memberikan kesan bersih dan lapang |
| Primary | Forest Green | Identitas utama dan elemen penting |
| Accent | Teal | Aksen teknologi, indikator, dan interaksi |
| Secondary | Sage Green | Permukaan sekunder dan elemen pendukung |
| Text Primary | Charcoal | Teks utama dengan kontras yang baik |
| Text Secondary | Muted Grey | Metadata dan informasi pendukung |
| Border | Soft Grey | Pemisah elemen yang tidak dominan |

Warna final ditetapkan dalam design tokens agar konsisten di seluruh halaman dan komponen.

---

## 3. Struktur Halaman

### 3.1 Header dan navigasi editorial

Navigasi disusun secara ringkas dan tidak menyerupai sidebar dashboard.

Menu yang harus tersedia:

- **START** — halaman awal dan titik masuk utama.
- **NEWS** — berita dan informasi perusahaan.
- **FEED** — aliran informasi terbaru.
- **FOR YOU** — konten yang relevan bagi pengguna.
- **FOLLOWING** — konten dari kanal atau sumber yang diikuti.
- **CHANNELS** — pengelompokan konten berdasarkan topik atau bidang.
- **PUBLISHER** — sumber atau penerbit informasi.

Navigasi harus tetap mudah dipahami pada desktop maupun perangkat dengan layar lebih kecil.

### 3.2 Hero section

Hero section menjadi fokus visual pertama saat halaman dibuka.

Elemen utama:

- Identitas SIMOGE HUD dan Perhutani.
- Headline dengan tipografi yang kuat.
- Deskripsi singkat mengenai platform.
- Lanskap hutan sebagai visual latar atau elemen ilustratif.
- Card autentikasi yang sederhana dan terintegrasi dengan layout.

Hero tidak boleh dipenuhi statistik, panel, atau ornamen futuristik yang tidak mendukung tujuan halaman.

### 3.3 Authentication card

Login ditampilkan sebagai satu card autentikasi yang bersih, dengan ukuran proporsional dan tidak menutupi seluruh halaman.

Komponen:

- Input identitas pengguna sesuai mekanisme autentikasi yang tersedia.
- Input kata sandi.
- Kontrol tampil/sembunyikan kata sandi.
- Tombol login utama.
- Indikator proses autentikasi.
- Pesan validasi dan kegagalan yang jelas.
- Opsi pemulihan akses jika didukung oleh sistem.

Autentikasi harus tetap berfungsi dengan benar tanpa ketergantungan pada animasi atau audio.

### 3.4 Business insight

Business insight merupakan elemen sekunder yang mendukung konteks bisnis, bukan menjadi pusat perhatian landing page.

Komponen yang direncanakan:

- Satu grafik mini.
- Beberapa indeks utama.
- Label dan periode pengukuran yang jelas.
- Indikator perubahan apabila tersedia.
- Keterangan sumber atau status data.

Insight dirancang agar dapat mendukung cakupan data seluruh DIVRE, tidak terikat pada satu wilayah saja.

**Aturan integritas data:**

1. Data aktual harus berasal dari sumber data yang sah.
2. Data contoh atau dummy wajib diberi label yang jelas.
3. Data yang belum tersedia tidak boleh ditampilkan sebagai fakta.
4. Periode, satuan, dan cakupan indeks harus dapat dipahami.
5. Definisi setiap indeks harus terdokumentasi sebelum dipakai sebagai indikator bisnis.
6. Perluasan cakupan DIVRE tidak boleh mengandalkan nilai yang di-hardcode untuk satu wilayah.

### 3.5 Area konten editorial

Area ini menjadi tempat penyajian berita, feed, kanal, dan informasi yang relevan.

Konten ditampilkan dengan pendekatan editorial:

- Judul yang jelas.
- Ringkasan singkat.
- Metadata seperlunya.
- Visual pendukung jika relevan.
- Hierarki berdasarkan kepentingan konten.

Tidak semua konten harus dimasukkan ke dalam card. Tata letak dapat memanfaatkan kolom, daftar editorial, atau blok konten sesuai kebutuhan.

---

## 4. Sistem Animasi

Animasi bertujuan membangun karakter visual yang hidup tanpa mengorbankan performa.

### Efek yang direncanakan

- **Subtle parallax:** pergerakan kecil pada lapisan visual lanskap.
- **Atmospheric gradient:** gradasi yang berubah perlahan.
- **Soft transitions:** transisi pada navigasi dan elemen interaktif.
- **Content reveal:** kemunculan konten secara halus.
- **Micro-interactions:** respons visual kecil pada tombol dan kontrol.

### Batasan implementasi

- Hindari animasi yang terus berjalan tanpa manfaat.
- Prioritaskan `transform` dan `opacity` untuk animasi yang lebih efisien.
- Hindari efek berat pada elemen besar atau seluruh halaman.
- Hentikan atau sederhanakan animasi ketika tab tidak aktif jika memungkinkan.
- Hormati preferensi `prefers-reduced-motion`.
- Animasi tidak boleh menghambat login, pemuatan konten, atau interaksi bisnis.

---

## 5. Sistem Backsound

### 5.1 Tujuan

Backsound digunakan sebagai elemen atmosferik opsional yang mendukung pengalaman visual. Audio bukan fitur utama dan tidak boleh mengganggu operasional bisnis.

### 5.2 Kebijakan pemutaran

Keputusan desain menggunakan pola **auto-download dan attempted autoplay**:

1. Halaman utama dan fungsi bisnis dimuat terlebih dahulu.
2. Pengunduhan audio dilakukan di latar belakang dengan prioritas rendah.
3. File audio disimpan pada cache browser setelah pengunduhan selesai.
4. Browser mencoba memutar audio secara otomatis setelah file siap.
5. Jika autoplay bersuara diblokir, audio menunggu interaksi pengguna.
6. Tombol ON/OFF tersedia untuk mengontrol pemutaran.
7. Ketika pengguna memilih OFF, audio dihentikan dan pemutaran otomatis tidak dicoba kembali selama sesi tersebut.
8. Hanya satu lagu yang boleh diputar pada satu waktu.

Autoplay bersuara tidak dapat dijamin karena kebijakan browser. Antarmuka harus menangani kondisi tersebut tanpa mengganggu pengguna.

### 5.3 Format dan optimasi audio

| Parameter | Rekomendasi awal |
|---|---|
| Format | MP3 |
| Bitrate | 64 kbps untuk audio atmosferik |
| Sample rate | 44,1 kHz |
| Pemutaran | HTML Audio API |
| Penyimpanan client | Cache Storage API |
| Autoplay | Dicoba setelah audio siap |
| Pengunduhan awal | Background, prioritas rendah |
| Pemrosesan backend | Tidak diperlukan |
| Layanan streaming | Tidak digunakan |

Bitrate dapat dinaikkan menjadi 96 kbps jika kualitas audio 64 kbps tidak memadai.

### 5.4 Manajemen aset audio

File backsound saat ini berada di direktori aset proyek:

`ui/assets/backsound`

Lokasi tersebut hanya menjadi lokasi aset pada lingkungan pengembangan. Implementasi tidak boleh menggunakan path absolut mesin pengembang, seperti `/home/bryankldr/PROYEK_2026/ana-hermes-dashboard/ui/assets/backsound`.

Ketentuan distribusi:

- Gunakan konfigurasi aset yang relatif terhadap root proyek.
- Sajikan audio sebagai file statis melalui infrastruktur web yang tersedia.
- Pastikan aset disertakan dalam proses build atau deployment.
- Gunakan versi cache yang dapat diperbarui ketika file audio berubah.
- Hindari mengunduh seluruh koleksi lagu sekaligus.
- Jangan melakukan decoding, transcoding, atau pemrosesan audio di backend produksi.

### 5.5 Prioritas performa

Urutan prioritas sistem:

1. Autentikasi dan keamanan.
2. API dan data bisnis.
3. Pemuatan konten utama.
4. Peta, laporan, dan komponen interaktif.
5. Visual tambahan dan animasi.
6. Backsound.

Jika koneksi atau sumber daya terbatas, backsound harus menjadi komponen pertama yang ditunda atau dinonaktifkan.

Cache browser tidak bersifat permanen dan dapat dihapus oleh browser. Karena itu, sistem harus dapat mengunduh ulang file apabila diperlukan.

---

## 6. Prinsip Arsitektur Teknis

### Frontend

Frontend bertanggung jawab atas:

- Rendering halaman dan navigasi.
- Interaksi autentikasi.
- Animasi visual.
- Rendering grafik mini dan indeks.
- Pengelolaan kontrol backsound.
- Pengunduhan dan penyimpanan cache audio di browser.

### Backend

Backend menggunakan Python 3 dan FastAPI sesuai arsitektur aplikasi yang ada.

Backend bertanggung jawab atas:

- Autentikasi dan validasi sesi.
- Penyediaan data bisnis.
- API konten dan business insight.
- Otorisasi akses berdasarkan pengguna dan cakupan kewenangan.
- Penyajian aset statis melalui mekanisme deployment yang sesuai.

Backend tidak perlu menjalankan layanan streaming atau memproses audio untuk fitur backsound ini.

### Data bisnis

Business insight harus menggunakan sumber data dan aturan bisnis yang terdefinisi. Frontend tidak boleh mengarang nilai indeks atau menghitung ulang indikator bisnis secara terpisah dari definisi resmi.

Cakupan lintas DIVRE harus menjadi bagian dari desain data, bukan sekadar pilihan tampilan.

---

## 7. Responsivitas dan Aksesibilitas

Desain harus beradaptasi terhadap:

- Desktop dan laptop sebagai lingkungan kerja utama.
- Tablet dan layar berukuran menengah.
- Perangkat dengan layar lebih kecil.

Ketentuan:

- Navigasi tidak boleh bertumpuk secara tidak teratur.
- Login harus tetap mudah digunakan.
- Teks memiliki kontras yang memadai.
- Semua kontrol interaktif dapat digunakan melalui keyboard.
- Fokus keyboard terlihat jelas.
- Kontrol audio memiliki label yang dapat dipahami.
- Animasi mengikuti preferensi pengurangan gerakan.
- Fungsi bisnis tetap dapat digunakan ketika audio gagal dimuat.

---

## 8. Prinsip Performa

SIMOGE HUD harus mengutamakan responsivitas dan stabilitas.

Strategi yang direncanakan:

- Memuat aset visual sesuai kebutuhan.
- Mengoptimalkan ukuran gambar dan audio.
- Menggunakan cache browser untuk aset statis.
- Menghindari dependensi frontend yang tidak diperlukan.
- Memisahkan proses bisnis dari efek visual.
- Menghindari pekerjaan CPU yang berat pada main thread.
- Menunda pengunduhan backsound sampai proses utama telah mendapatkan prioritas.
- Memastikan kegagalan audio tidak memengaruhi autentikasi atau dashboard.

---

## 9. Design System dan Reusability

Komponen visual harus menggunakan design tokens dan pola komponen yang konsisten.

Kelompok komponen:

- Typography.
- Color tokens.
- Spacing dan layout.
- Buttons dan form controls.
- Authentication card.
- Editorial navigation.
- Content list dan content card.
- Business insight dan mini chart.
- Status indicators.
- Audio control.
- Loading, empty, dan error states.

Komponen harus dapat digunakan ulang di halaman lain tanpa menduplikasi implementasi atau menetapkan warna dan ukuran secara terpisah di setiap halaman.

---

## 10. Kriteria Penerimaan Desain

Konsep dianggap siap diterjemahkan ke implementasi jika memenuhi kriteria berikut:

- [ ] Visual menggunakan gaya Modern Editorial × Forest-Tech.
- [ ] Layout memiliki ruang kosong yang memadai dan tidak menyerupai dashboard penuh panel.
- [ ] Identitas Perhutani tampil proporsional.
- [ ] Card login bersih, jelas, dan responsif.
- [ ] Semua menu editorial yang ditentukan tersedia.
- [ ] Business insight mendukung cakupan seluruh DIVRE.
- [ ] Data contoh dibedakan secara jelas dari data aktual.
- [ ] Animasi ringan dan mendukung aksesibilitas.
- [ ] Backsound otomatis diunduh dengan prioritas rendah.
- [ ] Autoplay dicoba dan kegagalan autoplay ditangani.
- [ ] Audio disimpan pada cache client setelah pengunduhan.
- [ ] Kontrol ON/OFF berfungsi.
- [ ] Tidak ada path absolut mesin pengembang di kode distribusi.
- [ ] Kegagalan audio tidak mengganggu fungsi bisnis.
- [ ] Aset statis dan cache dapat diperbarui ketika versi audio berubah.

---

## 11. Tahapan Implementasi

### Tahap 1 — Design foundation

Menetapkan palet warna, tipografi, spacing, grid, ikon, dan design tokens.

### Tahap 2 — Landing page

Membangun header, navigasi editorial, hero section, lanskap hutan, dan layout responsif.

### Tahap 3 — Authentication

Mengintegrasikan card login dengan sistem autentikasi dan sesi yang telah tersedia.

### Tahap 4 — Business insight

Menentukan definisi indeks, sumber data, cakupan DIVRE, periode pengukuran, dan status data contoh sebelum integrasi API.

### Tahap 5 — Motion dan interaksi

Mengimplementasikan parallax, transisi, dan micro-interactions dengan batasan performa.

### Tahap 6 — Audio cache

Mengimplementasikan pengunduhan bertahap, Cache Storage, attempted autoplay, kontrol ON/OFF, dan pembaruan cache berbasis versi.

### Tahap 7 — Validasi

Melakukan pengujian responsivitas, aksesibilitas, performa, autentikasi, data, cache, dan perilaku autoplay di browser yang didukung.

---

## 12. Prinsip Keputusan Akhir

SIMOGE HUD tidak perlu terlihat kompleks untuk terlihat canggih.

Nilai utamanya adalah antarmuka yang tenang, identitas kehutanan yang kuat, informasi bisnis yang dapat dipercaya, dan interaksi yang responsif. Setiap elemen visual maupun audio harus mendukung pengalaman tersebut tanpa mengurangi prioritas fungsi bisnis.

**Arah final:** Modern Editorial × Forest-Tech, dengan autentikasi sederhana, navigasi editorial, business insight lintas DIVRE, animasi ringan, dan backsound berbasis cache client dengan prioritas paling rendah.



## Batasan Ruang Lingkup Desain

### 1. Halaman yang Dicakup

Konsep **Modern Editorial × Forest-Tech** secara eksklusif berlaku untuk **public landing page SIMOGE HUD / ana-hermes-dashboard**, yaitu halaman yang ditampilkan sebelum pengguna berhasil login.

Ruang lingkupnya meliputi:

- Header dan navigasi editorial landing page.
- Hero section dengan visual lanskap hutan.
- Card autentikasi pengguna.
- Business insight ringkas sebagai informasi pendukung.
- Animasi atmosferik yang ringan.
- Kontrol backsound dan mekanisme cache audio client.
- Responsivitas serta aksesibilitas landing page.

### 2. Halaman yang Tidak Dicakup

Konsep ini tidak menjadi ketentuan desain untuk:

- Dashboard utama setelah login.
- Workspace atau antarmuka percakapan Anna.
- Panel grafik dan laporan.
- Spatial Map dan halaman pemetaan.
- Halaman administrasi dan pengelolaan pengguna.
- Halaman operasional, monitoring, dan analisis bisnis.
- Halaman internal lain yang memerlukan pola interaksi khusus.

Halaman-halaman tersebut tetap menggunakan kebutuhan, arsitektur informasi, komponen, dan design system yang sesuai dengan fungsi masing-masing.

### 3. Pemisahan Design System

Implementasi harus memisahkan gaya visual landing page dari aplikasi internal.

Ketentuan:

1. Komponen khusus landing page ditempatkan dalam lingkup komponen landing page.
2. Design tokens global yang memang digunakan bersama boleh digunakan lintas halaman, tetapi tidak boleh memaksakan gaya editorial pada dashboard internal.
3. Komponen autentikasi, navigasi editorial, visual lanskap, animasi, dan backsound tidak boleh otomatis diterapkan pada seluruh aplikasi.
4. Integrasi login menuju aplikasi internal harus mempertahankan mekanisme autentikasi, sesi, dan otorisasi yang sudah berlaku.
5. Perubahan landing page tidak boleh mengubah perilaku atau tampilan halaman internal di luar kebutuhan integrasi yang disepakati.

### 4. Kriteria Penerimaan Ruang Lingkup

- [ ] Gaya Modern Editorial × Forest-Tech hanya muncul pada landing page.
- [ ] Navigasi START, NEWS, FEED, FOR YOU, FOLLOWING, CHANNELS, dan PUBLISHER merupakan bagian dari landing page sesuai fungsi yang ditetapkan.
- [ ] Business insight landing page bersifat ringkas dan tidak menggantikan dashboard analitik.
- [ ] Backsound hanya menjadi fitur opsional landing page.
- [ ] Setelah login, pengguna masuk ke aplikasi internal sesuai alur yang sudah ditentukan.
- [ ] Dashboard, Anna, Spatial Map, panel laporan, dan halaman internal lainnya tidak mengalami perubahan desain yang tidak diminta.

**Prinsip utama:** landing page berfungsi sebagai gerbang masuk dan representasi visual SIMOGE HUD. Aplikasi setelah login tetap menjadi lingkungan kerja bisnis dengan kebutuhan desain dan interaksi tersendiri.
