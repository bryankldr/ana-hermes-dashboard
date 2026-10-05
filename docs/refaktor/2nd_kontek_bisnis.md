perlu kamu ketahui, hubungan antara database,
- getah_penyadap dengan  getah_andil menggunakan id_penyadap, getah_andil dengan  getah_petak dan petak_polygon di hubungkan dengan kolom kode_evapot. 
- di semua tabel di database memiliki kode_divre, kode_kph, kode_bkph, kode_rph, kode_tpg
- untuk getah_rencana_aktivitas dengan getah_aktivitas_sadap menggunakan id_rencana, dari getah_rencana_aktivitas, getah_aktivitas_sadap ke getap penyadap menggunakan id_penyadap, dan bisa juga di hubungkan ke getah_aktivitas_penerimaan melalui id_penyadap,
- di getah_drum jangan gunakan id_penyadap, karna sumber data berasal dari getah_aktivitas_penerimaan yang terhubung melalui nomor_drum, 
- getah_drum juga berhubungan dengan getah_pengangkutan melalui nomor_pengangkutan
- gettah_drum berhubungan dengan getah_perni dengan nomor_perni.
- getah_drum berhubungan dengan getah_mutu melalui id_mutu
- getah_target_ro_nps memiliki kolom tahun yang digunakan untuk filter tahun seperti di getah_petak,


- implementasi Target RO dan NPS : di tabel getah_target_ro_nps gunakan kolom bulan 1 adalah januari, 2 adalah februari dan seterusnya, di kolom ro_periode_1, ro_periode_2, nps_periode_1, nps_periode_2 adalah breakdown persen target yang harus dicapai per periode dikalikan target_rkap dari tabel getah_petak per masing masing petak
misal : target RO nomor_Petak 28 C3 periode 1 bulan 1 tahun 2026 adalah 3,5 % maka dikalikan target_rkap petak 697,6 Kg = 24,4 Kg, Target NPS nomor_Petak 28 C3 periode 2 bulan 5 tahun 2026 adalah 4 % dikalikan taarget_rkap 697,6 Kg = 27,9 Kg
- implementasi periode : Periode 1 =  (tanggal 1 - 15) Periode 2 = Tanggal 16 - akhir bulan)
- pertanyaan bisnis tentang periode biasanya, P1 saat ini berarti periode 1 bulan ini tahun ini begitupun juga P2, kalau pertanyaan P1 / P2 sampai dengan berarti P1 bulan 1 tahun ini sampai dengan P1 / P2 bulan ini tahun ini  akan di jumlahkan, kalau sampai dengan saja berarti semua mulai tanggal 1 hingga saat ini,
- untuk pertanyaan petak BONGKOR berarti petak yang tidak ada penyadapnya sama sekali, kalu pertanyaan andil BONGKOR adalah andil yang tidak ada aktivitasnya sama sekali selama 2 bulan lebih, untuk petak IDLE / andil IDLE adalah petak / andil yang periode lalu ada aktivitasnya namun periode saat ini tidak ada aktivitasnya. untuk petak / andil AKTIV adalah petak / andil yang ada aktivitasnya,  
- kode pewarnaan polygon efektivitas petak : untuk petak yang tidak ada penyadapnya berwarna merah, petak yang total luas_andil nnya < luas_baku petak berwarna kuning, petak yang luas_andilnya mendekati / sama / lebih dari luas_baku petak berwarna hijau, 
- kode pewarnaan polygon Pencapaian target RKAP petak sesuai periode : pencapaian 0 - 25 % berwarna merah, pencapaian 26 - 50 % berwarna oranye, pencapaian 51- 75 % berwarna kuning, pencapaian 76 - 100 % berwarna hijau, diatas 100 % berwarna emas,
-  kategori penyadap kurang produktiv adalah penyadap  aktiv  namun kurang produktif adalah banyak aktivitasnya namun penerimaannya di bawah target dengan perhitungan luas baku dari petak  luas_andil dari andil di rasio berapa % lalu di bandingkan dengan target periode RO / nps target_rkap pada petak sesuai periode, dan di hitung berat_penerimaan < dari target .
- analisa efektivitas petak 1 : luas_baku petak di bandingkan dengan total luas_andil pada andil yang terhubung dengan petak tersebut dapat di simpulkan ada bahwa petak tersebut membutuhkan penyadap / tidak.
- analisa efektivitas petak 2 : matrik luas_andil, jml_pohon pada getah_andil dengan luas_baku, jumlah_pohon pada getah_petak

pastikan nama kolom benar