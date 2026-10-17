---
source: manual (dari root vault)
ingested: 2026-10-02
sha256: e26c529a7adcc836a65940f5f0899af03d2963e971e60f1eb0dfd01761785316
---

# ANNA — Business Intelligence Semantic & Ontology Test Suite

## Tujuan

Test suite ini digunakan untuk menguji kemampuan ANNA dalam:

- memahami semantik bisnis SIMOGE
    
- memahami ontologi dan relasi antar-entitas
    
- memahami dimensi dan metrik
    
- memahami KPI
    
- memahami konteks waktu dan wilayah
    
- melakukan analisis komparatif
    
- melakukan diagnostic reasoning
    
- melakukan spatial reasoning
    
- membedakan fakta, perhitungan, interpretasi, dan hipotesis
    
- menggunakan Business Data Engine tanpa melakukan SQL langsung
    
- mengontrol dashboard dan peta berdasarkan intent operator
    
- menyusun laporan bisnis dari data yang tersedia
    

---

# 0. Entity Recognition

**Tujuan:** Menguji pemahaman terhadap entitas dasar bisnis.

-  `E001` Apa itu petak?
    
-  `E002` Apa itu penyadap?
    
-  `E003` Apa itu andil?
    
-  `E004` Apa itu aktivitas penyadapan?
    
-  `E005` Apa itu rencana aktivitas?
    
-  `E006` Apa itu target produksi?
    
-  `E007` Apa itu TPG?
    
-  `E008` Apa itu RPH?
    
-  `E009` Apa itu BKPH?
    
-  `E010` Apa itu KPH?
    
-  `E011` Apa hubungan antara penyadap dan andil?
    
-  `E012` Apa hubungan antara andil dan petak?
    
-  `E013` Apa hubungan antara rencana aktivitas dan aktivitas?
    
-  `E014` Siapa yang bertanggung jawab terhadap sebuah TPG?
    
-  `E015` Bagaimana hierarki KPH → BKPH → RPH → TPG?
    

---

# 1. Basic Retrieval

**Tujuan:** Menguji kemampuan mengambil informasi bisnis dasar.

-  `R001` Berapa total petak saat ini?
    
-  `R002` Berapa jumlah penyadap aktif?
    
-  `R003` Berapa jumlah TPG?
    
-  `R004` Berapa jumlah petak aktif?
    
-  `R005` Berapa jumlah petak idle?
    
-  `R006` Berapa jumlah petak bongkor?
    
-  `R007` Berapa aktivitas penyadapan pada periode ini?
    
-  `R008` Berapa produksi pada periode ini?
    
-  `R009` Berapa target produksi periode ini?
    
-  `R010` Berapa realisasi produksi periode ini?
    
-  `R011` Berapa luas total petak?
    
-  `R012` Berapa jumlah penyadap pada TPG tertentu?
    
-  `R013` Berapa jumlah petak pada BKPH tertentu?
    
-  `R014` Berapa aktivitas pada RPH tertentu?
    

---

# 2. Filter & Context Semantics

**Tujuan:** Menguji kemampuan menerjemahkan bahasa operator menjadi filter dashboard.

-  `F001` Tampilkan petak bongkor.
    
-  `F002` Tampilkan petak idle.
    
-  `F003` Tampilkan petak aktif.
    
-  `F004` Tampilkan petak bongkor di KPH tertentu.
    
-  `F005` Berapa petak idle di BKPH tertentu?
    
-  `F006` Berapa penyadap aktif di RPH tertentu?
    
-  `F007` Bagaimana kondisi petak di TPG tertentu?
    
-  `F008` Tampilkan aktivitas penyadapan bulan ini.
    
-  `F009` Tampilkan aktivitas penyadapan bulan lalu.
    
-  `F010` Bandingkan kondisi petak P1 dan P2.
    
-  `F011` Tampilkan petak yang belum memiliki penyadap.
    
-  `F012` Tampilkan petak yang memiliki lebih dari satu penyadap.
    
-  `F013` Tampilkan petak yang memiliki andil tetapi belum memiliki aktivitas.
    
-  `F014` Tampilkan petak bongkor beserta lokasinya.
    
-  `F015` Fokuskan peta pada BKPH tertentu.
    
-  `F016` Hilangkan filter wilayah.
    
-  `F017` Tampilkan seluruh KPH.
    

---

# 3. Ontology & Relationship Reasoning

**Tujuan:** Menguji pemahaman hubungan antar-entitas, bukan sekadar nama data.

-  `O001` Jika satu penyadap memiliki beberapa andil, bagaimana hubungan datanya?
    
-  `O002` Jika satu petak memiliki beberapa andil, apa artinya?
    
-  `O003` Jika satu petak memiliki dua penyadap, apakah berarti ada dua petak?
    
-  `O004` Jika seorang penyadap memiliki tiga andil pada petak berbeda, bagaimana menghitung jumlah petaknya?
    
-  `O005` Apa perbedaan jumlah penyadap dengan jumlah andil?
    
-  `O006` Apa perbedaan jumlah andil dengan jumlah petak?
    
-  `O007` Jika jumlah andil lebih besar daripada jumlah petak, apakah itu otomatis masalah?
    
-  `O008` Jika sebuah petak tidak memiliki penyadap tetapi memiliki andil, apa yang perlu diperiksa?
    
-  `O009` Jika penyadap tidak memiliki aktivitas pada periode ini, apakah otomatis tidak aktif?
    
-  `O010` Apakah petak bongkor berarti tidak memiliki penyadap?
    
-  `O011` Apakah petak yang memiliki penyadap pasti memiliki aktivitas?
    
-  `O012` Apakah satu aktivitas berarti satu penyadap?
    
-  `O013` Apakah satu rencana aktivitas dapat memiliki lebih dari satu aktivitas?
    
-  `O014` Mengapa jumlah aktivitas tidak selalu sama dengan jumlah penyadap?
    
-  `O015` Jika jumlah penyadap naik tetapi jumlah petak aktif tetap, apa kemungkinan penjelasannya?
    

---

# 4. KPI Understanding

**Tujuan:** Menguji pemahaman terhadap KPI dan derived metrics.

-  `K001` Berapa realisasi produksi terhadap target?
    
-  `K002` Berapa persentase pencapaian target?
    
-  `K003` Berapa gap antara target dan realisasi?
    
-  `K004` Berapa rata-rata produksi per penyadap?
    
-  `K005` Berapa rata-rata produksi per petak?
    
-  `K006` Berapa rata-rata produksi per andil?
    
-  `K007` Berapa produktivitas masing-masing TPG?
    
-  `K008` Berapa kontribusi masing-masing BKPH terhadap produksi?
    
-  `K009` Berapa kontribusi masing-masing TPG?
    
-  `K010` Berapa persentase petak aktif?
    
-  `K011` Berapa persentase petak idle?
    
-  `K012` Berapa persentase petak bongkor?
    
-  `K013` Berapa persentase petak tanpa penyadap?
    
-  `K014` Berapa rasio penyadap terhadap petak?
    
-  `K015` Berapa rasio andil terhadap petak?
    
-  `K016` Berapa aktivitas rata-rata per penyadap?
    
-  `K017` Berapa produksi per hektare?
    

---

# 5. KPI Semantic Traps

**Tujuan:** Menguji apakah ANNA memahami KPI secara benar dan tidak menyamakan perubahan satu metrik dengan performa keseluruhan.

-  `T001` Jika realisasi naik 10%, apakah performa otomatis membaik?
    
-  `T002` Jika penyadap naik 20% tetapi produksi hanya naik 5%, apa yang terjadi pada produktivitas per penyadap?
    
-  `T003` Jika produksi naik tetapi target naik lebih besar, bagaimana pencapaian target berubah?
    
-  `T004` Jika petak aktif naik tetapi produksi turun, apakah itu kontradiksi?
    
-  `T005` Jika petak bongkor turun, apakah produksi pasti naik?
    
-  `T006` Jika aktivitas meningkat, apakah produksi pasti meningkat?
    
-  `T007` Jika penyadap turun tetapi produksi tetap, bagaimana produktivitas berubah?
    
-  `T008` Jika target turun tetapi realisasi tetap, bagaimana pencapaian target berubah?
    
-  `T009` Apakah pencapaian target dapat meningkat ketika produksi sebenarnya turun?
    
-  `T010` Apa perbedaan growth produksi dengan pencapaian target?
    
-  `T011` Apa perbedaan produktivitas dengan total produksi?
    
-  `T012` Mengapa rata-rata produksi bisa naik sementara total produksi turun?
    
-  `T013` Mengapa total produksi bisa naik sementara produktivitas turun?
    

---

# 6. Temporal Reasoning

**Tujuan:** Menguji pemahaman periode, tren, dan perubahan waktu.

-  `TM001` Bagaimana produksi bulan ini dibanding bulan lalu?
    
-  `TM002` Bagaimana kondisi petak dibanding periode sebelumnya?
    
-  `TM003` Apakah jumlah petak bongkor meningkat atau menurun?
    
-  `TM004` Bagaimana tren aktivitas tiga bulan terakhir?
    
-  `TM005` Apakah produktivitas meningkat sejak awal tahun?
    
-  `TM006` Kapan terjadi perubahan terbesar?
    
-  `TM007` Pada periode mana pencapaian target paling rendah?
    
-  `TM008` Apakah penurunan produksi merupakan perubahan sementara atau bagian dari tren?
    
-  `TM009` Apakah aktivitas bergerak searah dengan produksi?
    
-  `TM010` Apakah peningkatan penyadap diikuti peningkatan produksi?
    
-  `TM011` Periode mana yang menunjukkan anomali?
    
-  `TM012` Apa perubahan KPI terbesar dibanding periode sebelumnya?
    

---

# 7. Comparative Analysis

**Tujuan:** Menguji perbandingan antar dimensi bisnis.

-  `C001` Bandingkan seluruh BKPH berdasarkan produksi.
    
-  `C002` Bandingkan seluruh TPG berdasarkan produktivitas.
    
-  `C003` Bandingkan dua KPH.
    
-  `C004` Bandingkan kondisi petak dua BKPH.
    
-  `C005` Wilayah mana yang memiliki proporsi petak bongkor paling tinggi?
    
-  `C006` Wilayah mana yang memiliki pencapaian target paling rendah?
    
-  `C007` TPG mana yang memiliki produktivitas tinggi tetapi jumlah penyadap rendah?
    
-  `C008` TPG mana yang memiliki banyak penyadap tetapi produktivitas rendah?
    
-  `C009` Apakah wilayah dengan penyadap terbanyak juga menghasilkan produksi terbesar?
    
-  `C010` Apakah wilayah dengan petak aktif terbanyak juga memiliki produktivitas tertinggi?
    

---

# 8. Diagnostic BI

**Tujuan:** Menguji kemampuan mencari indikator yang relevan ketika terjadi perubahan KPI.

-  `D001` Produksi turun. Apa yang perlu saya periksa?
    
-  `D002` Target tercapai tetapi produksi turun. Bagaimana mungkin?
    
-  `D003` Produksi turun tetapi aktivitas naik. Apa yang perlu diperiksa?
    
-  `D004` Penyadap naik tetapi produksi turun. Apa yang perlu diperiksa?
    
-  `D005` Petak aktif meningkat tetapi produktivitas menurun. Apa artinya?
    
-  `D006` Petak bongkor meningkat. KPI apa yang perlu dilihat?
    
-  `D007` Banyak petak tanpa penyadap. Apa dampaknya?
    
-  `D008` TPG memiliki banyak penyadap tetapi produksi rendah. Apa yang perlu dianalisis?
    
-  `D009` TPG memiliki sedikit penyadap tetapi produksi tinggi. Apa yang perlu diperiksa?
    
-  `D010` Mengapa BKPH dapat memiliki produksi tinggi tetapi pencapaian target rendah?
    
-  `D011` Mengapa BKPH dapat memiliki produksi rendah tetapi pencapaian target tinggi?
    
-  `D012` Indikator apa yang mungkin berkaitan dengan penurunan produktivitas?
    

---

# 9. Root Cause Exploration

**Tujuan:** Menguji kemampuan membangun diagnostic tree tanpa mengarang causal relationship.

-  `RC001` Produksi turun 15%. Bantu saya mencari kemungkinan penyebabnya.
    
-  `RC002` Mulai dari KPI utama, indikator apa yang harus diperiksa?
    
-  `RC003` Apakah penurunan produksi terkonsentrasi pada wilayah tertentu?
    
-  `RC004` Apakah penurunan berasal dari jumlah penyadap atau produktivitas?
    
-  `RC005` Apakah aktivitas penyadapan ikut berubah?
    
-  `RC006` Apakah perubahan terjadi pada petak aktif, idle, atau bongkor?
    
-  `RC007` Apakah ada TPG yang menyumbang sebagian besar penurunan?
    
-  `RC008` Apakah penurunan terjadi merata atau hanya pada wilayah tertentu?
    
-  `RC009` Buat diagnostic tree untuk penurunan produksi.
    
-  `RC010` Pisahkan mana fakta dan mana hipotesis.
    

---

# 10. Spatial Intelligence

**Tujuan:** Menguji hubungan antara data numerik dan konteks geografis.

-  `S001` Tampilkan seluruh petak bongkor di peta.
    
-  `S002` Tampilkan petak idle di BKPH tertentu.
    
-  `S003` Tampilkan petak tanpa penyadap.
    
-  `S004` Tampilkan petak dengan lebih dari satu penyadap.
    
-  `S005` Tampilkan petak dengan produktivitas rendah.
    
-  `S006` Wilayah mana yang memiliki konsentrasi petak bongkor tertinggi?
    
-  `S007` Apakah petak bongkor terkonsentrasi pada RPH tertentu?
    
-  `S008` Tampilkan wilayah dengan produksi rendah dan bongkor tinggi.
    
-  `S009` Tampilkan petak dengan aktivitas rendah tetapi target tinggi.
    
-  `S010` Tampilkan TPG dengan pencapaian target rendah di peta.
    
-  `S011` Fokuskan peta pada wilayah dengan masalah yang sedang dianalisis.
    
-  `S012` Jelaskan apa yang terlihat pada peta setelah filter diterapkan.
    
-  `S013` Hubungkan kondisi geografis dengan KPI yang sedang dibahas.
    

---

# 11. Multi-Dimensional Drill Down

**Tujuan:** Menguji kemampuan berpindah antar level ontology.

-  `MD001` Tampilkan kondisi KPH secara keseluruhan.
    
-  `MD002` Drill-down KPH → BKPH → RPH → TPG.
    
-  `MD003` Dari KPH dengan produksi terendah, cari BKPH yang paling berkontribusi terhadap gap.
    
-  `MD004` Dari BKPH tersebut, cari RPH yang paling berkontribusi.
    
-  `MD005` Dari RPH tersebut, cari TPG yang relevan.
    
-  `MD006` Tampilkan petak bermasalah dari TPG tersebut.
    
-  `MD007` Berapa penyadap yang terkait dengan petak tersebut?
    
-  `MD008` Bagaimana aktivitas penyadap tersebut pada periode ini?
    
-  `MD009` Bagaimana kontribusinya terhadap produksi?
    
-  `MD010` Tampilkan seluruh rantai analisis tersebut di dashboard.
    

---

# 12. Executive Intelligence

**Tujuan:** Menguji kemampuan menyusun informasi menjadi laporan bisnis.

-  `EX001` Bagaimana kondisi bisnis saat ini?
    
-  `EX002` Berikan executive summary kondisi KPH saat ini.
    
-  `EX003` Apa hal utama yang perlu diperhatikan?
    
-  `EX004` Apa KPI utama saat ini?
    
-  `EX005` Apa perubahan terbesar dibanding periode sebelumnya?
    
-  `EX006` Apa yang membaik?
    
-  `EX007` Apa yang memburuk?
    
-  `EX008` Wilayah mana yang perlu dianalisis lebih lanjut?
    
-  `EX009` Tampilkan bukti untuk kesimpulan tersebut.
    
-  `EX010` Apa yang belum dapat disimpulkan dari data?
    
-  `EX011` Buatkan laporan kondisi periode ini.
    
-  `EX012` Buatkan laporan untuk KPH tertentu.
    
-  `EX013` Buatkan laporan untuk BKPH tertentu.
    
-  `EX014` Buatkan laporan untuk RPH tertentu.
    
-  `EX015` Buatkan laporan untuk TPG tertentu.
    

---

# 13. Ambiguous Natural Language

**Tujuan:** Menguji kemampuan memahami bahasa operator yang tidak formal.

-  `A001` Gimana kondisi petak sekarang?
    
-  `A002` Ada masalah di mana?
    
-  `A003` Yang merah mana?
    
-  `A004` Coba lihat yang bermasalah.
    
-  `A005` Mana yang perlu diperhatikan?
    
-  `A006` Produksi kita gimana?
    
-  `A007` Kok turun?
    
-  `A008` Yang paling parah di mana?
    
-  `A009` TPG mana yang perlu dicek?
    
-  `A010` Coba bandingkan dengan sebelumnya.
    
-  `A011` Tunjukkan yang aneh.
    
-  `A012` Cari yang tidak normal.
    
-  `A013` Ada yang janggal?
    
-  `A014` Fokus yang produktivitasnya rendah.
    
-  `A015` Coba bedah KPH ini.
    

---

# 14. Semantic Ambiguity

**Tujuan:** Menguji apakah ANNA meminta klarifikasi ketika definisi bisnis tidak cukup jelas.

-  `SA001` Apa maksud "petak tidak aktif"?
    
-  `SA002` Apa maksud "produksi rendah"?
    
-  `SA003` Apa maksud "penyadap bermasalah"?
    
-  `SA004` Apa maksud "TPG terbaik"?
    
-  `SA005` Apa maksud "wilayah terburuk"?
    
-  `SA006` Jika operator mengatakan "yang paling bagus", KPI apa yang digunakan?
    
-  `SA007` Jika operator mengatakan "yang paling parah", bagaimana menentukan kriterianya?
    
-  `SA008` Jika operator meminta "produktivitas rendah", dibandingkan dengan apa?
    
-  `SA009` Jika operator meminta "produksi turun", dibandingkan terhadap periode apa?
    
-  `SA010` Jika operator meminta "masalah", bagaimana menentukan domain masalah?
    

**Expected behavior:**

ANNA tidak boleh membuat definisi sendiri jika konteks tidak cukup.

---

# 15. Data Integrity & Analytical Skepticism

**Tujuan:** Menguji kemampuan mendeteksi data yang tidak layak langsung disimpulkan.

-  `DI001` Jumlah petak tiba-tiba turun 30%. Apakah berarti petak hilang?
    
-  `DI002` Jumlah penyadap tiba-tiba naik dua kali lipat. Apa yang harus diperiksa?
    
-  `DI003` Produksi menjadi nol. Apakah benar produksi nol?
    
-  `DI004` Aktivitas menjadi nol. Apa kemungkinan penyebabnya?
    
-  `DI005` Target menjadi nol. Apakah berarti tidak ada target?
    
-  `DI006` Ada petak tanpa koordinat. Apa dampaknya terhadap analisis peta?
    
-  `DI007` Ada penyadap tanpa andil. Apa yang harus diperiksa?
    
-  `DI008` Ada andil tanpa petak. Apa artinya?
    
-  `DI009` Ada aktivitas tanpa rencana. Apa yang harus diperiksa?
    
-  `DI010` Ada data duplikat. Apakah KPI masih dapat dipercaya?
    
-  `DI011` Data periode sebelumnya berubah setelah sinkronisasi. Bagaimana memperlakukannya?
    
-  `DI012` Apakah data saat ini cukup lengkap untuk membuat kesimpulan?
    

---

# 16. KPI Design

**Tujuan:** Menguji kemampuan berpikir sebagai BI analyst, bukan hanya consumer dashboard.

-  `KD001` KPI apa yang cocok untuk mengukur kesehatan petak?
    
-  `KD002` KPI apa yang cocok untuk mengukur produktivitas penyadap?
    
-  `KD003` KPI apa yang cocok untuk mengukur kinerja TPG?
    
-  `KD004` KPI apa yang cocok untuk mengukur efektivitas aktivitas?
    
-  `KD005` KPI apa yang cocok untuk mengukur pencapaian target?
    
-  `KD006` KPI apa yang dapat menjadi leading indicator?
    
-  `KD007` KPI apa yang merupakan lagging indicator?
    
-  `KD008` KPI apa yang sebaiknya berada di dashboard utama?
    
-  `KD009` KPI apa yang cocok menjadi warning indicator?
    
-  `KD010` Bagaimana membedakan KPI operasional dan KPI strategis?
    

---

# 17. Advanced Business Reasoning

**Tujuan:** Menguji reasoning lintas KPI.

-  `AR001` Produksi meningkat 8%, tetapi produktivitas penyadap turun 6%. Jelaskan kemungkinan yang terjadi.
    
-  `AR002` Petak aktif meningkat 12%, tetapi produksi hanya meningkat 2%. Apa yang perlu diperiksa?
    
-  `AR003` Penyadap berkurang 10%, tetapi produksi meningkat 5%. Apa perubahan KPI yang perlu diperhatikan?
    
-  `AR004` Pencapaian target meningkat dari 85% menjadi 92%, tetapi produksi absolut turun. Bagaimana mungkin?
    
-  `AR005` BKPH A menghasilkan produksi lebih tinggi daripada BKPH B, tetapi produktivitas A lebih rendah. Jelaskan.
    
-  `AR006` TPG A memiliki produksi tertinggi tetapi pencapaian target terendah. Bagaimana mungkin?
    
-  `AR007` TPG B memiliki produksi rendah tetapi produktivitas tinggi. Apa yang perlu diperiksa?
    
-  `AR008` Petak bongkor turun tetapi produksi juga turun. Apakah kedua indikator tersebut bertentangan?
    
-  `AR009` Aktivitas meningkat 30% tetapi produksi hanya meningkat 3%. Apa yang perlu dianalisis?
    
-  `AR010` Jika data mendukung, bagaimana membedakan volume effect, productivity effect, dan mix effect?
    

---

# 18. Business Causality Test

**Tujuan:** Menguji apakah ANNA mampu membedakan korelasi dari sebab-akibat.

-  `CA001` Aktivitas meningkat dan produksi meningkat. Apakah aktivitas menyebabkan produksi meningkat?
    
-  `CA002` Penyadap meningkat dan produksi meningkat. Apakah penambahan penyadap menyebabkan peningkatan produksi?
    
-  `CA003` Bongkor turun dan produksi naik. Apakah penurunan bongkor menyebabkan produksi naik?
    
-  `CA004` Produktivitas turun setelah jumlah petak bertambah. Apakah penambahan petak menyebabkan produktivitas turun?
    
-  `CA005` Jika dua KPI bergerak bersama, apa yang dapat disimpulkan?
    
-  `CA006` Apa bukti tambahan yang diperlukan untuk menyatakan hubungan sebab-akibat?
    

**Expected principle:**

> Correlation is not causation.

ANNA harus menggunakan bahasa seperti:

- "bergerak bersamaan"
    
- "berkorelasi secara observasional"
    
- "perlu diperiksa lebih lanjut"
    
- "belum cukup bukti untuk menyimpulkan sebab-akibat"
    

---

# 19. Full Business Report

**Tujuan:** Menguji kemampuan menghasilkan laporan bisnis lengkap.

-  `BR001` Laporkan kondisi bisnis saat ini.
    
-  `BR002` Laporkan kondisi periode berjalan.
    
-  `BR003` Laporkan kondisi KPH tertentu.
    
-  `BR004` Laporkan kondisi BKPH tertentu.
    
-  `BR005` Laporkan kondisi RPH tertentu.
    
-  `BR006` Laporkan kondisi TPG tertentu.
    
-  `BR007` Buat laporan produksi.
    
-  `BR008` Buat laporan kondisi petak.
    
-  `BR009` Buat laporan aktivitas penyadapan.
    
-  `BR010` Buat laporan produktivitas.
    
-  `BR011` Buat laporan pencapaian target.
    
-  `BR012` Buat laporan dengan peta sebagai pendukung.
    
-  `BR013` Buat laporan lengkap beserta perubahan terhadap periode sebelumnya.
    
-  `BR014` Buat laporan lengkap beserta anomali.
    
-  `BR015` Buat laporan lengkap beserta rekomendasi analisis lanjutan.
    

---

# 20. Conversation Chain Tests

## Chain A — Petak

-  `CH001` Tampilkan petak bongkor.
    
-  `CH002` Berapa jumlahnya?
    
-  `CH003` Di mana paling banyak?
    
-  `CH004` Drill-down.
    
-  `CH005` Cari wilayah penyumbang terbesar.
    
-  `CH006` Tampilkan di peta.
    
-  `CH007` Apa indikator lain yang perlu diperiksa?
    
-  `CH008` Apakah data menunjukkan penyebabnya?
    
-  `CH009` Jika belum, apa hipotesisnya?
    
-  `CH010` Data apa yang diperlukan untuk menguji hipotesis tersebut?
    

---

## Chain B — Produksi

-  `CH011` Bagaimana produksi bulan ini?
    
-  `CH012` Bandingkan dengan bulan lalu.
    
-  `CH013` Kenapa berubah?
    
-  `CH014` Cek aktivitas.
    
-  `CH015` Cek penyadap.
    
-  `CH016` Cek produktivitas.
    
-  `CH017` Cek wilayah.
    
-  `CH018` Drill-down ke TPG.
    
-  `CH019` Tampilkan wilayah terkait di peta.
    
-  `CH020` Buat ringkasan analisis.
    

---

## Chain C — Executive

-  `CH021` Anna, laporkan kondisi KPH saat ini.
    
-  `CH022` Apa masalah utamanya?
    
-  `CH023` Apa buktinya?
    
-  `CH024` Tampilkan di peta.
    
-  `CH025` Drill-down sampai TPG.
    
-  `CH026` Apa yang berubah dibanding periode sebelumnya?
    
-  `CH027` Apa yang membaik?
    
-  `CH028` Apa yang memburuk?
    
-  `CH029` Apa yang belum kita ketahui?
    
-  `CH030` Apa analisis berikutnya yang perlu dilakukan?
    

---

# 21. Ultimate Ontology Test

## `ONT001`

Jelaskan model bisnis SIMOGE yang kamu pahami, mulai dari:

1. struktur wilayah
    
2. KPH
    
3. BKPH
    
4. RPH
    
5. TPG
    
6. penyadap
    
7. andil
    
8. petak
    
9. rencana aktivitas
    
10. aktivitas penyadapan
    
11. target
    
12. produksi
    
13. KPI
    

Jelaskan:

- entity
    
- attribute
    
- relationship
    
- dimension
    
- measure
    
- KPI
    
- derived metric
    

Jangan menyebut nama tabel database kecuali diperlukan.

---

## `ONT002`

Bagaimana kamu menganalisis pertanyaan:

> "Kenapa produksi KPH ini turun?"

Jelaskan:

1. data apa yang diperlukan
    
2. KPI apa yang diperiksa
    
3. dimensi apa yang digunakan
    
4. hubungan entitas yang relevan
    
5. bagaimana melakukan drill-down
    
6. kapan menggunakan peta
    
7. bagaimana membedakan fakta dan hipotesis
    
8. bagaimana menghindari kesimpulan kausal yang tidak didukung data
    

---

## `ONT003`

Jelaskan bagaimana kamu menangani:

> "Ada masalah di KPH ini. Cari tahu."

Jika informasi tersebut ambigu, jelaskan:

1. apa yang belum diketahui
    
2. pertanyaan klarifikasi yang diperlukan
    
3. KPI yang mungkin digunakan
    
4. bagaimana menentukan scope
    
5. bagaimana melakukan diagnostic analysis
    
6. bagaimana mempresentasikan hasilnya
    

---

# 22. Prime Intelligence Test

## `PI001`

Berikan kepada ANNA:

> **"Anna, analisis kondisi bisnis saat ini. Jangan hanya berikan angka. Identifikasi perubahan penting, KPI yang relevan, pola yang terlihat, wilayah yang perlu diperhatikan, kemungkinan anomali, dan hal-hal yang belum dapat disimpulkan. Gunakan dashboard dan peta jika diperlukan. Untuk setiap kesimpulan, bedakan fakta, perhitungan, interpretasi, dan hipotesis."**

---

## `PI002`

Berikan:

> **"Anna, saya tidak tahu masalah bisnisnya apa. Cari sendiri dari data yang tersedia."**

Expected behavior:

```text
Data
 ↓
KPI health check
 ↓
Variance detection
 ↓
Anomaly detection
 ↓
Spatial distribution
 ↓
Drill-down
 ↓
Evidence
 ↓
Interpretation
 ↓
Hypothesis
 ↓
Next investigation
```

ANNA tidak boleh mengarang masalah hanya agar terlihat pintar.

---

# 23. Final Intelligence Test

## `FINAL001`

> **"Anna, lakukan business health assessment untuk kondisi saat ini. Gunakan seluruh konteks yang tersedia. Mulai dari KPI tingkat KPH, identifikasi perubahan signifikan, lakukan drill-down ke BKPH/RPH/TPG bila diperlukan, hubungkan dengan kondisi penyadap, andil, petak dan aktivitas, kemudian gunakan peta untuk menunjukkan lokasi yang relevan. Bedakan dengan jelas fakta, derived metrics, comparison, interpretation, dan hypothesis. Jika data tidak cukup untuk menyimpulkan sesuatu, katakan secara eksplisit apa yang kurang."**

---

# Expected Intelligence Model

ANNA seharusnya mengikuti pola:

```text
Operator Intent
       ↓
Context Understanding
       ↓
Business Ontology
       ↓
Semantic Interpretation
       ↓
Business Data Engine
       ↓
Evidence
       ↓
Metric Calculation
       ↓
Comparison
       ↓
Diagnostic Reasoning
       ↓
Spatial Reasoning
       ↓
Interpretation
       ↓
Hypothesis
       ↓
Presentation
```

---

# Evidence Discipline

Setiap jawaban faktual harus dapat ditelusuri ke:

```text
KPI Evidence
       atau
Named Business Tool Result
```

ANNA harus membedakan:

### FACT

Data yang langsung tersedia.

### DERIVED METRIC

Nilai yang dihitung dari data yang tersedia.

### COMPARISON

Perbandingan dua atau lebih periode/dimensi.

### INTERPRETATION

Makna bisnis yang diberikan terhadap fakta.

### HYPOTHESIS

Kemungkinan penjelasan yang belum terbukti.

Contoh:

```text
FACT:
Produksi turun 8%.

DERIVED:
Pencapaian target turun dari 94% menjadi 87%.

COMPARISON:
Penurunan terbesar berasal dari BKPH X.

INTERPRETATION:
Perubahan produksi terkonsentrasi pada wilayah tersebut.

HYPOTHESIS:
Perubahan aktivitas atau produktivitas mungkin berkaitan
dengan penurunan tersebut.

EVIDENCE NEEDED:
Data aktivitas dan produktivitas pada periode pembanding.
```

---

# Forbidden Behavior

ANNA dinyatakan **FAIL** apabila melakukan salah satu hal berikut:

-  Mengarang angka.
    
-  Menganggap data kosong sebagai `0`.
    
-  Membuat KPI dari data yang tidak tersedia.
    
-  Mengarang business rule.
    
-  Mengarang hubungan antar-entitas.
    
-  Menganggap petak = andil.
    
-  Menganggap penyadap = andil.
    
-  Menganggap aktivitas = produksi.
    
-  Menganggap korelasi = kausalitas.
    
-  Menggunakan SQL langsung.
    
-  Mengakses database secara langsung.
    
-  Menggunakan raw GeoJSON untuk menjawab permintaan map.
    
-  Mengklaim sesuatu sebagai fakta tanpa evidence.
    
-  Menyembunyikan data yang tidak tersedia.
    
-  Memberikan kesimpulan pasti ketika evidence hanya mendukung hipotesis.
    
-  Menentukan "terbaik/terburuk" tanpa definisi KPI yang jelas.
    
-  Menggunakan ranking ketika denominator atau population berbeda secara material.
    
-  Mengabaikan filter/periode yang sedang aktif.
    
-  Mengubah konteks wilayah tanpa memberitahu operator.
    

---

# Scoring Framework

Gunakan skala:

|Score|Meaning|
|--:|---|
|`0`|Tidak memahami / salah total|
|`1`|Memahami sebagian tetapi salah secara bisnis|
|`2`|Jawaban benar tetapi dangkal|
|`3`|Benar + konteks tepat|
|`4`|Benar + reasoning + evidence|
|`5`|Benar + reasoning + evidence + proaktif menemukan insight|

## Dimensi Penilaian

|Dimensi|Weight|
|---|--:|
|Entity Semantics|10%|
|Ontology & Relationships|15%|
|KPI Semantics|15%|
|Temporal Reasoning|10%|
|Spatial Reasoning|10%|
|Analytical Reasoning|15%|
|Evidence Discipline|15%|
|Operator / Dashboard Interaction|10%|
|**Total**|**100%**|

---

# Test Result Template

Untuk setiap test, catat:

```text
Test ID:
Question:

Expected Intent:

Expected Entities:

Expected Filters:

Expected KPI:

Expected Tool:

Expected Map Action:

Expected Evidence:

Expected Reasoning:

ANNA Response:

Score:
0 / 1 / 2 / 3 / 4 / 5

Failure Type:

Notes:
```

---

# Minimum Acceptance Criteria

ANNA belum dianggap memiliki Business Intelligence reasoning yang memadai apabila:

- entity semantics benar tetapi relationship salah
    
- KPI dapat disebutkan tetapi tidak dapat dijelaskan
    
- mampu mengambil angka tetapi tidak memahami denominator
    
- mampu menjawab tetapi tidak memahami periode
    
- mampu melakukan filter tetapi kehilangan context
    
- mampu melihat korelasi tetapi menyebutnya sebagai sebab
    
- mampu membuat laporan tetapi tidak dapat menunjukkan evidence
    
- mampu menemukan anomaly tetapi tidak dapat melakukan drill-down
    
- mampu menggunakan map tetapi tidak dapat menghubungkan map dengan KPI
    
- mampu menjawab pertanyaan tetapi tidak dapat menjelaskan keterbatasan data
    

Target akhir:

```text
ANNA bukan sekadar:

"AI yang bisa membaca dashboard."

ANNA harus menjadi:

"AI yang memahami model bisnis,
memahami konteks data,
memahami KPI,
mampu melakukan drill-down,
mampu menghubungkan data dengan ruang,
mampu menemukan pola,
dan mampu menjelaskan apa yang diketahui
serta apa yang belum diketahui."
```