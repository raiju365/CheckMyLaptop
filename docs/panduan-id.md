# Panduan CheckMyLaptop

CheckMyLaptop memeriksa laptop Windows setelah kamu memberi izin. Aplikasi membaca data yang tersedia, menghubungkan temuan yang berkaitan, dan menyarankan langkah pemeriksaan berikutnya.

1. Buka [Releases](https://github.com/raiju365/CheckMyLaptop/releases), unduh `CheckMyLaptop-Windows-x64.zip` jika tersedia, lalu ekstrak seluruh folder sebelum membuka `CheckMyLaptop.exe`. Dari folder source, instal Python 3.11 atau lebih baru, lalu klik dua kali `CheckMyLaptop.cmd`.
2. Buka aplikasi, klik **Scan laptop**, lalu setujui dialog izin untuk mulai. Di terminal, ketik `ALLOW` saat diminta atau jalankan `py -3 -m checkmylaptop --cli --allow`.
3. Baca **Diagnostic summary** untuk melihat bukti yang saling menguatkan dan langkah pemeriksaan berikutnya. Di **Measured performance**, kamu bisa melihat RAM tersedia, penggunaan memori committed, serta lima kelompok proses dengan penggunaan RAM terbesar di akhir scan. Angka per kelompok dapat mencakup memori yang dipakai bersama.
4. Periksa **Scan coverage**. Status **Partial** berarti hanya sebagian data berhasil terbaca. **Unavailable** berarti data pemeriksaan tersebut tidak tersedia.
5. Gunakan **Save report** untuk menyimpan laporan TXT atau JSON. Baca dulu laporannya sebelum dibagikan ke teknisi.

Aplikasi berfungsi sebagai pemeriksaan awal. Temuan membantu menentukan apa yang perlu diperiksa berikutnya. Gunakan diagnostik produsen atau bantuan teknisi untuk mengonfirmasi kerusakan sebelum mengganti komponen. Jika ada peringatan penyimpanan yang menyarankan pencadangan, dahulukan pencadangan file penting.

Untuk verifikasi komponen Windows secara menyeluruh, buka aplikasi dengan **Run as administrator**, centang **Verify Windows components**, lalu beri izin scan. Verifikasi bisa berjalan hingga 15 menit dan Windows dapat menulis log servis. Pemeriksaan tetap berjalan lokal tanpa mengirim laporan atau menjalankan perbaikan.

Sensor langsung CPU/GPU dan kipas, tes stabilitas, serta fungsi fisik layar, keyboard dan tiap port perlu diuji terpisah.
