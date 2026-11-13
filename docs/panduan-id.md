# Panduan CheckMyLaptop

CheckMyLaptop memeriksa laptop Windows dengan satu klik. Aplikasi membaca data yang tersedia, mengurutkan temuan berdasarkan prioritas, dan menyarankan langkah pemeriksaan berikutnya.

1. Buka [Releases](https://github.com/raiju365/CheckMyLaptop/releases) dan unduh `CheckMyLaptop.exe` jika tersedia. Dari folder source, instal Python 3.11 atau lebih baru, lalu klik dua kali `CheckMyLaptop.cmd`.
2. Buka aplikasi dan klik **Scan laptop**. Gunakan akun Windows biasa.
3. Baca hasil **High** terlebih dahulu. Setiap temuan mencantumkan bukti dan tindakan berikutnya.
4. Periksa **Scan coverage**. Status **Partial** berarti hanya sebagian data berhasil terbaca. **Unavailable** berarti data pemeriksaan tersebut tidak tersedia.
5. Gunakan **Save report** untuk menyimpan laporan TXT atau JSON. Baca dulu laporannya sebelum dibagikan ke teknisi.

Aplikasi berfungsi sebagai pemeriksaan awal. Temuan membantu menentukan apa yang perlu diperiksa berikutnya. Gunakan diagnostik produsen atau bantuan teknisi untuk mengonfirmasi kerusakan sebelum mengganti komponen. Jika ada peringatan penyimpanan yang menyarankan pencadangan, dahulukan pencadangan file penting.

Pemeriksaan ini berjalan di laptopmu tanpa koneksi internet. Aplikasi tidak memperbaiki perangkat atau mengubah pengaturan Windows. Fitur yang memerlukan tes fisik, seperti layar, keyboard, kipas dan setiap port, belum diuji oleh versi ini.
