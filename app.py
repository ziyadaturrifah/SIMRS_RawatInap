"""SIMRS - Modul Rawat Inap (Flask + SQLAlchemy).

Jalankan:  python app.py   ->  http://127.0.0.1:5000
Database SQLite dibuat otomatis di folder instance/ beserta data contoh.
"""
import os
import secrets
from datetime import date, datetime, time, timedelta
from functools import wraps
from urllib.parse import urlsplit, urlunsplit

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   session, url_for)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import case, func, or_
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
database_url = os.environ.get("DATABASE_URL", "sqlite:///simrs.db")
if database_url.startswith(("postgres://", "postgresql://")):
    parsed_database_url = urlsplit(database_url)
    database_url = urlunsplit((
        "postgresql+psycopg",
        parsed_database_url.netloc,
        parsed_database_url.path,
        parsed_database_url.query,
        parsed_database_url.fragment,
    ))
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "ganti-ini-sebelum-dikumpulkan"),
    # Untuk MySQL: "mysql+pymysql://user:password@localhost/simrs_rawat_inap"
    SQLALCHEMY_DATABASE_URI=database_url,
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db = SQLAlchemy(app)

KELAS = ["VIP", "Kelas 1", "Kelas 2", "Kelas 3"]
PENJAMIN = ["Umum", "BPJS", "Asuransi"]
GOL_DARAH = ["-", "A", "B", "AB", "O"]
CARA_PULANG = ["Sembuh", "Membaik", "Dirujuk",
               "Pulang atas permintaan sendiri", "Meninggal"]
BULAN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
         "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
NAMA_HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]


# --------------------------------------------------------------------------
# Model database
# --------------------------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(40), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    nama = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin / dokter / perawat


class Pasien(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    no_rm = db.Column(db.String(20), unique=True, nullable=False)
    nama = db.Column(db.String(120), nullable=False)
    jenis_kelamin = db.Column(db.String(1), nullable=False)  # L / P
    tgl_lahir = db.Column(db.Date, nullable=False)
    alamat = db.Column(db.String(255))
    telepon = db.Column(db.String(30))
    gol_darah = db.Column(db.String(2), default="-")
    penjamin = db.Column(db.String(20), default="Umum")
    rawat = db.relationship("RawatInap", back_populates="pasien",
                            order_by="RawatInap.tgl_masuk.desc()")

    @property
    def umur(self):
        t = date.today()
        return t.year - self.tgl_lahir.year - (
            (t.month, t.day) < (self.tgl_lahir.month, self.tgl_lahir.day))

    @property
    def rawat_aktif(self):
        return next((r for r in self.rawat if r.status == "dirawat"), None)


class Dokter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(120), nullable=False)
    spesialis = db.Column(db.String(80), nullable=False)
    rawat = db.relationship("RawatInap", back_populates="dokter")


class Kamar(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nama = db.Column(db.String(60), unique=True, nullable=False)
    kelas = db.Column(db.String(20), nullable=False)
    tarif = db.Column(db.Integer, nullable=False)  # rupiah per hari
    beds = db.relationship("Bed", back_populates="kamar", order_by="Bed.nomor",
                           cascade="all, delete-orphan")


URUTAN_KELAS = case({k: i for i, k in enumerate(KELAS)}, value=Kamar.kelas, else_=99)


class Bed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kamar_id = db.Column(db.Integer, db.ForeignKey("kamar.id"), nullable=False)
    nomor = db.Column(db.Integer, nullable=False)
    kamar = db.relationship("Kamar", back_populates="beds")
    riwayat = db.relationship("RiwayatBed", back_populates="bed")

    @property
    def aktif(self):
        """Riwayat bed yang sedang berjalan (bed terisi) atau None (kosong)."""
        return next((r for r in self.riwayat if r.selesai is None), None)

    @property
    def label(self):
        return f"{self.kamar.nama} / Bed {self.nomor}"


class RawatInap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    no_rawat = db.Column(db.String(30), unique=True, nullable=False)
    pasien_id = db.Column(db.Integer, db.ForeignKey("pasien.id"), nullable=False)
    dokter_id = db.Column(db.Integer, db.ForeignKey("dokter.id"), nullable=False)
    tgl_masuk = db.Column(db.DateTime, nullable=False)
    tgl_keluar = db.Column(db.DateTime)
    diagnosa_awal = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(10), nullable=False, default="dirawat")
    cara_pulang = db.Column(db.String(60))
    ringkasan_pulang = db.Column(db.Text)
    total_biaya = db.Column(db.Integer)  # terisi saat pasien pulang
    pasien = db.relationship("Pasien", back_populates="rawat")
    dokter = db.relationship("Dokter", back_populates="rawat")
    riwayat_bed = db.relationship("RiwayatBed", back_populates="rawat",
                                  order_by="RiwayatBed.mulai",
                                  cascade="all, delete-orphan")
    catatan = db.relationship("Catatan", back_populates="rawat",
                              order_by="Catatan.waktu.desc()",
                              cascade="all, delete-orphan")

    @property
    def bed_sekarang(self):
        return next((r.bed for r in self.riwayat_bed if r.selesai is None), None)

    @property
    def lama_rawat(self):
        akhir = self.tgl_keluar or datetime.now()
        return max(1, (akhir.date() - self.tgl_masuk.date()).days)

    @property
    def biaya_kamar(self):
        if self.status == "pulang" and self.total_biaya is not None:
            return self.total_biaya
        return sum(r.biaya for r in self.riwayat_bed)


class RiwayatBed(db.Model):
    """Satu baris per bed yang pernah ditempati (mendukung pindah kamar)."""
    id = db.Column(db.Integer, primary_key=True)
    rawat_id = db.Column(db.Integer, db.ForeignKey("rawat_inap.id"), nullable=False)
    bed_id = db.Column(db.Integer, db.ForeignKey("bed.id"), nullable=False)
    mulai = db.Column(db.DateTime, nullable=False)
    selesai = db.Column(db.DateTime)
    tarif = db.Column(db.Integer, nullable=False)  # salinan tarif saat masuk bed
    rawat = db.relationship("RawatInap", back_populates="riwayat_bed")
    bed = db.relationship("Bed", back_populates="riwayat")

    @property
    def hari(self):
        akhir = self.selesai or datetime.now()
        return max(1, (akhir.date() - self.mulai.date()).days)

    @property
    def biaya(self):
        return self.hari * self.tarif


class Catatan(db.Model):
    """Catatan perkembangan harian / visite."""
    id = db.Column(db.Integer, primary_key=True)
    rawat_id = db.Column(db.Integer, db.ForeignKey("rawat_inap.id"), nullable=False)
    waktu = db.Column(db.DateTime, nullable=False, default=datetime.now)
    penulis_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    suhu = db.Column(db.Float)
    tekanan_darah = db.Column(db.String(10))
    nadi = db.Column(db.Integer)
    keluhan = db.Column(db.Text)
    instruksi = db.Column(db.Text)
    rawat = db.relationship("RawatInap", back_populates="catatan")
    penulis = db.relationship("User")


# --------------------------------------------------------------------------
# Helper, filter template, keamanan
# --------------------------------------------------------------------------
@app.template_filter("rupiah")
def rupiah(v):
    return "Rp" + f"{int(v or 0):,}".replace(",", ".")


@app.template_filter("tgl")
def tgl(d):
    return f"{d.day} {BULAN[d.month - 1]} {d.year}" if d else "-"


@app.template_filter("tglwaktu")
def tglwaktu(d):
    return f"{d.day} {BULAN[d.month - 1]} {d.year}, {d:%H:%M}" if d else "-"


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


app.jinja_env.globals["csrf_token"] = csrf_token


@app.before_request
def muat_user():
    uid = session.get("user_id")
    g.user = db.session.get(User, uid) if uid else None


@app.before_request
def lindungi_csrf():
    if request.method == "POST":
        token = session.get("_csrf")
        if not token or token != request.form.get("_csrf"):
            abort(400)


@app.context_processor
def sisipkan_konteks():
    return dict(user=getattr(g, "user", None), KELAS=KELAS, PENJAMIN=PENJAMIN,
                GOL_DARAH=GOL_DARAH, CARA_PULANG=CARA_PULANG, today=date.today().isoformat())


def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if not g.user:
            return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return wrapper


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **k):
        if g.user.role != "admin":
            abort(403)
        return f(*a, **k)
    return wrapper


def parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_dt(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return None


def dt_input(d):
    return d.strftime("%Y-%m-%dT%H:%M")


def kamar_tersedia():
    """[(kamar, [bed kosong, ...])] hanya kamar yang masih punya bed kosong."""
    hasil = []
    for k in Kamar.query.order_by(URUTAN_KELAS, Kamar.nama).all():
        kosong = [b for b in k.beds if b.aktif is None]
        if kosong:
            hasil.append((k, kosong))
    return hasil


def buat_no_rawat():
    prefix = f"RI-{date.today():%Y%m%d}-"
    n = RawatInap.query.filter(RawatInap.no_rawat.like(prefix + "%")).count()
    return f"{prefix}{n + 1:03d}"


def buat_no_rm():
    maks = db.session.query(func.max(Pasien.id)).scalar() or 0
    return f"RM-{maks + 1:06d}"


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if u and check_password_hash(u.password_hash, request.form.get("password", "")):
            session.clear()
            session["user_id"] = u.id
            nxt = request.args.get("next", "")
            if nxt.startswith("/") and not nxt.startswith("//"):
                return redirect(nxt)
            return redirect(url_for("dashboard"))
        flash("Username atau password salah. Periksa lagi lalu coba masuk.", "danger")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    total_bed = Bed.query.count()
    terisi = RiwayatBed.query.filter(RiwayatBed.selesai.is_(None)).count()
    awal_hari = datetime.combine(date.today(), time.min)
    hari = date.today()
    return render_template(
        "dashboard.html",
        total_bed=total_bed,
        dirawat=terisi,
        bed_kosong=total_bed - terisi,
        bor=round(terisi / total_bed * 100) if total_bed else 0,
        masuk_hari_ini=RawatInap.query.filter(RawatInap.tgl_masuk >= awal_hari).count(),
        pulang_hari_ini=RawatInap.query.filter(RawatInap.tgl_keluar >= awal_hari).count(),
        kamar=Kamar.query.order_by(URUTAN_KELAS, Kamar.nama).all(),
        terbaru=RawatInap.query.filter_by(status="dirawat")
        .order_by(RawatInap.tgl_masuk.desc()).limit(6).all(),
        tanggal_teks=f"{NAMA_HARI[hari.weekday()]}, {hari.day} {BULAN[hari.month - 1]} {hari.year}",
    )


# --------------------------------------------------------------------------
# Pasien
# --------------------------------------------------------------------------
@app.route("/pasien")
@login_required
def pasien_list():
    q = request.args.get("q", "").strip()
    penjamin = request.args.get("penjamin", "")
    page = request.args.get("page", 1, type=int)
    query = Pasien.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Pasien.nama.ilike(like), Pasien.no_rm.ilike(like),
                                 Pasien.telepon.ilike(like), Pasien.alamat.ilike(like)))
    if penjamin in PENJAMIN:
        query = query.filter(Pasien.penjamin == penjamin)
    pagination = query.order_by(Pasien.nama).paginate(page=page, per_page=10, error_out=False)
    return render_template("pasien_list.html", pagination=pagination, q=q, penjamin=penjamin)


def _validasi_pasien(f):
    errors = []
    if not f.get("nama", "").strip():
        errors.append("Nama pasien wajib diisi.")
    if f.get("jenis_kelamin") not in ("L", "P"):
        errors.append("Pilih jenis kelamin pasien.")
    lahir = parse_date(f.get("tgl_lahir"))
    if not lahir or lahir > date.today():
        errors.append("Tanggal lahir tidak valid.")
    return errors, lahir


def _isi_pasien(p, f, lahir):
    p.nama = f["nama"].strip()
    p.jenis_kelamin = f["jenis_kelamin"]
    p.tgl_lahir = lahir
    p.alamat = f.get("alamat", "").strip()
    p.telepon = f.get("telepon", "").strip()
    p.gol_darah = f.get("gol_darah") if f.get("gol_darah") in GOL_DARAH else "-"
    p.penjamin = f.get("penjamin") if f.get("penjamin") in PENJAMIN else "Umum"


@app.route("/pasien/baru", methods=["GET", "POST"])
@login_required
def pasien_baru():
    if request.method == "POST":
        errors, lahir = _validasi_pasien(request.form)
        if not errors:
            p = Pasien(no_rm=buat_no_rm())
            _isi_pasien(p, request.form, lahir)
            db.session.add(p)
            db.session.commit()
            flash(f"Pasien {p.nama} tersimpan dengan nomor {p.no_rm}.", "success")
            return redirect(url_for("pasien_detail", id=p.id))
        for e in errors:
            flash(e, "danger")
    return render_template("pasien_form.html", pasien=None, form=request.form)


@app.route("/pasien/<int:id>")
@login_required
def pasien_detail(id):
    return render_template("pasien_detail.html", pasien=db.get_or_404(Pasien, id))


@app.route("/pasien/<int:id>/ubah", methods=["GET", "POST"])
@login_required
def pasien_ubah(id):
    p = db.get_or_404(Pasien, id)
    if request.method == "POST":
        errors, lahir = _validasi_pasien(request.form)
        if not errors:
            _isi_pasien(p, request.form, lahir)
            db.session.commit()
            flash("Data pasien diperbarui.", "success")
            return redirect(url_for("pasien_detail", id=p.id))
        for e in errors:
            flash(e, "danger")
        return render_template("pasien_form.html", pasien=p, form=request.form)
    form = dict(nama=p.nama, jenis_kelamin=p.jenis_kelamin,
                tgl_lahir=p.tgl_lahir.isoformat(), alamat=p.alamat, telepon=p.telepon,
                gol_darah=p.gol_darah, penjamin=p.penjamin)
    return render_template("pasien_form.html", pasien=p, form=form)


@app.route("/pasien/<int:id>/hapus", methods=["POST"])
@admin_required
def pasien_hapus(id):
    p = db.get_or_404(Pasien, id)
    if p.rawat:
        flash("Pasien yang punya riwayat rawat inap tidak bisa dihapus.", "danger")
        return redirect(url_for("pasien_detail", id=id))
    db.session.delete(p)
    db.session.commit()
    flash("Data pasien dihapus.", "success")
    return redirect(url_for("pasien_list"))


# --------------------------------------------------------------------------
# Kamar & bed
# --------------------------------------------------------------------------
@app.route("/kamar")
@login_required
def kamar_list():
    q = request.args.get("q", "").strip()
    kelas = request.args.get("kelas", "")
    query = Kamar.query
    if q:
        query = query.filter(Kamar.nama.ilike(f"%{q}%"))
    if kelas in KELAS:
        query = query.filter(Kamar.kelas == kelas)
    return render_template("kamar_list.html", kamar=query.order_by(URUTAN_KELAS, Kamar.nama).all(),
                           q=q, kelas=kelas)


def _validasi_kamar(f, kamar_id=None):
    errors = []
    nama = f.get("nama", "").strip()
    if not nama:
        errors.append("Nama kamar wajib diisi.")
    else:
        dup = Kamar.query.filter(func.lower(Kamar.nama) == nama.lower())
        if kamar_id:
            dup = dup.filter(Kamar.id != kamar_id)
        if dup.first():
            errors.append("Nama kamar sudah dipakai. Gunakan nama lain.")
    if f.get("kelas") not in KELAS:
        errors.append("Pilih kelas kamar.")
    try:
        tarif = int(f.get("tarif", ""))
        if tarif <= 0:
            raise ValueError
    except ValueError:
        tarif = None
        errors.append("Tarif per hari harus berupa angka lebih dari 0.")
    return errors, nama, tarif


@app.route("/kamar/baru", methods=["GET", "POST"])
@admin_required
def kamar_baru():
    if request.method == "POST":
        errors, nama, tarif = _validasi_kamar(request.form)
        jumlah = request.form.get("jumlah_bed", type=int) or 0
        if not 1 <= jumlah <= 20:
            errors.append("Jumlah bed harus antara 1 dan 20.")
        if not errors:
            k = Kamar(nama=nama, kelas=request.form["kelas"], tarif=tarif)
            k.beds = [Bed(nomor=i) for i in range(1, jumlah + 1)]
            db.session.add(k)
            db.session.commit()
            flash(f"Kamar {k.nama} dengan {jumlah} bed ditambahkan.", "success")
            return redirect(url_for("kamar_list"))
        for e in errors:
            flash(e, "danger")
    return render_template("kamar_form.html", kamar=None, form=request.form)


@app.route("/kamar/<int:id>/ubah", methods=["GET", "POST"])
@admin_required
def kamar_ubah(id):
    k = db.get_or_404(Kamar, id)
    if request.method == "POST":
        errors, nama, tarif = _validasi_kamar(request.form, k.id)
        if not errors:
            k.nama, k.kelas, k.tarif = nama, request.form["kelas"], tarif
            db.session.commit()
            flash("Data kamar diperbarui. Pasien yang sudah masuk tetap memakai tarif lama.", "success")
            return redirect(url_for("kamar_list"))
        for e in errors:
            flash(e, "danger")
        return render_template("kamar_form.html", kamar=k, form=request.form)
    return render_template("kamar_form.html", kamar=k,
                           form=dict(nama=k.nama, kelas=k.kelas, tarif=k.tarif))


@app.route("/kamar/<int:id>/tambah-bed", methods=["POST"])
@admin_required
def bed_tambah(id):
    k = db.get_or_404(Kamar, id)
    nomor = max([b.nomor for b in k.beds], default=0) + 1
    db.session.add(Bed(kamar_id=k.id, nomor=nomor))
    db.session.commit()
    flash(f"Bed {nomor} ditambahkan ke {k.nama}.", "success")
    return redirect(url_for("kamar_list"))


@app.route("/bed/<int:id>/hapus", methods=["POST"])
@admin_required
def bed_hapus(id):
    b = db.get_or_404(Bed, id)
    if b.riwayat:
        flash("Bed yang pernah dipakai pasien tidak bisa dihapus.", "danger")
    else:
        db.session.delete(b)
        db.session.commit()
        flash("Bed dihapus.", "success")
    return redirect(url_for("kamar_list"))


# --------------------------------------------------------------------------
# Dokter
# --------------------------------------------------------------------------
@app.route("/dokter", methods=["GET", "POST"])
@login_required
def dokter_list():
    if request.method == "POST":
        if g.user.role != "admin":
            abort(403)
        nama = request.form.get("nama", "").strip()
        spesialis = request.form.get("spesialis", "").strip()
        if not nama or not spesialis:
            flash("Nama dan spesialis dokter wajib diisi.", "danger")
        else:
            db.session.add(Dokter(nama=nama, spesialis=spesialis))
            db.session.commit()
            flash(f"{nama} ditambahkan.", "success")
        return redirect(url_for("dokter_list"))
    q = request.args.get("q", "").strip()
    query = Dokter.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Dokter.nama.ilike(like), Dokter.spesialis.ilike(like)))
    return render_template("dokter_list.html", dokter=query.order_by(Dokter.nama).all(), q=q)


@app.route("/dokter/<int:id>/hapus", methods=["POST"])
@admin_required
def dokter_hapus(id):
    d = db.get_or_404(Dokter, id)
    if d.rawat:
        flash("Dokter yang pernah menangani pasien tidak bisa dihapus.", "danger")
    else:
        db.session.delete(d)
        db.session.commit()
        flash("Dokter dihapus.", "success")
    return redirect(url_for("dokter_list"))


# --------------------------------------------------------------------------
# Rawat inap
# --------------------------------------------------------------------------
@app.route("/rawat-inap")
@login_required
def rawat_list():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    dokter_id = request.args.get("dokter", type=int)
    page = request.args.get("page", 1, type=int)
    query = RawatInap.query.join(Pasien)
    if q:
        like = f"%{q}%"
        di_kamar = (db.session.query(RiwayatBed.rawat_id)
                    .join(Bed, RiwayatBed.bed_id == Bed.id)
                    .join(Kamar, Bed.kamar_id == Kamar.id)
                    .filter(RiwayatBed.selesai.is_(None), Kamar.nama.ilike(like)))
        query = query.filter(or_(Pasien.nama.ilike(like), Pasien.no_rm.ilike(like),
                                 RawatInap.no_rawat.ilike(like),
                                 RawatInap.diagnosa_awal.ilike(like),
                                 RawatInap.id.in_(di_kamar)))
    if status in ("dirawat", "pulang"):
        query = query.filter(RawatInap.status == status)
    if dokter_id:
        query = query.filter(RawatInap.dokter_id == dokter_id)
    pagination = query.order_by(RawatInap.tgl_masuk.desc()).paginate(
        page=page, per_page=10, error_out=False)
    return render_template("rawat_list.html", pagination=pagination, q=q, status=status,
                           dokter_id=dokter_id, dokter=Dokter.query.order_by(Dokter.nama).all())


@app.route("/rawat-inap/baru", methods=["GET", "POST"])
@login_required
def rawat_baru():
    dirawat_ids = db.session.query(RawatInap.pasien_id).filter(RawatInap.status == "dirawat")
    pasien_opts = Pasien.query.filter(~Pasien.id.in_(dirawat_ids)).order_by(Pasien.nama).all()
    dokter_opts = Dokter.query.order_by(Dokter.nama).all()

    if request.method == "POST":
        f = request.form
        errors = []
        pasien = next((p for p in pasien_opts if str(p.id) == f.get("pasien_id")), None)
        dokter = db.session.get(Dokter, f.get("dokter_id", type=int)) if f.get("dokter_id") else None
        bed = db.session.get(Bed, f.get("bed_id", type=int)) if f.get("bed_id") else None
        masuk = parse_dt(f.get("tgl_masuk"))
        diagnosa = f.get("diagnosa_awal", "").strip()
        if not pasien:
            errors.append("Pilih pasien. Pasien yang sedang dirawat tidak bisa diterima lagi.")
        if not dokter:
            errors.append("Pilih dokter penanggung jawab.")
        if not bed or bed.aktif:
            errors.append("Pilih bed yang masih kosong.")
        if not masuk:
            errors.append("Tanggal dan jam masuk tidak valid.")
        elif masuk > datetime.now() + timedelta(minutes=5):
            errors.append("Waktu masuk tidak boleh di masa depan.")
        if not diagnosa:
            errors.append("Diagnosa awal wajib diisi.")
        if not errors:
            tarif = bed.kamar.tarif
            r = RawatInap(no_rawat=buat_no_rawat(), pasien=pasien, dokter=dokter,
                          tgl_masuk=masuk, diagnosa_awal=diagnosa, status="dirawat")
            r.riwayat_bed.append(RiwayatBed(bed=bed, mulai=masuk, tarif=tarif))
            db.session.add(r)
            db.session.commit()
            flash(f"{pasien.nama} diterima di {bed.label}.", "success")
            return redirect(url_for("rawat_detail", id=r.id))
        for e in errors:
            flash(e, "danger")
        form = f
    else:
        form = dict(pasien_id=request.args.get("pasien_id", ""),
                    bed_id=request.args.get("bed_id", ""),
                    tgl_masuk=dt_input(datetime.now()))
    return render_template("rawat_form.html", form=form, pasien_opts=pasien_opts,
                           dokter_opts=dokter_opts, kamar_opts=kamar_tersedia())


@app.route("/rawat-inap/<int:id>")
@login_required
def rawat_detail(id):
    r = db.get_or_404(RawatInap, id)
    return render_template("rawat_detail.html", r=r, kamar_opts=kamar_tersedia(),
                           sekarang=dt_input(datetime.now()))


@app.route("/rawat-inap/<int:id>/catatan", methods=["POST"])
@login_required
def catatan_tambah(id):
    r = db.get_or_404(RawatInap, id)
    if r.status != "dirawat":
        flash("Pasien sudah pulang, catatan baru tidak bisa ditambahkan.", "danger")
        return redirect(url_for("rawat_detail", id=id))
    f = request.form
    try:
        suhu = float(f["suhu"].replace(",", ".")) if f.get("suhu") else None
        nadi = int(f["nadi"]) if f.get("nadi") else None
    except ValueError:
        flash("Suhu dan nadi harus berupa angka.", "danger")
        return redirect(url_for("rawat_detail", id=id))
    td = f.get("tekanan_darah", "").strip()
    keluhan = f.get("keluhan", "").strip()
    instruksi = f.get("instruksi", "").strip()
    if not any([suhu, nadi, td, keluhan, instruksi]):
        flash("Isi minimal satu kolom catatan sebelum menyimpan.", "danger")
        return redirect(url_for("rawat_detail", id=id))
    db.session.add(Catatan(rawat=r, penulis_id=g.user.id, waktu=datetime.now(), suhu=suhu,
                           nadi=nadi, tekanan_darah=td, keluhan=keluhan, instruksi=instruksi))
    db.session.commit()
    flash("Catatan harian tersimpan.", "success")
    return redirect(url_for("rawat_detail", id=id))


@app.route("/rawat-inap/<int:id>/pindah", methods=["POST"])
@login_required
def rawat_pindah(id):
    r = db.get_or_404(RawatInap, id)
    bed_baru = db.session.get(Bed, request.form.get("bed_id", type=int) or 0)
    if r.status != "dirawat":
        flash("Pasien sudah pulang, tidak bisa dipindahkan.", "danger")
    elif not bed_baru or bed_baru.aktif:
        flash("Pilih bed tujuan yang masih kosong.", "danger")
    else:
        sekarang = datetime.now()
        for rb in r.riwayat_bed:
            if rb.selesai is None:
                rb.selesai = sekarang
        tarif = bed_baru.kamar.tarif
        r.riwayat_bed.append(RiwayatBed(bed=bed_baru, mulai=sekarang, tarif=tarif))
        db.session.commit()
        flash(f"Pasien dipindahkan ke {bed_baru.label}.", "success")
    return redirect(url_for("rawat_detail", id=id))


@app.route("/rawat-inap/<int:id>/pulang", methods=["POST"])
@login_required
def rawat_pulang(id):
    r = db.get_or_404(RawatInap, id)
    f = request.form
    keluar = parse_dt(f.get("tgl_keluar"))
    if r.status != "dirawat":
        flash("Pasien ini sudah dipulangkan.", "danger")
    elif f.get("cara_pulang") not in CARA_PULANG:
        flash("Pilih cara pulang.", "danger")
    elif not keluar or keluar < r.tgl_masuk:
        flash("Waktu pulang tidak valid. Waktu pulang harus setelah waktu masuk.", "danger")
    else:
        for rb in r.riwayat_bed:
            if rb.selesai is None:
                rb.selesai = keluar
        r.tgl_keluar = keluar
        r.status = "pulang"
        r.cara_pulang = f["cara_pulang"]
        r.ringkasan_pulang = f.get("ringkasan_pulang", "").strip()
        r.total_biaya = sum(x.biaya for x in r.riwayat_bed)
        db.session.commit()
        flash(f"{r.pasien.nama} dipulangkan. Total biaya kamar {rupiah(r.total_biaya)}.", "success")
    return redirect(url_for("rawat_detail", id=id))


# --------------------------------------------------------------------------
# Error page
# --------------------------------------------------------------------------
@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def error(e):
    pesan = {400: "Permintaan tidak valid. Muat ulang halaman lalu coba lagi.",
             403: "Halaman ini hanya untuk admin.",
             404: "Halaman atau data tidak ditemukan."}[e.code]
    return render_template("error.html", kode=e.code, pesan=pesan), e.code


# --------------------------------------------------------------------------
# Data contoh
# --------------------------------------------------------------------------
def seed():
    if User.query.first():
        return
    accounts = [
        ("admin", os.environ.get("SIMRS_ADMIN_PASSWORD", "admin123"), "Administrator RS", "admin"),
        ("dokter", os.environ.get("SIMRS_DOCTOR_PASSWORD", "dokter123"),
         "dr. Andi Prasetyo, Sp.PD", "dokter"),
        ("perawat", os.environ.get("SIMRS_NURSE_PASSWORD", "perawat123"), "Ns. Lestari", "perawat"),
    ]
    for uname, pw, nama, role in accounts:
        db.session.add(User(username=uname, password_hash=generate_password_hash(pw),
                            nama=nama, role=role))

    dokter = [Dokter(nama=n, spesialis=s) for n, s in [
        ("dr. Andi Prasetyo, Sp.PD", "Penyakit Dalam"), ("dr. Rina Kartika, Sp.A", "Anak"),
        ("dr. Budi Hartono, Sp.B", "Bedah"), ("dr. Maya Lestari, Sp.OG", "Kebidanan dan Kandungan"),
        ("dr. Hendra Wijaya, Sp.JP", "Jantung dan Pembuluh Darah")]]

    spesifikasi = [("Anggrek 101", "VIP", 900000, 1), ("Anggrek 102", "VIP", 900000, 1),
                   ("Melati 201", "Kelas 1", 500000, 2), ("Melati 202", "Kelas 1", 500000, 2),
                   ("Dahlia 301", "Kelas 2", 300000, 3), ("Dahlia 302", "Kelas 2", 300000, 3),
                   ("Kenanga 401", "Kelas 3", 150000, 4), ("Kenanga 402", "Kelas 3", 150000, 4)]
    beds = []
    for nama, kelas, tarif, n in spesifikasi:
        k = Kamar(nama=nama, kelas=kelas, tarif=tarif)
        k.beds = [Bed(nomor=i) for i in range(1, n + 1)]
        beds.extend(k.beds)
        db.session.add(k)

    data_pasien = [
        ("Siti Aminah", "P", date(1978, 3, 14), "Jl. Merdeka No. 12, Malang", "081234560001", "O", "BPJS"),
        ("Budi Santoso", "L", date(1965, 11, 2), "Jl. Pahlawan No. 45, Sidoarjo", "081234560002", "A", "BPJS"),
        ("Dewi Lestari", "P", date(1992, 7, 21), "Jl. Mawar No. 3, Surabaya", "081234560003", "B", "Asuransi"),
        ("Agus Wijaya", "L", date(1984, 1, 30), "Jl. Diponegoro No. 88, Gresik", "081234560004", "AB", "Umum"),
        ("Rina Marlina", "P", date(2016, 5, 9), "Jl. Kenanga No. 7, Mojokerto", "081234560005", "A", "BPJS"),
        ("Hadi Kusuma", "L", date(1958, 9, 17), "Jl. Veteran No. 21, Kediri", "081234560006", "O", "BPJS"),
        ("Nur Aini", "P", date(1999, 12, 5), "Jl. Anggrek No. 19, Surabaya", "081234560007", "B", "Umum"),
        ("Fajar Ramadhan", "L", date(1990, 4, 25), "Jl. Sudirman No. 60, Pasuruan", "081234560008", "O", "Asuransi"),
        ("Lia Permata", "P", date(1987, 8, 11), "Jl. Cendana No. 5, Jombang", "081234560009", "A", "BPJS"),
        ("Joko Susilo", "L", date(1952, 2, 3), "Jl. Gajah Mada No. 33, Madiun", "081234560010", "AB", "BPJS"),
        ("Sri Wahyuni", "P", date(1971, 6, 28), "Jl. Melati No. 14, Blitar", "081234560011", "O", "Umum"),
        ("Bayu Pratama", "L", date(2003, 10, 19), "Jl. Kartini No. 9, Surabaya", "081234560012", "B", "Umum"),
        ("Eka Putri", "P", date(1995, 3, 2), "Jl. Flamboyan No. 27, Sidoarjo", "081234560013", "A", "Asuransi"),
        ("Rudi Hartanto", "L", date(1969, 5, 15), "Jl. Pemuda No. 71, Probolinggo", "081234560014", "O", "BPJS"),
    ]
    pasien = []
    for i, (n, jk, lahir, alamat, tel, gol, pj) in enumerate(data_pasien, 1):
        p = Pasien(no_rm=f"RM-{i:06d}", nama=n, jenis_kelamin=jk, tgl_lahir=lahir,
                   alamat=alamat, telepon=tel, gol_darah=gol, penjamin=pj)
        pasien.append(p)
        db.session.add(p)
    db.session.flush()

    sekarang = datetime.now()
    # (pasien, dokter, bed, hari lalu, diagnosa, lama rawat bila sudah pulang atau None)
    kasus = [
        (0, 0, 4, 3, "Demam berdarah dengue (DBD) grade II", None),
        (1, 4, 2, 5, "Gagal jantung kongestif", None),
        (2, 3, 0, 1, "Pasca persalinan sesar", None),
        (3, 2, 9, 2, "Fraktur tibia dekstra, pasca operasi", None),
        (4, 1, 14, 2, "Gastroenteritis akut dengan dehidrasi sedang", None),
        (5, 0, 5, 6, "Diabetes melitus tipe 2 tidak terkontrol", None),
        (6, 0, 10, 1, "Tifoid (demam tifoid)", None),
        (9, 4, 3, 4, "Infark miokard akut", None),
        (7, 2, 11, 9, "Apendisitis akut, pasca apendektomi", 4),
        (8, 0, 15, 12, "Pneumonia komunitas", 5),
    ]
    for pi, di, bi, hari, diag, lama in kasus:
        masuk = (sekarang - timedelta(days=hari)).replace(hour=9, minute=20, second=0, microsecond=0)
        r = RawatInap(no_rawat=f"RI-{masuk:%Y%m%d}-{pi + 1:03d}", pasien=pasien[pi],
                      dokter=dokter[di], tgl_masuk=masuk, diagnosa_awal=diag)
        rb = RiwayatBed(bed=beds[bi], mulai=masuk, tarif=beds[bi].kamar.tarif)
        r.riwayat_bed.append(rb)
        for h in range(min(hari, 3) if lama is None else 2):
            r.catatan.append(Catatan(
                waktu=masuk + timedelta(days=h, hours=5), penulis_id=3 if h % 2 == 0 else 2,
                suhu=round(36.4 + (h * 0.4) % 1.8, 1), tekanan_darah=["120/80", "130/85", "110/70"][h % 3],
                nadi=78 + h * 4, keluhan=["Mual dan lemas", "Nyeri berkurang, nafsu makan membaik",
                                          "Keluhan membaik, mulai mobilisasi"][h % 3],
                instruksi=["Lanjutkan infus dan obat oral", "Diet lunak, pantau cairan",
                           "Evaluasi ulang besok pagi"][h % 3]))
        if lama is not None:
            keluar = masuk + timedelta(days=lama, hours=3)
            rb.selesai = keluar
            r.tgl_keluar, r.status = keluar, "pulang"
            r.cara_pulang = "Sembuh"
            r.ringkasan_pulang = "Kondisi stabil, kontrol rawat jalan 1 minggu."
            r.total_biaya = rb.biaya
        db.session.add(r)
    db.session.commit()


os.makedirs(app.instance_path, exist_ok=True)

with app.app_context():
    db.create_all()
    seed()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
