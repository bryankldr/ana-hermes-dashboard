# Business Context — SIMOGE

## Acronym Definitions

| Singkatan | Bahasa | Arti |
|-----------|--------|------|
| SIMOGE | - | Sistem Informasi Manajemen Operasional Kebun (Forest Management System) |
| RTT | Rencana Tebang Tanam | Annual cutting/planting plan |
| KPH | Kesatuan Pengelolaan Hutan | Forest Management Unit |
| BKPH | Balai Kesatuan Pengelolaan Hutan | Sub-unit of KPH |
| RPH | Resor Pengelolaan Hutan | Forest Management Plan |
| TPG | Tempat Pengumpulan Getah | Tapping location (collection point) |
| Drum | - | Container untuk pengangkutan getah |
| Perni | - | Surat perintah pengangkutan |
| Mutu TPG | - | Quality grade on TPG|
| Mutu PGT | - | Quality grade on PGT|
| RO | Retak Out | (target metric) |
| NPS | Non-Petak Sadap | (target metric) |
| RKAP | Rencana Kerja | Annual work plan / production target |
| Sadap | - | Tapping (natural pine resin collection) |
| Andil | - | Tapper assignment to a petak |
| Evapot | Evaluasi Potensi | Potential Evaluation |
| Getah | - | Natural pine resin |

## Key Entities

### PETAK (Work Unit)
- **Format nomor_petak**: `{hierarchy} {letter/number}` e.g. "28 C3"
- **Identitas**: `kode_evapot` (primary join key), `nomor_petak`, `kode_kph`, `kode_bkph`, `kode_rph`, `kode_tpg`
- **Metrics**: `luas_baku` (ha), `target_rkap` (kg), `tahun_rtt`, `jumlah_pohon`, `tipe_jarak`
- **Status**: `status` (string), `ket` (keterangan)

### RTT (Rencana Tebang Tanam)
- **Scope**: Annual plan covering all petak in a KPH
- **Field**: `getah_petak.tahun_rtt` (e.g. 2025, 2026)
- **Default year**: CURRENT_YEAR
- **KPH Banyuwangi Barat** (kode_kph=31211): 810 petak, total luas 5.847,5 ha (2026)

### PENYADAP (Tapper)
- Collects resin from petak via tapping
- Linked to petak through `getah_andil` (andil = assignment)
- Linked to activities via `getah_aktivitas_sadap` (actual tapping)

### ANDIL (Assignment)
- Penyadap → Petak assignment
- `kode_evapot` links to both `getah_petak` and `petak_polygon`
- `luas_andil` = area assigned to each penyadap

### DRUM (Container)
- Carries collected resin (getah) from petak to collection point
- **Status flow**: aktif → transport → perni
- **DB rule** (`database_helper.updateDrumWithStatusLogic`):
  - has `nomor_perni` → status = 'perni' (completed)
  - has `nomor_pengangkutan` → status = 'transport' (in transit)
  - else → 'penuh' (full, awaiting transport)

### PERIODE
- **Periode 1**: tanggal 1-15 (first half of month)
- **Periode 2**: tanggal 16-akhir (second half of month)
- **P1 saat ini** = periode 1 bulan ini
- **P1 sampai dengan** = akumulasi periode 1 dari bulan 1 s/d bulan ini
- **P2 sampai dengan** = akumulasi periode 2 dari bulan 1 s/d bulan ini

### TARGET RO/NPS
- Table: `getah_target_ro_nps`
- **Columns**: `bulan` (1-12), `ro_periode_1`, `ro_periode_2`, `nps_periode_1`, `nps_periode_2`
- **Values**: Percentage breakdown (e.g. 3.5 = 3.5%)
- **Calculation**: Target per petak = `target_rkap` × (`ro_periode_X` / 100)

Example:
- Petak 28 C3, target_rkap = 697,6 Kg
- Periode 1, bulan 1, tahun 2026: 3,5%
- Target = 697,6 × 0,035 = **24,4 Kg**
- Periode 2, bulan 5, tahun 2026: 4%
- Target = 697,6 × 0,04 = **27,9 Kg**

## Kode KPH

| Kode | Nama |
|------|------|
| 31211 | BANYUWANGI BARAT |

## Color Codes (Polygon)

### Efektivitas Petak (presence of tappers)
| kategori | warna | hex |
|----------|-------|-----|
| bongkor (no penyadap) | merah | #ef4444 |
| kurang (luas_andil < luas_baku) | kuning | #eab308 |
| terpenuhi (luas_andil >= luas_baku) | hijau | #22c55e |

### Pencapaian RKAP
| range | warna | hex |
|-------|-------|-----|
| 0-25% | merah | #ef4444 |
| 26-50% | oranye | #f97316 |
| 51-75% | kuning | #eab308 |
| 76-100% | hijau | #22c55e |
| >100% | emas | #fbbf24 |

## Idle / Bongkor Definitions

| Term | Definition |
|------|------------|
| Petak Bongkor | No `getah_andil` rows at all (no penyadap assigned ever) |
| Andil Bongkor | Penyadap has activity but zero collections for 2+ months |
| Petak Idle | Had activity last period, no activity this period |
| Andil Idle | Penyadap had activity last period, no activity this period |
| Petak Aktif | Has activity in current period |
| Andil Aktif | Penyadap has activity in current period |

## Productivity Threshold

A penyadap is **kurang produktif** if:
- Has activity (aktif)
- BUT: `berat_penerimaan` < target periode
- Target periode = `target_rkap` × RO% (from `getah_target_ro_nps`)
- Rasio = `luas_andil` / `luas_baku` × 100 compared to periode target
- If `berat_penerimaan` < target → kurang produktif
