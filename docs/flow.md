Operator
   │
   ▼
"petak RTT tahun ini"
   │
   ▼
Business Context
   │
   ├── RTT = ?
   ├── Petak = ?
   ├── tahun RTT = CURRENT_YEAR
   └── default scope = tahun berjalan
   │
   ▼
Data Resolver
   │
   ├── resolve tabel/collection Petak
   ├── resolve field tahun_rtt
   └── resolve geometry
   │
   ▼
Database
   │
   │ SELECT COUNT(*)
   │ FROM petak
   │ WHERE tahun_rtt = 2026
   │
   ▼
Spatial Query
   │
   │ SELECT geometry
   │ FROM petak
   │ WHERE tahun_rtt = 2026
   │
   ▼
MapLibre MCP
   │
   ├── add/filter layer
   ├── highlight RTT Petak
   └── fitBounds()
   │
   ▼
ANA
   │
   └── "Ditemukan 1.247 petak RTT tahun 2026.
       Sudah saya tampilkan di peta."