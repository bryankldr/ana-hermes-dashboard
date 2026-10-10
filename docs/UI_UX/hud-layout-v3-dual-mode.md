# HUD Layout v3 — Dual-Mode per User, Map Full-Body, Header Mobile Drawer

Tanggal: 2026-10-10. Status: FASE 1 + FASE 2 + FASE 3 SELESAI (2026-10-10, commit 849fb4e). V3 gantikan v2 (satu layout + auto-stack dibatalkan).

## 1. Keputusan kunci

- Tiap user punya 2 layout: `desktop` + `mobile`. Atur sekali per mode, simpan terpisah.
- `mapPanel` bukan panel bebas. Full-body otomatis isi `.hud-body`, tanpa drag, tanpa resize, tanpa simpan.
- Header desktop selalu tampil. Header mobile hidden default, drawer overlay hanya saat dipanggil.
- `bottomTelemetry` masuk header kanan sebagai strip mini. Footer bawah dihapus (ketutup keyboard/chat di mobile).
- `disabled` shared antar mode. `panel_access` (DB) tetap sumber gate.

## 2. Struktur UI

```
.hud-header
  desktop (>=780px): fixed top, full-width, z 30
    left: topControls (38x26 ikon-only, aturan tetap)
    center: topDials (arc saja, tooltip native via title, aturan tetap)
    right: bottomTelemetry mini (suhu CPU/GPU + equalizer 48x16)
  mobile (<780px): hidden default translateY(-100%), drawer overlay saat toggle
    toggle: tombol floating ☰ 38x26 kanan-atas, z 50, selalu tampil di mobile
.hud-body
  desktop: padding-top = tinggi header; mobile: full (header overlay, bukan push)
  #mapPanel: absolute inset 0, w/h 100%, z 5, non-drag non-resize, posisi dari CSS
  panel lain: floating absolute di atas map, drag + resize seperti sekarang
  #codeViewer: hidden default, overlay konfirmasi agen, bringToFront via freeZ (aturan tetap)
```

Aturan tetap yang tidak diubah: topControls ikon-only 38x26 + title, dials tanpa teks + title, codeViewer hidden default, drag via `closest('[data-layout-id]')`, gate `panel_access NULL = tanpa batas`.

## 3. Model data — `layout_<uid>.json`

```json
{
  "v": 3,
  "locked": true,
  "disabled": ["16"],
  "desktop": { "layouts": {
    "agentPanel": {"fx":0.02,"fy":0.10,"fw":0.16,"fh":0.30,"x":"30px","y":"120px","w":"230px","h":"260px"}
  } },
  "mobile": { "layouts": {
    "agentPanel": {"fx":0.04,"fy":0.08,"fw":0.92,"fh":0.25,"x":"15px","y":"90px","w":"330px","h":"200px"}
  } }
}
```

- `fx/fy/fw/fh 0-1` = sumber kebenaran posisi relatif terhadap `.hud-body`.
- `x/y/w/h px` = cache kompatibel + rollback. Server tulis dua-duanya saat save.
- `v` = versi migrasi. `v1` (px saja) dimigrasi sekali: `frac = px / viewport_saat_save`.
- `mapPanel`, `topControls`, `topDials`, `bottomTelemetry`, `codeViewer` TIDAK ada di `layouts`. Posisi dari CSS / overlay.
- `disabled` di root, shared desktop + mobile. Gate akhir = `panel_access AND NOT disabled`.
- Mode aktif dari viewport: `<780px = mobile`, selebihnya desktop. Tanpa toggle manual (toggle hanya preview, tidak simpan silang).

## 4. Perilaku per mode

Desktop:
- Header lock. Keluarkan 3 id header + mapPanel dari `LayoutManager ids`.
- Body panel bebas drag/resize. Save ke slot `desktop`.
- Offset migrasi sekali: `y += headerH` untuk slot desktop agar panel atas tidak ketutup header.

Mobile:
- Header hidden default. Toggle ☰ buka drawer overlay. Tap luar / tombol tutup → sembunyi.
- Body panel bebas juga (bukan stack otomatis). Slot `mobile` diatur user sesuai mau.
- Seed pertama: copy slot desktop lalu clamp full-width agar tidak kacau saat pertama buka.
- Drag sentuh hanya dari `.panel-title` (satu jari), agar scroll body tidak tabrakan drag.
- Resize handle 24px untuk jari (desktop 12px cukup).
- Map tetap full-body di belakang.

## 5. Store per-user (server)

Sekarang: `layout.json` tunggal global, `GET/POST /api/layout` token global, `{locked, layouts:{id:{x,y,w,h px}}, disabled}`.

Usulan:
- uid HANYA dari cookie sesi `ana_session` via `auth_local`. Bukan dari body/query. Cegah spoof.
- GET: `layout_<uid>.json` ada → pakai. Tidak ada → seed dari `layout.json` (desktop = isi lama, mobile = clamp copy), simpan terpisah setelah itu.
- POST body: `{mode: desktop|mobile, layouts, disabled}`. Validasi entri sama seperti sekarang (dict per id). Tulis atomic `tmp + rename`, bukan `write_text` langsung. Dua tab save bersamaan tidak corrupt.
- Token global tanpa sesi: baca `layout.json` read-only, POST ditolak 401.
- Rollback: hapus `layout_<uid>.json` → kembali `layout.json`. Satu file, tanpa migrasi DB.

## 6. Migrasi

1. Server baca `layout.json` lama → seed slot desktop.
2. Frontend keluarkan 4 id dari manager. Offset `y += headerH` sekali slot desktop.
3. `v1/v2` tanpa frac → hitung frac saat save pertama di viewport itu.
4. layout.json lama dipertahankan sebagai default global + fallback.

## 7. Fase + uji tiap fase

1. Header lock + map full-body (CSS + keluarkan ids + offset migrasi). Uji 1440 + 360: map isi body, header tidak geser, `node --check` + serve=disk.
2. Per-user 2 slot (server uid + atomic + seed + tolak token-only POST). Uji: user A geser desktop user B tidak ikut; tanpa login baca global; dua tab save tidak corrupt.
3. Frac + drawer mobile + touch-title-drag + handle 24px. Uji: 1440 → 360 → rotasi → keyboard buka (header tidak terdorong), panel tidak hilang.

Tiap fase rilis + smoke sebelum lanjut. Tanpa lompat fase.

## 8. Risiko + mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Slot mobile kosong pertama | panel kacau di HP | seed clamp otomatis dari desktop |
| Drag vs scroll mobile | jari geser panel malah scroll | drag hanya dari `.panel-title` |
| uid spoof via body | user tulis layout orang | uid dari sesi cookie saja |
| Drift rounding frac↔px | posisi geser tiap reload | frac sumber tunggal, px cache |
| Dua tab save bersamaan | file corrupt | atomic tmp+rename |
| Header tutup panel atas | panel tidak terjangkau | offset `y += headerH` sekali |
| Stack/auto hilang (sengaja) | user mobile atur manual dulu | seed + clamp, atur sekali per mode |

## 9. Yang belum diputus

- Breakpoint 780px (usul, bisa 768).
- Drag mobile dari title saja (usul, perlu uji).
- `disabled` shared (usul) vs per-mode (beban ganda, ditolak sementara).
- Equalizer 48x16 di header mini (usul, perlu cek visual).
