// scripts/build_ui.mjs — bundel + minify UI untuk produksi.
// Tujuan: kurangi keterbacaan santai di DevTools (bukan pengamanan) dan
// hilangkan console.* dari bundel. Sumber tetap di ui/src/ (tetap satu-satunya
// sumber kebenaran); hasil build di ui/dist/ dan TIDAK di-commit.
//
// Pakai:  npm run build:ui        → ui/dist/app.min.js
// Aktifkan di server: ANA_UI_BUNDLE=1 (server menyajikan bundel untuk /src/main.js)
import { build } from "esbuild";
import { statSync } from "node:fs";

const out = "ui/dist/app.min.js";
const t0 = Date.now();
const res = await build({
  entryPoints: ["ui/src/main.js"],
  outfile: out,
  bundle: true,
  format: "esm",
  target: ["es2020"],
  minify: true,
  sourcemap: false,
  legalComments: "none",
  drop: ["console"],          // buang console.* dari bundel produksi
  loader: { ".css": "empty" },
  logLevel: "warning",
  metafile: false,
});
if (res.errors.length) { console.error("BUILD GAGAL", res.errors); process.exit(1); }
const kb = (statSync(out).size / 1024).toFixed(1);
console.log(`ok: ${out} ${kb} kB dalam ${Date.now() - t0} ms`);
