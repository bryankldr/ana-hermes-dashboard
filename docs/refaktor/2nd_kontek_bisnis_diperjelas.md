Untuk konteks map, sebaiknya bisnis logic tidak ditampilkan sebagai daftar tabel mentah, tetapi diterjemahkan menjadi 4 domain evaluasi spasial. Struktur berikut bisa dijadikan acuan langsung untuk Hermes/Anna agar narasi dan visualisasi map konsisten dengan data sebenarnya.

1. Evaluasi Petak

Tujuan: menjawab apakah setiap petak sudah memiliki coverage penyadapan yang memadai dan bagaimana kondisi alokasi andilnya.

Map mengevaluasi setiap petak_polygon berdasarkan hubungan:

getah_petak → getah_andil → petak_polygon

dengan penghubung kode_evapot.

Indikator utama

Coverage penyadap

BONGKOR → petak tidak memiliki penyadap sama sekali.
IDLE → periode sebelumnya memiliki aktivitas, tetapi periode berjalan tidak memiliki aktivitas.
AKTIV → terdapat aktivitas penyadapan pada periode berjalan.

Efektivitas luas
Bandingkan:

total luas_andil pada petak
vs
luas_baku petak

Interpretasi:

Kondisi	Makna Map
Tidak ada penyadap	Petak membutuhkan penyadap
luas_andil < luas_baku	Coverage belum penuh
luas_andil ≈ luas_baku	Coverage sesuai
luas_andil > luas_baku	Coverage melebihi luas baku
Warna polygon efektivitas petak
🔴 Merah — tidak ada penyadap
🟡 Kuning — total luas_andil < luas_baku
🟢 Hijau — total luas_andil ≥ luas_baku

Jadi ketika operator melihat map, warna polygon menjawab pertanyaan: "Apakah petak ini sudah tertangani secara penyadapan?"

2. Evaluasi Aktivitas

Tujuan: melihat apakah aktivitas penyadapan benar-benar berlangsung pada petak dan andil yang dialokasikan.

Relasi utama:

getah_rencana_aktivitas
        │
        └── id_rencana
                ↓
       getah_aktivitas_sadap
                │
                └── id_penyadap
                        ↓
                  getah_penyadap
                        │
                        ↓
                    getah_andil
                        │
                        ↓
              kode_evapot → petak

Evaluasi aktivitas tidak hanya menghitung berapa aktivitas, tetapi melihat status operasional penyadapan secara spasial.

Status aktivitas

AKTIV

Ada aktivitas pada periode berjalan.

IDLE

Sebelumnya ada aktivitas.
Periode berjalan tidak ada aktivitas.

BONGKOR

Untuk andil: tidak terdapat aktivitas selama lebih dari 2 bulan.
Untuk petak: tidak terdapat penyadap sama sekali.

Perlu dibedakan:

Petak BONGKOR ≠ Andil BONGKOR.

Petak dapat memiliki penyadap pada sebagian andil, sementara sebagian andil lainnya sudah tidak aktif.

Informasi yang ditampilkan di map

Ketika polygon/petak dipilih:

PETAK 28 C3

Status       : AKTIV
Penyadap     : 8
Andil        : 12
Andil Aktif  : 10
Andil Idle   : 1
Andil Bongkor: 1

Aktivitas periode berjalan : 86
Aktivitas periode lalu     : 91

Dengan demikian Evaluasi Aktivitas menjawab:

"Apakah kegiatan penyadapan benar-benar berlangsung di wilayah ini, dan bagian mana yang mulai tidak aktif?"

3. Evaluasi Produksi

Tujuan: membandingkan produksi aktual dengan target produksi pada lokasi dan periode yang sama.

Ini merupakan hubungan:

Petak
  │
  ├── target_rkap
  │
  └── getah_target_ro_nps
          │
          ├── RO
          └── NPS

Aktivitas Penyadapan
          ↓
getah_aktivitas_penerimaan
          ↓
Produksi/Penerimaan
Target periode

getah_target_ro_nps menentukan persentase target berdasarkan:

tahun
bulan
ro_periode_1
ro_periode_2
nps_periode_1
nps_periode_2

Periode:

P1 = tanggal 1–15
P2 = tanggal 16–akhir bulan

Target kilogram:

Target Periode =
Persentase Target Periode × target_rkap Petak

Contoh:

Petak 28 C3
Target RKAP = 697,6 Kg

RO P1 Januari = 3,5%

Target RO P1
= 3,5% × 697,6
= 24,4 Kg
Evaluasi pencapaian
Pencapaian =
Penerimaan Aktual / Target Periode × 100%
Warna polygon pencapaian RKAP
Pencapaian	Warna
0–25%	🔴 Merah
26–50%	🟠 Oranye
51–75%	🟡 Kuning
76–100%	🟢 Hijau
>100%	🟨 Emas

Dengan demikian map dapat digunakan untuk menjawab:

"Petak mana yang sudah mencapai target dan petak mana yang tertinggal?"

Evaluasi produktivitas penyadap

Ini berbeda dengan sekadar melihat aktivitas.

Seorang penyadap dapat:

AKTIF
+
aktivitas banyak
+
produksi rendah

Artinya masalahnya bukan ketiadaan aktivitas, tetapi produktivitas.

Perhitungan dasarnya:

Proporsi luas andil
=
luas_andil / luas_baku_petak

Kemudian proporsi tersebut digunakan untuk memperoleh target yang relevan bagi penyadap/andil:

Target Penyadap/Andil
=
Target Periode Petak × Proporsi Luas Andil

Kemudian:

Produksi Aktual < Target

→ masuk kategori kurang produktif.

Jadi Anna tidak boleh menyimpulkan:

"Penyadap ini tidak aktif."

jika datanya menunjukkan aktivitas tinggi.

Narasi yang benar adalah:

"Penyadap aktif dengan aktivitas tinggi, tetapi penerimaan masih berada di bawah target proporsional berdasarkan luas andil."

4. Evaluasi Matrik

Tujuan: melihat keseimbangan antara luas, pohon, andil, penyadap, aktivitas, dan produksi.

Ini adalah evaluasi yang lebih diagnostik daripada sekadar status.

Matriks utama petak

Hubungkan:

GETAH_PETAK
│
├── luas_baku
├── jumlah_pohon
└── target_rkap
       │
       └─────────────┐
                     ↓
GETAH_ANDIL         EVALUASI
│
├── luas_andil
├── jml_pohon
└── id_penyadap
                     ↓
             AKTIVITAS
                     ↓
             PENERIMAAN
Matriks luas

Bandingkan:

luas_baku petak
        VS
Σ luas_andil

Untuk mengetahui:

coverage penyadapan;
kekurangan alokasi andil;
kelebihan alokasi;
petak yang membutuhkan tambahan penyadap.
Matriks pohon

Bandingkan:

jumlah_pohon petak
        VS
Σ jml_pohon andil

Ini memberikan pemeriksaan kedua terhadap distribusi andil.

Contohnya:

Petak 28 C3

Luas baku       : 10,0 Ha
Total luas andil: 8,5 Ha

Pohon petak     : 2.400
Pohon pada andil: 2.050

Map kemudian dapat menunjukkan bahwa masalahnya bukan hanya jumlah penyadap, tetapi coverage spasial andil terhadap potensi petak.

Struktur akhir Map untuk Anna

Saya sarankan Map memiliki empat mode evaluasi, bukan mencampurkan seluruh indikator sekaligus:

                    ┌──────────────────────┐
                    │     SPATIAL MAP      │
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
          ▼                    ▼                    ▼
   EVALUASI PETAK       EVALUASI AKTIVITAS   EVALUASI PRODUKSI
          │                    │                    │
     Coverage              Status              Target vs
     Penyadap              Aktivitas           Aktual
     Luas Andil            P1 / P2              RO / NPS
          │                    │                    │
          └────────────────────┼────────────────────┘
                               ▼
                       EVALUASI MATRIK
                               │
                   ┌───────────┼───────────┐
                   ▼           ▼           ▼
                 Luas        Pohon     Produktivitas
Filter global map

Semua mode sebaiknya mengikuti filter yang sama:

Tahun
Bulan
Periode
Divre
KPH
BKPH
RPH
TPG

Dengan aturan periode:

P1       → P1 bulan berjalan tahun berjalan
P2       → P2 bulan berjalan tahun berjalan

P1/P2 s.d.
→ seluruh P1/P2 sejak Januari
  sampai periode berjalan

s.d.
→ 1 Januari tahun berjalan
  sampai tanggal berjalan
Konsep terpenting untuk Anna

Anna sebaiknya memperlakukan map sebagai business intelligence layer, bukan sekadar peta.

Setiap polygon harus bisa menjawab empat pertanyaan:

Mode	Pertanyaan bisnis
Evaluasi Petak	Apakah petak sudah tertangani dan coverage penyadapannya memadai?
Evaluasi Aktivitas	Apakah penyadapan benar-benar berlangsung?
Evaluasi Produksi	Apakah produksi aktual mencapai target RO/NPS pada periode tersebut?
Evaluasi Matrik	Apakah luas, pohon, penyadap, aktivitas, dan produksi berada dalam keseimbangan?

Dan yang paling penting untuk AI:

Anna harus memisahkan fakta data, indikator turunan, dan interpretasi bisnis.

Contoh:

Fakta

Petak 28 C3 memiliki 8 penyadap dan total luas andil 8,5 Ha dari luas baku 10 Ha.

Indikator

Coverage luas andil mencapai 85%.

Interpretasi bisnis

Petak masih memiliki gap coverage 1,5 Ha yang belum teralokasikan.

Bukan:

"Petak ini bermasalah."

Karena "bermasalah" adalah kesimpulan evaluatif yang harus memiliki dasar KPI yang jelas.

Dengan struktur ini, Spatial Map + Chart Panel + Anna dapat menjadi satu sistem analisis: Anna memilih/mengontrol layer map, membaca KPI aktual, lalu menjelaskan apa yang terjadi, di mana terjadi, seberapa besar gap-nya, dan indikator apa yang mendukung kesimpulan tersebut.