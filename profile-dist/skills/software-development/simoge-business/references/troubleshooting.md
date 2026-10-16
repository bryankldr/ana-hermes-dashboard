# Troubleshooting — CLI & Patch Pitfalls

## Jalur aman: CLI langsung, BUKAN python3 -c
`terminal` memblokir `python3 -c "..."` multi-baris (fail-closed). Pola lolos:
```bash
python3 ~/.hermes/profiles/anna/skills/software-development/simoge-business/scripts/ana_simoge_tool.py aktivitas_agregat tahun=2026 bulan=6 periode=0 grup_by=pembaharuan
python3 .../ana_simoge_tool.py aktivitas_top_petak tahun=2026 bulan=6 periode=0 limit=10 > /tmp/x.json && read_file /tmp/x.json
```
JANGAN `python3 -c`, JANGAN pipa python→python. Arg `key=value`, numerik auto int. `workdir` = `ANA_WORKDIR` (`.env`) di mesin tsb — jangan hardcode home. Resolve via `pathlib.Path(__file__).resolve().parents` atau `$ANA_WORKDIR`.

## Aki memotong pesan
Jangan `--select`/file 1-2 baris untuk multi-baris — `\n` terpotong. Pakai `2>&1 | tail -30` (handler), `| tail -5` (JSON).

## Pitfall patch menyisipkan karakter asing
Edit merusak f-string sekitar sisip (`f"..." _fmt_num(x)` → SyntaxError). Aturan: tiap patch `ast.parse` + sapu char asing. Fix pakai patch terarah, bukan `re.sub` global.

## Verify the call
`show_on_map` wajib return dict `{ok,features,spatial_id}`. `None`/falsy = broken — stop, jangan fallback chart. Cek: `r=show_on_map(...); print(type(r).__name__, r.get("features"), r.get("spatial_id"))`. `row_count` (DB rows) vs `features` (polygon ter-parse) beda 1 wajar.

## Pitfall helper di dalam function
`def` kolom-0 akhiri body enclosing — text di bawah dead code setelah `return` helper. `py_compile` lolos tapi return `None`. Define helper di module level.

## PATH LITERAL
`SKILL.md` tulis path lengkap. 3 salinan lama pernah ada — sekarang symlink. `find` >1 = bug.

## Token retry
`show_on_map`/`_post_show` resolve token fresh tiap call (`ANA_TOKEN` env atau `.ana_token`), retry 1x saat 401 bila env kosong — tutup race restart-mid-call.


## Pitfall: loop ana_kpi boros
`search_files ana_kpi` → `read_file ana_kpi.py` → `for y,m,p in loop: get_production_kpi` = 18 call, token 150K. Ganti 1× `call_pandas_tool(..., operations=[percentage_change])` atau 2× `call_simoge_packet`. SKILL 1.3.1 sudah contoh trend.

## Chart 401 walau token benar — sid salah
`POST /api/spatial/chart` berdata menolak `401 chart berisi data wajib push lewat sesi user login` bila header `X-Hermes-Session` tidak resolve ke user: kirim `HERMES_SESSION_ID` = isi `.ana_current_sid` (sid live dashboard, mis. `fa8526e0`), BUKAN `HERMES_SESSION_ID` bawaan env terminal agen yang beda. Pola CLI: `HERMES_SESSION_ID=$(cat $ANA_WORKDIR/.ana_current_sid | awk '{print $1}') PYTHONPATH=<scripts> python3 <scripts>/ana_chart_tool.py show ...`. Verifikasi: `cat .ana_current_sid` lalu `cat .ana_scope_<sid>.json` wajib memuat `user_id` non-kosong; bila file scope tak ada = sid basi, baca ulang `.ana_current_sid`.
