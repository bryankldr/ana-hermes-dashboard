# Skill Evaluation Notes — ana-hermes-dashboard

Tanggal: 28 Sep 2026
Sumber daftar: `/home/bryankldr/PROYEK_2026/ana-hermes-dashboard/skill.md` (15 entri)
Metode: `hermes skills install` satu per satu → scan `skills-guard-v6` → baca `SKILL.md` → uninstall jika tidak relevan
Konteks proyek: Flutter `simoge_revisi_juli_2026` + `ana-hermes-dashboard` (Dart/TS, AVD Pixel_9, Docker/Compose), bukan data platform / Next.js heavy / Kaggle

## Ringkasan Eksekutif

- **Dipertahankan (2):** `docker-management`, `pm2-remote-manager`
- **Dibuang (11):** `ai-proposal-generator`, `code-review-sr`, `afrexai-data-analyst`, `afrexai-data-engineering`, `fl-sql-analyst`, `mcp-builder-cn`, `nlm-notebooklm`, `afrexai-nextjs-production`, `ai-coder`, `agent-collaboration-profile-builder`, `form` (stale)
- **Diblokir — jangan pasang (2):** `kaggle`, `yuyonghao-mcp-client` (verdict DANGEROUS, Hermes menolak install paksa)

Semua skill yang dibuang sudah di-uninstall. `hermes skills list` kini hanya menyisakan builtin + 2 yang dipertahankan.

## Tabel Keputusan

| # | Skill | Source | Verdict Scan | Keputusan | Alasan Singkat |
|---|---|---|---|---|---|
| 1 | `ai-proposal-generator` | clawhub (@jeffjhunter) | SAFE | **BUANG** | Generator proposal HTML 5 style/6 theme dari meeting notes. Workflow enterprise sales, tidak ada use-case di simoge/dashboard. |
| 2 | `code-review-sr` | clawhub (@theshadowrose) | SAFE | **BUANG** | AI code review (regex pre-pass + LLM). Fungsi duplikat builtin `sdlc-review` yang sudah ada. |
| 3 | `afrexai-data-analyst` | clawhub (@1kalin) | SAFE | **BUANG** | Framework DICE lengkap (571 baris, template SQL RFM/cohort/funnel). Untuk tim data analyst, bukan Flutter/ops. |
| 4 | `afrexai-data-engineering` | clawhub (@1kalin) | SAFE | **BUANG** | Data Engineering Command Center (921 baris). Overkill untuk skala proyek ini. |
| 5 | `form` | clawhub | STALE (file upstream hilang) | **BUANG / SKIP** | Index kadaluarsa, tidak bisa di-install. |
| 6 | `kaggle` | clawhub (@shepsci) | **DANGEROUS** (61 finding) | **JANGAN PASANG** | Persistence cron/launchd, exfiltrasi KAGGLE_TOKEN. Hermes block paksa. |
| 7 | `fl-sql-analyst` | clawhub (@philipstark) | SAFE | **BUANG** | NL→SQL (SQLite/PG/MySQL) + CSV import. Tidak ada kebutuhan NL→SQL; cukup via `xlsx`/`docx`/`pdf` builtin. |
| 8 | `mcp-builder-cn` | clawhub (@yang1002378395) | SAFE (1 MEDIUM) | **BUANG** | Guide membangun MCP server. Kamu butuh memakai, bukan membangun MCP. |
| 9 | `yuyonghao-mcp-client` | clawhub (@yuyonghao-123) | **DANGEROUS** (6 finding) | **JANGAN PASANG** | Bocor GITHUB_TOKEN hardcoded, traversal /etc/passwd. Hermes block paksa. |
| 10 | `nlm-notebooklm` | clawhub (@hewenqiang) | SAFE | **BUANG** | Wrapper `nlm` CLI + MCP NotebookLM. Butuh login Google + `nlm` terpasang, bukan workflow saat ini. |
| 11 | `docker-management` | official (sprmn24) | CAUTION (official) | **TAHAN** | Manage container/image/compose/volume/network. Relevan — dashboard & simoge pakai Docker/Compose. |
| 12 | `afrexai-nextjs-production` | clawhub (@1kalin) | CAUTION (9 finding) | **BUANG** | Next.js production checklist. Dashboard Next.js sederhana, tidak butuh metodologi berat ini. |
| 13 | `pm2-remote-manager` | clawhub (@qoohsuan) | SAFE | **TAHAN** (kondisional) | SSH-based PM2 remote. Berguna jika deploy Node di VPS pakai PM2. Hapus jika tidak pakai PM2. |
| 14 | `ai-coder` | clawhub (@chinakingkong) | SAFE | **BUANG** | Generic code-gen sangat tipis (61 baris). Kalah vs builtin `claude-code`/`codex`/`opencode`. |
| 15 | `agent-collaboration-profile-builder` | clawhub (@lakendocean) | SAFE | **BUANG** | Kuesioner → USER.md/WORKSTYLE.md. One-time setup, bukan skill operasional. |

## Detail Per Skill

### 1. ai-proposal-generator — BUANG
Fungsi: `Meeting Notes + Template + Theme → HTML Proposal` responsif + export PDF. 5 style, 6 theme, wizard 6 langkah.
Kenapa dibuang: Tidak ada alur pembuatan proposal klien di proyek. Menambah file `proposals/templates/themes` tanpa pemakai.

### 2. code-review-sr — BUANG
Fungsi: Local regex pre-pass (secrets, eval, SQLi) + AI deep review (Anthropic/OpenAI/Ollama), score 1-10. Zero deps.
Kenapa dibuang: Duplikat builtin `sdlc-review`. Risiko kirim source ke AI provider.

### 3. afrexai-data-analyst — BUANG
Fungsi: DICE (Define/Investigate/Communicate/Evaluate), profiling SQL, 5-splits, cohort/RFM/funnel, rubric 0-100.
Kenapa dibuang: Stack simoge SQLite/Drift + Directus, bukan warehouse analytics.

### 4. afrexai-data-engineering — BUANG
Fungsi: 11 fase data engineering (architecture, SCD, pipeline, quality, PII, cost).
Kenapa dibuang: Untuk tim data platform TB-scale. Proyek ini <1GB batch pull-only.

### 5. form — BUANG / SKIP
Fungsi: Tidak terverifikasi — `Error: files no longer exist upstream`. Stale index.

### 6. kaggle — JANGAN PASANG (DANGEROUS)
Fungsi: Kaggle competition + badge-collector.
Kenapa diblokir: 61 high-risk (persistence cron/launchd, docker_pull, KAGGLE_TOKEN exfil). Hermes menolak bahkan dengan --force.

### 7. fl-sql-analyst — BUANG
Fungsi: NL→SQL SQLite/PG/MySQL, CSV import ke `data/analyst.db`, saved queries.
Kenapa dibuang: Tidak butuh NL→SQL tambahan.

### 8. mcp-builder-cn — BUANG
Fungsi: Panduan 4 fase membangun MCP server (FastMCP/TS SDK).
Kenapa dibuang: Fokus memakai skill, bukan membangun MCP.

### 9. yuyonghao-mcp-client — JANGAN PASANG (DANGEROUS)
Fungsi: MCP client helper.
Kenapa diblokir: GITHUB_TOKEN hardcoded, /etc/passwd traversal. Hermes block paksa.

### 10. nlm-notebooklm — BUANG
Fungsi: `nlm` CLI + MCP NotebookLM (research/podcast/quiz/video).
Kenapa dibuang: Butuh `nlm login` (session ~20 menit) + Google. Tidak ada workflow NotebookLM. Alternatif: `arxiv`/`grounded-citations` builtin.

### 11. docker-management — TAHAN
Fungsi: Docker CLI lengkap (container, image, compose, volume/network, cleanup, Dockerfile optimization).
Kenapa ditahan: Official skill, relevan untuk compose stack dashboard & simoge. CAUTION wajar (sudo/docker_pull).

### 12. afrexai-nextjs-production — BUANG
Fungsi: Next.js production (App Router, RSC, Core Web Vitals, caching, deploy).
Kenapa dibuang: Dashboard bukan app Next.js skala produksi.

### 13. pm2-remote-manager — TAHAN (kondisional)
Fungsi: Remote PM2 via SSH (list/restart/logs/monit/scale, ecosystem.config.js).
Kenapa ditahan: Berguna jika deploy Node via PM2 di VPS. Jika full Docker Compose, boleh dibuang.

### 14. ai-coder — BUANG
Fungsi: Generic code-gen/debug/testing 61 baris tanpa tool konkret.
Kenapa dibuang: Kalah lengkap vs builtin `claude-code`/`codex`/`opencode`.

### 15. agent-collaboration-profile-builder — BUANG
Fungsi: Kuesioner 5 dimensi → `AI_USER_PROFILE.md` / `USER.md`+`WORKSTYLE.md`.
Kenapa dibuang: One-time profiling, bukan skill harian. Bisa diganti `memory` + USER.md manual.

## State Akhir

```
hermes skills list | grep -E "docker|pm2"
  docker-management  devops  official  official  enabled  → TAHAN
  pm2-manager        —       local     local     enabled  → TAHAN (kondisional)
```

Semua skill clawhub yang tidak relevan sudah ter-uninstall (`~/.hermes/skills/<name>` terhapus).

## Rekomendasi
1. Pertahankan `docker-management`. Pertimbangkan lepas `pm2-remote-manager` jika tidak ada server PM2 aktif.
2. Jangan pernah pasang `kaggle` dan `yuyonghao-mcp-client` sampai author perbaiki temuan DANGEROUS.
3. Untuk kebutuhan baru, prioritaskan builtin (`sdlc-review`, `xlsx`, `docx`, `pdf`, `arxiv`) sebelum cari di clawhub.
