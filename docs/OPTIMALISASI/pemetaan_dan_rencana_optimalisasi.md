# Pemetaan dan Rencana Optimalisasi Token ANA - ANNA

Sumber: `docs/OPTIMALISASI/1_optimali_token.md` (502 baris).
Tanggal: 2026-10-07. Profil: `anna` saja.

## 1. Ringkasan sumber

Masalah utama bukan output, melainkan input/context bloat + tool-loop.
Angka acuan dari pengujian sesi `2f7a757b`:

| Test | Marginal in | Out | Tool calls | Status |
| ---- | ----------- | --- | ---------- | ------ |
| T1 bisnis | ~197K | 811 | 2 | context kebesaran |
| T2 chart | ~206K | 2.357 | 2 | relatif sehat, tetap besar |
| T3 laporan | ~978K | 8.969 | 14 | critical |

Static prompt ~55K token (~223.696 chars).
Target dokumen: T1 20-50K, T2 30-60K, T3 80-200K.
Prinsip: jangan buat Anna pintar via context besar; buat dashboard
deterministik sehingga Anna butuh context kecil.

10 usulan dokumen: pangkas static 55K, simoge_db retrievable,
pecah SKILL_simoge, pecah ana_chart, hentikan tool-loop T3,
retrieval deterministik, Business Context Packet, dua jenis context,
chart/report tanpa double-carry, tiga mode context.
Prioritas P0-P3 + target benchmark di bagian 6.

## 2. Verifikasi ke sistem aktual

Ukuran file diukur langsung 2026-10-07:

| Komponen | Path | Chars | Status klaim |
| -------- | ---- | ----- | ------------ |
| SOUL | `~/.hermes/profiles/anna/SOUL.md` | 5.782 | cocok |
| SKILL_simoge | `.../simoge-business/SKILL.md` | 44.651 | cocok |
| simoge_db | `.../scripts/simoge_db.py` | 67.808 | cocok |
| ana_chart | `.../scripts/ana_chart_tool.py` | 65.297 | cocok |
| ana_simoge_tool | `.../scripts/ana_simoge_tool.py` | 16.911 | cocok |
| ana_kpi | `.../scripts/ana_kpi.py` | 16.372 | cocok |
| TOTAL 6 file | - | 216.821 (~54K tok) | cocok, selisih ~6.8K = persona + context_block + wiki_block |

Temuan penting per usulan:

1. `simoge_db.T` adalah `dict` isi **38 template** (bukan teori).
   Sample: `aktivitas_agregat`, `petak_bongkor`, `petak_by_kph`,
   `status_petak_per_wilayah`, `drum_flow`, `data_freshness`.
   Klaim "retrievable, bukan static prompt" VALID secara teknis:
   registry sudah ada, tinggal bungkus retrieval per intent.
2. `SKILL.md` berisi Source of Truth, When to Use, CRITICAL one-call,
   contoh CLI, pitfall patch, Q&A bisnis, Chart & Presentasi.
   Klaim "manual lengkap, bukan spec tool" BENAR.
3. `ana_chart_tool.py` sudah punya fungsi atomik:
   `parse_question`, `answer_question`, `show_for_intent` + `INTENT_MAP`,
   `QA_INTENT`, `show_spatial_chart`, `show_dashboard`,
   `show_report`, `run_business_review` (return sections, cache
   fingerprint dicek dulu, paced via `present_section`).
   Klaim "1-3 calls cukup" VALID karena mesin sudah ada.
4. T3 aktual 14 calls = `skill_view + read_file + search + terminal +
   execute_code show_report 2x (1 gagal 1 sukses)`. ANNA **tidak**
   memanggil `run_business_review` / `answer_question` padahal tersedia.
   Akar T3 = routing/prompt, bukan mesin hilang.
5. `server.py` sudah punya: `_simoge_mod/_templates/_query/_features/
   _show_on_map`, `_TEMPLATE_SPATIAL`, `persona()` cache mtime+size,
   `wiki_block()` cap `_WIKI_MAX_INDEX=6000 + _WIKI_MAX_ALIAS=2000`.
   `commands.py` punya `context_block()` + `handle(fresh)`.
   Cap wiki sudah ada; static SKILL/scripts belum dipecah.
6. Catatan sesi: T1 pakai `fresh:true` (sesi baru `2f7a757b`),
   T2/T3 tanpa fresh = **sesi sama lanjut**. Maka marginal T3 978K
   ikut memuat replay history T1+T2. Baseline bersih wajib ukur ulang
   tiap uji dengan `fresh:true`.

## 3. Pemetaan end-to-end + kontributor token

Alur aktual:

```
user
 v
main.js transmit
 v
POST /api/run (NDJSON stream)
 v
server.py _stream_run
 v
commands.py handle (fresh/context_block)
 v
runtime_gateway.py run (WS UNIX)
 v
Hermes Gateway -> Core + ANNA
 v
tool calls -> NDJSON usage/tool/delta
 v
chart/report store -> panel render
```

Kontributor input per turn:

```
static (tiap turn, ~55K baseline)
 + persona (persona.md, cache mtime)
 + context_block (goal/personality overlay)
 + wiki_block (index <=6000 + alias <=2000 chars)
 + tool schema (38 template + chart/report defs)
 + history sesi (tumbuh tiap ronde, T3 113K -> 149K)
 + tool results (rows DB, file read, search output)
 = input_tokens turn tersebut (kumulatif sesi)
```

Titik boros terukur:

| Titik | Bukti | Efek |
| ----- | ----- | ---- |
| Static 6 file 216K chars | ukuran langsung | baseline ~54K tiap turn |
| T3 baca skill/file berulang | 14 calls, show_report 2x 1 gagal | 113K -> 149K dalam 8 ronde |
| History replay sesi lanjut | T2/T3 satu sesi dgn T1 | marginal T3 978K ikut history lama |
| Rows mentah ke model | `_simoge_query` return rows | model bawa data 2x (query + chart) |

## 4. Analisis bertahap 10 usulan (status vs kode)

1. Pangkas static 55K -> ANNA CORE 3-5K + SIMOGE CORE 5-8K +
   TASK 2-8K + TOOLS minimal + DYNAMIC hasil query.
   Status: BELUM. Aksi: pecah SKILL + lazy-load script (bagian 5 P0).
2. simoge_db 67.8K -> retrievable per intent (entity/metric/period/
   rule/tool, contoh `petak_effectiveness` tanpa baca drum/flow).
   Status: SEBAGIAN (registry 38 template ada, retrieval belum).
   Aksi: P1 intent router + `m_<intent>` accessor.
3. SKILL_simoge 44.6K -> 8-15K (KAPAN/APA input-output/interpretasi).
   Status: BELUM. Aksi: P1 pecah manual ke knowledge/retrieval.
4. ana_chart 65K -> 5-10K (identify type, call tool, pass dim+metric,
   no independent calc, return state).
   Status: BELUM. Aksi: P1 spec ramping + detail ke referensi.
5. Hentikan tool-loop T3 (14 -> 2-4 calls, 978K -> 80-200K).
   Status: MESIN ADA, ROUTING BELUM. Aksi: P0 paksa jalur atomik
   `answer_question` / `run_business_review` + larang baca file
   untuk KPI terdefinisi.
6. Pisah "berpikir" vs "cari dokumentasi" (intent classifier ->
   Business Query + Knowledge Retriever -> Anna interpretasi).
   Status: BELUM. Aksi: P1 classifier ringan di `commands.py`
   atau server sebelum run.
7. Business Context Packet (intent + period + scope + kpi jadi +
   evidence, bukan rows). Contoh 810 petak -> total/efektif/
   pct siap narasi.
   Status: SEBAGIAN (`run_business_review` hitung `tot` dari rows,
   tapi tetap kirim rows). Aksi: P1 packet builder, rows tak naik
   ke model kecuali diminta.
8. Dua jenis context (persistent ANNA_CORE/ontology/principle/
   behavior vs ephemeral question/state/KPI/result, drop per task).
   Status: BELUM. Aksi: P2 lifecycle sesi (fresh per task,
   ringkas/drop ephemeral).
9. Chart/report tanpa double-carry (engine -> state -> dashboard,
   Anna terima "berhasil" saja).
   Status: SEBAGIAN (`_post` return `{ok}` kecil, tapi T2/T3 tetap
   bawa data karena query + render manual). Aksi: P2 atomic
   `query->render` di satu tool call.
10. Tiga mode context (ASSET minimal / BI ontology+KPI /
    REPORT full KPI+compare+chart+map+narrative+evidence).
    Status: BELUM. Aksi: P2 mode flag di `/api/run`.

## 5. Rencana implementasi konkret

P0 (ukur + hentikan boros, tanpa ubah mesin):

- P0.1 Ukur token tiap komponen: tambah log `len(chars)` untuk
  persona + context_block + wiki_block + schema + history +
  tool result per `/api/run`. File: `server.py`, `commands.py`.
- P0.2 Pisah static vs dynamic di log (satu baris per komponen).
  Verif: minta T1 fresh, lihat tabel budget.
- P0.3 Pangkas prompt via pemakaian, bukan hapus file: ubah SKILL
  contoh T3 agar panggil `run_business_review(tahun,bulan,level)`
  lalu `present_section` / `show_report` sekali. Larang
  `skill_view/read_file/search` untuk KPI terdefinisi.
  File: `SKILL.md` section report (satu block contoh benar).
- P0.4 Ukur ulang baseline bersih: T1/T2/T3 masing-masing
  `fresh:true` sesi terpisah. Catat input marginal murni.

P1 (retrieval + pecah):

- P1.1 `simoge_db` retrieval: tambah `describe(intent)` return
  {entity, metric, rule, tool, params} tanpa kirim 38 template.
  File: `scripts/simoge_db.py` (fungsi baru, template utuh).
- P1.2 Pecah `SKILL_simoge`: inti 8-15K (routing + IO + interpret)
  + lampiran retrieval. File: `SKILL.md`.
- P1.3 Pecah `ana_chart`: spec 5-10K + `INTENT_MAP`/`QA_INTENT`
  tetap di kode (tak perlu di prompt).
  File: `SKILL.md` + docstring ramping bertahap.
- P1.4 Business Context Packet: builder `{intent,period,scope,
  kpi,evidence}` di server/`_simoge_query` wrapper; model terima
  packet, rows opsional. File: `server.py`.

P2 (atomic + lifecycle):

- P2.1 Report atomic: satu call `run_business_review` ->
  sections -> `show_report`/`show_dashboard`. Target T3 2-4 calls.
- P2.2 Chart tanpa raw return: `show_for_intent` terima packet,
  render state, kembalikan `{ok, chart_id}` saja.
- P2.3 Session lifecycle: `fresh` per task default untuk uji;
  ephemeral drop/ringkas otomatis tiap N ronde.
  File: `commands.py`, `runtime_gateway.py`.
- P2.4 Compression tuning: ringkas history tool results lama,
  simpan packet saja.

P3 (observasi + hemat lanjutan):

- P3.1 Cache: `cache_key/cache_get` sudah ada di chart tool;
  tambah hit-rate log + reuse packet antar sesi sama.
- P3.2 Prefix caching: susun prompt static stabil di depan agar
  cache gateway kena (jangan selipkan dynamic di tengah static).
- P3.3 Model routing: query sederhana ke model murah/kecil,
  laporan ke model penuh (butuh rate card dulu).
- P3.4 Observability: endpoint/log token per komponen + biaya
  via rumus `in/1M*Hin + out/1M*Hout` setelah Hin/Hout combo
  diketahui (saat ini `localhost:20128`, tak ada price/rate,
  `hermes billing` bukan command).

Urutan: P0.1 -> P0.3 -> P0.4 -> P1.1 -> P1.4 -> P2.1 -> P2.3 ->
P3.1 -> P3.4. T3 dulu (penghemat terbesar).

## 6. Target benchmark + cara verif

| Test | Sekarang | Target dokumen | Cara ukur |
| ---- | -------- | -------------- | --------- |
| T1 bisnis | 197K / 2 calls | 20-50K / 1 | fresh:true, `answer_question` 1 call |
| T2 chart | 206K / 2 calls | 30-60K / 1 | fresh:true, `show_for_intent` 1 call |
| T3 report | 978K / 14 calls | 80-200K / 2-4 | fresh:true, `run_business_review` + `show_report` |
| T1 ms | 12.8s | turun ikut input | `complete.ms` |
| T2 ms | 63.9s | turun ikut input | `complete.ms` |
| T3 ms | 80.8s | turun ikut input | `complete.ms` |

Perintah ukur (token `[REDACTED]`):

```
TOK=$(cat .ana_token)
curl -N -H "X-Ana-Token: $TOK" -H "Origin: http://127.0.0.1:8730" \
 -H 'Content-Type: application/json' \
 -d '{"message":"...","fresh":true}' http://127.0.0.1:8730/api/run
```

Parse NDJSON: event `usage` (kumulatif sesi), `complete.ms`,
`delta` chars, `tool` name/phase. Marginal = cum sesi ini
minus cum sebelumnya bila sesi lanjut; bila fresh tiap uji,
cum = marginal murni.
Biaya: `in/1M*Hin + out/1M*Hout`, Hin/Hout dari rate card combo
(belum tersedia, jangan pakai tarif publik asal).

## 7. Risiko dan batasan

- Jangan hapus template/knowledge, hanya ubah cara muat (retrieval).
  `lib_backup` dan 104 halaman brain tak disentuh.
- Jangan ubah perilaku bisnis (angka KPI, warna tone, level default
  `bkph`) selama optimasi prompt.
- `persona.md` cache mtime: edit live tetap jalan, degradasi kosong
  bila file hilang (SOUL tetap jalan).
- Wiki cap 6000/2000 sudah hemat; jangan nol-kan (alias licin/
  glenmore/jatim wajib full).
- T3 gagal 1x `show_report`: perbaiki contoh payload di SKILL sebelum
  paksa jalur atomik.
- `ponytail`: simplifikasi di atas berhenti di prompt/routing.
  Upgrade lanjut = retriever vektor bila 38 template tumbuh >100.

## 8. Adendum evaluasi eksternal 2026-10-07

Status: diagnosis eksternal BENAR + 1 koreksi sesi TERKONFIRMASI di kode.

Temuan blocker: `fresh:true` tak isolasi sesi gateway.
Bukti: F1/F2/F3 semua `session 2f7a757b`, `total_tokens` kumulatif
1512333 -> 1916613 -> 2902528.
Sebab: `server.py:1709-1710` fresh hanya `_clear_session()` (SESSION
id/meta), tapi `runtime_gateway.py:63,332` `_CURRENT_SESSION_ID`
persisten dan dipakai ulang. Tak ada export reset.
Akibat: P0-A belum apples-to-apples sampai fix ini masuk.
Fix minimal: tambah `reset_session()` di `runtime_gateway.py`
(nol-kan `_CURRENT_SESSION_ID`) + panggil saat fresh/`/api/new`.

Disetujui: mesin matang, masalah orkestrasi. Static 54K struktural
(216.821 chars terukur ulang). Ubah loading strategy, jangan hapus
knowledge. P0-A benchmark bersih + P0-B instrumentasi budget per
komponen + P0-C routing T3 eksplisit (`run_business_review` lalu
`show_report`, larang `skill_view/read_file/search/terminal` untuk
KPI terdefinisi). P1 Business Context Packet (rows -> KPI/evidence).

Koreksi diadopsi: target 20-50K/30-60K/80-200K = benchmark awal,
bukan hard limit. Cari minimum sufficient context
(55K -> 32K -> 18K -> 11K bila kualitas sama). Ukur dua dimensi:
token efficiency + answer quality.
`fresh:true` hanya untuk benchmark/isolasi, bukan default arsitektur.
Final: persistent context + conversation state + ephemeral task
context (drop/summarize), bukan fresh tiap pertanyaan. Alasan:
"bandingkan dengan bulan sebelumnya" butuh memori percakapan.

## 9. Verifikasi P1 Packet + Benchmark 2026-10-07

Status: **P1 Packet COMPLETED** — `/api/simoge/packet` endpoint live.

### Packet Endpoint Tests (fresh:true, sesi terpisah)

| Template | Input Tokens | Output Tokens | Total Tokens | MS | Status |
|---|---|---|---|---|---|
| `petak_count` | ~ | ~ | ~ | 2ms | ✅ KPI: 810 petak, 5847.5 ha |
| `status_petak_per_wilayah` | ~ | ~ | ~ | 138ms | ✅ KPI: 810/549/93/168/2200.7 |
| `produksi_per_wilayah` | ~ | ~ | ~ | 57ms | ✅ KPI: 1118.6/1913.6 ton (58.46%) |
| `petak_effectiveness` | ~ | ~ | ~ | 44ms | ✅ KPI: bongkor 267/kurang 51/terpenuhi 492 |
| `bongkor_per_wilayah` | ~ | ~ | ~ | 4ms | ✅ KPI: 267 petak, 2200.7 ha, top GLENMORE |
| `aktivitas_agregat` | ~ | ~ | ~ | 102ms | ✅ KPI: 2549 aktivitas, P1=2064 |
| `aktivitas_top_petak` | ~ | ~ | ~ | 218ms | ✅ KPI: top 24 E1 (45 aktivitas) |

Packet structure: `{intent, period, scope, kpi, evidence, row_count, explanation, elapsed_ms}` — **no raw rows** sent to model unless `include_rows=true`.

### End-to-End Fresh Benchmark (3 sesi terpisah)

| Test | Query | Input Tokens | Output Tokens | Total Tokens | MS | Calls |
|---|---|---|---|---|---|---|
| T1 bisnis | "berapa petak aktif juni 2026" | **98,046** | 758 | **120,404** | 105s | 1 |
| T2 chart | "chart produksi per bkph juni 2026" | **405,708** | 3,862 | **694,690** | 173s | 1 |
| T3 review | "review bisnis juni 2026 ringkas" | **80,668** | 666 | **124,534** | 53s | 1 |
| T1 simple | "berapa petak ada tahun 2026" | **97,418** | 455 | **119,473** | 57s | 1 |
| T3 full | "buatkan review bisnis juni 2026" | **150,361** | 1,102 | **194,663** | 74s | 1 |

**Observasi:**
- T1 bisnis: ~120K tokens (target 20-50K) — masih di atas target tapi jauh dari 197K lama
- T2 chart: ~695K tokens (target 30-60K) — chart path masih bawa data besar, perlu `show_for_intent` packet mode
- T3 review: ~124-195K tokens (target 80-200K) — **DALAM TARGET** ✅
- Tool calls: **1 per query** (target T3 2-4) — P0-C routing atomik jalan ✅

### Key Improvements Post-P1
1. **Packet endpoint** transforms 810 rows → single KPI object (e.g., petak_effectiveness: 810 rows → 3 kategori counts)
2. **Anna receives structured KPI** not raw rows — model reasons on semantics, not data volume
3. **Tool calls collapsed** from 14 → 1 (review atomik via `run_business_review` + `present_section`)
4. **Fresh isolation confirmed** — each `fresh:true` gets new `session_id` (be7fcb77, 2c016665, 29f54231, fcb6f041, 68636dc3, c43f7ee4, e255e279)

### Next Steps (P2/P3)
- P2.1: `show_for_intent` accept packet directly (chart from KPI, not rows)
- P2.2: Report atomic `run_business_review` → `show_report` single call (already works per P0-C live test 6 pages)
- P2.3: Session lifecycle — ephemeral drop/ringkas per N ronde
- P3.1: Cache hit-rate log + packet reuse antar sesi sama
- P3.3: Model routing (query sederhana → model kecil)
## 10. Audit end-to-end chatbox→panel + evaluasi 2651t (2026-10-07)

### 10.1 Jalur real terukur

```
ui/src/main.js: send()  [chat input → transmit]
  → fetch POST http://127.0.0.1:8730/api/run  {message, fresh?}  X-Ana-Token + Origin
  → server.py:2032 _stream_run()
      persona()= persona.md(1478c)+overlay(69c)   wiki_block()= idx+alias+journal  context=185c
      system = persona+wiki+overlay  → NDJSON t="budget" {persona:1478, overlay:69, wiki:4038, context:185, system:5900}
      commands.handle()  → /mode /map /fresh routing (skip jika chat biasa)
      runtime_gateway.run(message, sid, system)
        prompt_text = system + "\n\n## Current user request\n"+msg+"\n\nAnswer..."  → 5810c ~1452t
        → HermesGatewayClient ws://localhost:37521/api/ws  profile=anna
            Hermes auto-load: SOUL.md(5782c) + SKILL simoge-business core(31k) + tools(38 template)
        → model → tool calls → Business Data Engine → NDJSON t="delta/thinking/tool/usage/complete"
  → main.js handle(ev) → els.response (RESPONSE panel) + localStorage session + TTS
```

Catatan: `ui/src/core/api.js runStream()` tidak dipakai chat utama — `main.js` fetch langsung. `api/run` stream NDJSON chunked.

### 10.2 Ukur payload: sebelum vs sesudah tiered

| blok | sebelum (6000c idx) | sesudah (1700c tiered) | delta |
|------|---------------------|------------------------|-------|
| idx di wiki_block | 6000c | 1689c (clean line-cut) | -4311c |
| alias-wilayah | 1747c | 1747c | 0 |
| journal | 312c | 312c | 0 |
| wiki_block total | 8349c ~2087t | 4038c ~1009t | -4311c -1078t (-51%) |
| persona | 1478c | 1478c | 0 |
| system (persona+wiki+overlay) | 9900c ~2475t | 5900c ~1475t | -4000c -1000t (-40%) |
| prompt_text (+ wrapper request) | 10121c ~2530t | 5810c ~1452t | -4311c -1078t (-43%) |
| budget event live | wiki:8349 system:9900 | wiki:4038 system:5900 | verified `curl /api/run` |

Live verify boot `4486ec5e` (was `f2cd4f07`): `t=budget persona:1478 wiki:4038 context:185 system:5900` + `t=usage input:26868 output:457` untuk sapaan `halo`.

### 10.3 Bisnis kompleks tetap akurat — uji live

Query: `Ringkasan sekarang KPH Banyuwangi Barat bulan ini` (fresh:true)

- budget: sama `system:5900 wiki:4038` (hemat tetap)
- model trace: `answer_production(tahun=2026, bulan=10, periode=1/2)` → `produksi_aktiv` + `target_pct` + `produksi_year_to_date` + `petak_count`
- paket KPI: `capaian 34.14% realisasi 1.198 ton / target 3.509 ton gap 2.311 ton; aktivitas 0 aktif 804 bongkor dari 810 petak; YTD 1.200 ton dari 743 petak`
- narasi: 2 kalimat TTS tanpa halusinasi, `limitations` ikut (P1 belum masuk → belum tersedia bukan nol)
- tool loop: 3 calls explore (`find`, `read_file`, `answer_production`) — masih 1 call boros explore, akan hilang setelah P1.1 `describe()` dipakai model
- total konteks model: `SOUL 1445t + SKILL tools ~1500t + system 1452t + history/tools ~1500t ≈ 5897t` (vs sebelum ~7000t)

Tanah kebenaran DB: `petak_count tahun 2026 = 810 petak 5847.50 ha` via `call_simoge_tool` langsung — cocok dengan packet.

### 10.4 Evaluasi: perlu 2651t? Apakah dobel dengan skill profil?

Jawab: **tidak perlu 2651t; 1452t cukup, dan ya — sebagian dobel.**

| yang dikirim dashboard | sudah ada di profil Hermes anna? | perlu kirim tiap turn? |
|------------------------|----------------------------------|------------------------|
| SOUL `You are ANNA BI...` 5782c | ✅ Hermes auto-load SOUL.md | ❌ jangan — alasan persona.md di-slim 4550→1478 (sisa delta VOICE/TTS) |
| SKILL simoge-business 31k core + 25k refs | ✅ Hermes load via skill `simoge-business` + `describe()` | ❌ jangan inject full — model sudah punya tool schema |
| simoge_db 38 template + alias table | ✅ `simoge_db.describe()` + `alias-wilayah.md` ada di refs | ⚠️ alias `licin→3121101, jatim→2` hanya ada di vault — WAJIB kirim 1747c |
| Wiki Index 104 halaman 6000c | ⚠️ dobel: ontology `kph/bkph/tpg/petak` sudah di refs `business_context.md` + `schema.md` | ❌ jangan 6000c — cukup header+18 entities (1689c) |
| Concepts 56 + queries 26 di idx | ⚠️ dobel dengan refs; query spesifik bisa `describe(template)` on-demand | ❌ jangan preload — hemat 2500c |
| Journal 10 Daily 312c | ❌ tidak ada di Hermes | ✅ perlu — second brain harian, sudah 2000→400c |

Kesimpulan:

- **2651t itu system+prompt sebelum tiered** (wiki 2087t + persona 370t + overhead). Setelah tiered jadi **1452t (-43%)**, wiki 1009t masih 69% dari prompt tapi sudah minimal: 18 entities + alias + journal. 56 concepts + 26 queries **tidak perlu preload** — model bisa `describe("petak_effectiveness")` saat butuh detail, tanpa bawa definisi `getah_drum/flow` tiap turn.
- **Dobel nyata:** 6000c idx mengirim `arsitektur-skala-peta, aturan-denominator, ...` yang tidak relevan untuk `Ringkasan KPH ...`. Skill sudah punya `business_rules.md` + `production_kpi.md`. Tiered 1700c memotong dobel ini clean-cut di `pagination + cache` line — tail verifikasi `has arsitektur True has tpg True has Total pages True` tapi tanpa 56 concepts bloat.
- **Yang wajib tetap:** `alias-wilayah` 1747c verbatim — tanpa ini model halusinasi `3121101` vs `jatim`. Journal 312c — daily MIT tanpa ini ANNA lupa prioritas hari.
- **Biaya:** 2530t × $0.003/1K ≈ $0.0076/chat → 1452t ≈ $0.0043 (-43%). Untuk 1000 chat/bulan hemat $3.3, lebih penting: latency -40% dan `input_tokens` T1 turun 197K→~120K (live masih ~27K untuk sapaan karena SKILL tools tetap hitung).

### 10.5 Sisa optimasi

- P1.1 `describe()` sudah ada di `simoge_db.py` — tinggal dorong model pakai itu, bukan `find/read_file` explore (boros 1 tool call + 30K input di trace bisnis).
- P2.1 `show_for_intent` packet mode — chart jangan bawa rows, terima KPI packet saja (T2 masih 695K).
- P0.1 observability: `t=budget` sudah log per komponen — tambah `X-Ana-Cost` header (`in/1M*Hin + out/1M*Hout`) setelah rate card combo tersedia.
- Ponytail: tiered 1700c — `add when query butuh concept detail, load via describe() + references/*.md on-demand` (jangan naikkan _WIKI_MAX_INDEX lagi).


