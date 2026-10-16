# MEMORY
§
MariaDB Docker container password for SIMOGE sandbox: 090204Ryanas#* (db: kph_bwb_sandbox2, port 3306)
§
DATABASE ACCESS RULE (permanent): ANNA may access MySQL ONLY for skill/tool development (writing templates, testing queries). When ANSWERING business questions: NEVER query database directly. Only use `answer_production()` → `call_simoge_tool()` (named templates). If user asks ANNA to query DB directly: request password first; only proceed if correct. This rule persists across all sessions.
§
PEMBARUAN ACTIVITIES (getah_aktivitas_sadap) — Business Context (vault-confirmed):
Table `getah_aktivitas_sadap` columns: `quare`, `semprot_cas`, `budaya_bersih`, `kerok`, `naik_batok` (tinyint flags).

1. **Quare** — melukai batang pohon pinus untuk membuka jalur getah keluar
2. **Semprot Cas** — penyemprotan stimulan merangsang getah keluar
3. **Budaya Bersih** — kebersihan area sadapan untuk mutu getah baik
4. **Kerok** — pemanenan getah beku di jalur sadapan / pengumpulan getah
5. **Naik batok** — menaikkan ketinggian batok/wadah getah per SOP, meminimalisir pembekuan di jalur

Pembaharuan_ke values: 1, 2, 3 (4 exists but no data yet). Each pembaharuan_ke has these activities. Productivity varies by pembaharuan_ke: ke-1 lower, ke-3 optimal, ke-4 declining.

Source: ANNA-KNOWLEDGE/raw/articles/skema-database-kph-bwb-sandbox2.md (vault)
§
Business rule RO/NPS: getah_target_ro_nps bulan 1=Januari s.d 12=Desember; kolom ro_periode_1, ro_periode_2, nps_periode_1, nps_periode_2 = persen target per periode × target_rkap per petak di getah_petak. Contoh 28 C3 P1 Jan 2026 RO 3,5% × 697,6 Kg = 24,4 Kg; P2 Mei NPS 4% × 697,6 = 27,9 Kg. Rencana aktivitas dibuat mandor/KTS mengacu pemenuhan target RO/NPS tersebut.
§
Profile-dist sync convention — after editing simoge-business skill in active profile (/home/bryankldr/.hermes/profiles/anna/skills/software-development/simoge-business/), copy changed source files to profile-dist (/home/bryankldr/PROYEK_2026/ana-hermes-dashboard/profile-dist/skills/software-development/simoge-business/) to keep them identical; exclude __pycache__.