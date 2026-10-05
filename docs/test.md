Yang paling penting: jadikan ini Business Ontology ANA

Jangan memasukkan pertanyaan tersebut hanya sebagai daftar prompt.

ANA seharusnya belajar model:

DIVRE
  │
  └── KPH
       │
       └── BKPH
            │
            └── RPH
                 │
                 └── TPG
                      │
                      └── PETAK
                           │
              ┌────────────┼────────────┐
              │            │            │
            ANDIL       POLYGON       TARGET
              │                         │
          PENYADAP                 RO / NPS
              │
          RENCANA
              │
          AKTIVITAS
              │
          PENERIMAAN
              │
            DRUM
          ┌───┼────┐
          │        │
  PENGANGKUTAN PERNI MUTU

Dan ada dua dimensi yang memotong graph tersebut:

                    ┌─────────────┐
                    │    WAKTU    │
                    │ Tahun/Bulan │
                    │ P1 / P2     │
                    └──────┬──────┘
                           │
BUSINESS GRAPH ────────────┼────────────
                           │
                    ┌──────▼──────┐
                    │   SPATIAL   │
                    │ Polygon     │
                    │ Point       │
                    │ Adjacent    │
                    └─────────────┘

Itulah yang akan membuat ANA mampu memahami pertanyaan seperti:

"Tampilkan di peta petak RTT tahun ini yang tidak memiliki penyadap, tetapi target RKAP-nya lebih dari 500 kg dan sampai P2 bulan ini pencapaiannya kurang dari 50%."

Pertanyaan tersebut sebenarnya bukan satu query sederhana. ANA harus melakukan:

tahun = CURRENT_YEAR
        ↓
petak.tahun_rtt = tahun
        ↓
petak tanpa penyadap
        ↓
target RKAP > 500
        ↓
hitung target sampai periode berjalan
        ↓
hitung realisasi sampai periode berjalan
        ↓
pencapaian < 50%
        ↓
ambil polygon
        ↓
MapLibre highlight/filter
        ↓
jawab COUNT + luas + daftar wilayah

Itulah level pemahaman yang sebaiknya kita jadikan target ANA, bukan sekadar membuatnya mampu menjawab pertanyaan secara hafalan