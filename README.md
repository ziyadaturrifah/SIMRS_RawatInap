# SIMRS - Modul Rawat Inap

Aplikasi web SIMRS dengan satu modul: **Rawat Inap**. Dibuat dengan Python Flask, SQLAlchemy,
SQLite, dan Bootstrap.

## Cara menjalankan

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
python app.py
```

Buka http://127.0.0.1:5000. Database SQLite dan data contoh dibuat otomatis saat pertama dijalankan
(file `instance/simrs.db`). Hapus file itu bila ingin mengulang dari data contoh.

## Deploy demo online gratis (PythonAnywhere)

PythonAnywhere Beginner menyediakan satu web app gratis. Semua pengguna yang membuka URL web app yang sama akan menggunakan database SQLite online yang sama.

1. Buat akun gratis di [PythonAnywhere](https://www.pythonanywhere.com/registration/register/beginner/) dan konfirmasi email.
2. Buka **Consoles > Bash**, lalu clone repo dan pasang dependensi:

   ```bash
   git clone https://github.com/ziyadaturrifah/SIMRS_RawatInap.git
   cd SIMRS_RawatInap
   mkvirtualenv --python=/usr/bin/python3.13 simrs-venv
   pip install -r requirements.txt
   ```

3. Buka **Web > Add a new web app**, pilih **Manual configuration** dan Python 3.13. Pada bagian **Virtualenv**, isi `/home/<username>/.virtualenvs/simrs-venv`.
4. Pada bagian **Code**, isi **Source code** dan **Working directory** dengan `/home/<username>/SIMRS_RawatInap`.
5. Buka tautan WSGI configuration file di halaman Web. Ganti isinya dengan kode di bawah dan ganti `<username>` dengan username PythonAnywhere:

   ```python
   import os
   import sys

   path = "/home/<username>/SIMRS_RawatInap"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ["SECRET_KEY"] = "ganti-dengan-rahasia-panjang-acak"
   os.environ["SIMRS_ADMIN_PASSWORD"] = "ganti-password-admin"
   os.environ["SIMRS_DOCTOR_PASSWORD"] = "ganti-password-dokter"
   os.environ["SIMRS_NURSE_PASSWORD"] = "ganti-password-perawat"

   from app import app as application
   ```

   Buat nilai rahasia/password sendiri dan jangan unggah atau bagikan isi file WSGI tersebut. Atur sebelum pertama kali membuka aplikasi agar akun demo dibuat dengan password baru.
6. Klik **Reload** pada halaman Web, lalu buka URL yang diberikan PythonAnywhere. Bagikan URL dan kredensial demo kepada teman kelompok melalui jalur pribadi.

Database online dibuat otomatis pada folder proyek dan dipakai bersama oleh aplikasi. SQLite lokal di komputermu tidak ikut dipindahkan. Untuk memperbarui kode, jalankan `git pull` di Bash console lalu klik **Reload**.

**Demo saja:** jangan gunakan data pasien nyata atau informasi kesehatan sensitif. Beginner account memiliki batasan penggunaan; periksa [paket PythonAnywhere](https://www.pythonanywhere.com/pricing/).

## Alternatif deploy demo (Render)

Repo ini juga berisi `render.yaml` untuk membuat web service dan PostgreSQL di Render. Jika akun Render meminta verifikasi kartu, gunakan PythonAnywhere di atas atau ikuti persyaratan akun Render sendiri sebelum melanjutkan. Free web service dapat tidur saat tidak dipakai dan database gratis Render memiliki masa berlaku; cek ketentuan terbaru Render.

Akun contoh:

| Peran   | Username | Password   |
|---------|----------|------------|
| Admin   | admin    | admin123   |
| Dokter  | dokter   | dokter123  |
| Perawat | perawat  | perawat123 |

Kredensial di atas hanya untuk lokal. Saat deploy, atur password kuat melalui WSGI Environment Variables atau Render Environment sebelum database diinisialisasi.

Admin boleh mengelola kamar, bed, dan dokter. Dokter dan perawat mengelola pasien, admisi, catatan,
pindah kamar, dan pemulangan.

## Fitur dan kriteria penilaian

| Kriteria | Yang tersedia |
|---|---|
| Front-end | Dashboard dengan peta bed, tampilan responsif (desktop dan HP), validasi form, pesan kesalahan yang jelas |
| Menu pencarian | Pasien (nama, no. RM, telepon, alamat, penjamin), rawat inap (nama, no. RM, no. rawat, diagnosa, nama kamar, status, dokter), kamar (nama, kelas), dokter (nama, spesialis) |
| Fungsionalitas | Admisi, catatan harian, pindah kamar, pemulangan, hitung biaya otomatis, bed otomatis kosong lagi |
| Integrasi database | 7 tabel berelasi lewat SQLAlchemy |
| Kompleksitas dan kelengkapan | Login dengan peran, perlindungan CSRF, paginasi, riwayat pindah kamar dengan tarif per kamar, BOR di dashboard |

## Alur rawat inap

1. Daftarkan pasien (menu Pasien).
2. Terima pasien: pilih pasien, dokter penanggung jawab, bed kosong, diagnosa awal.
3. Selama dirawat: isi catatan harian (tanda vital, keluhan, instruksi) dan pindahkan kamar bila perlu.
4. Pulangkan pasien: bed kembali kosong, lama rawat dan total biaya kamar tersimpan.

Biaya kamar = jumlah hari di tiap kamar x tarif kamar itu (minimal 1 hari per kamar).

## Struktur database

`user`, `pasien`, `dokter`, `kamar` (1) - (N) `bed`, `rawat_inap`, `riwayat_bed` (menghubungkan rawat inap dan bed),
`catatan` (catatan harian per rawat inap).

## Pakai MySQL (opsional)

1. `pip install PyMySQL` lalu buat database kosong `simrs_rawat_inap`.
2. Atur variabel lingkungan sebelum menjalankan:
   `DATABASE_URL=mysql+pymysql://user:password@localhost/simrs_rawat_inap`

## Upload ke GitHub (satu repository per kelompok)

```bash
git init
git add .
git commit -m "Modul rawat inap awal"
git branch -M main
git remote add origin https://github.com/<akun>/<repo>.git
git push -u origin main
```

Anggota lain: `git clone`, buat branch sendiri, lalu `git pull` sebelum `git push`.

## Struktur folder

```
app.py            model database, route, dan data contoh
templates/        halaman HTML (Jinja2)
static/style.css  tampilan
requirements.txt  daftar library
```
