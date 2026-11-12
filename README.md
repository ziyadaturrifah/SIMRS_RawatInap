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

Akun contoh:

| Peran   | Username | Password   |
|---------|----------|------------|
| Admin   | admin    | admin123   |
| Dokter  | dokter   | dokter123  |
| Perawat | perawat  | perawat123 |

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
