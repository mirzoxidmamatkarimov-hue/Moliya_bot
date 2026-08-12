"""
Moliyaviy monitoring boti uchun ma'lumotlar bazasi moduli.
SQLite bazasidan foydalanadi, har bir foydalanuvchi uchun alohida yozuvlar saqlanadi.
"""
import sqlite3
from datetime import datetime
from contextlib import contextmanager

DB_PATH = "moliya.db"


@contextmanager
def get_connection():
    """Baza bilan ulanishni ochib, ish tugagach avtomatik yopadi."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# Ko'p uchraydigan kategoriyalar uchun standart klassifikatsiya.
# Bu ro'yxatda bo'lmagan kategoriyalar uchun foydalanuvchidan so'raladi.
STANDART_ZARUR = {
    "ovqat", "oziq-ovqat", "oziqovqat", "bozor", "kommunal", "ijara", "kvartira",
    "kvartira haqi", "benzin", "yoqilg'i", "yoqilgi", "dori", "dori-darmon",
    "sog'liq", "sogliq", "tibbiyot", "shifokor", "ta'lim", "talim", "o'quv",
    "internet", "aloqa", "telefon", "kredit", "qarz", "soliq", "sug'urta",
    "sugurta", "bolalar", "maktab", "bog'cha",
}
STANDART_KERAKSIZ = {
    "restoran", "kafe", "fastfud", "fast food", "kofe", "choyxona",
    "o'yin", "oyin", "ko'ngilochar", "kongilochar", "kino", "konsert",
    "alkogol", "chekish", "sigareta", "sigaret", "gadget", "aksessuar",
    "sovg'a", "sovga", "brend", "shopping", "yangi kiyim", "o'yin-kulgi",
}


def standart_holat(kategoriya: str):
    """Kategoriya nomi standart ro'yxatda bo'lsa, holatini qaytaradi. Bo'lmasa None."""
    k = kategoriya.strip().lower()
    if k in STANDART_ZARUR:
        return "zarur"
    if k in STANDART_KERAKSIZ:
        return "keraksiz"
    return None


def init_db():
    """Baza va jadvalni birinchi marta ishga tushirishda yaratadi."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tranzaksiyalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                tur TEXT NOT NULL CHECK(tur IN ('kirim', 'chiqim')),
                summa REAL NOT NULL,
                kategoriya TEXT NOT NULL,
                sana TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS kategoriya_holati (
                user_id INTEGER NOT NULL,
                kategoriya TEXT NOT NULL,
                holat TEXT NOT NULL CHECK(holat IN ('zarur', 'keraksiz')),
                PRIMARY KEY (user_id, kategoriya)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS byudjetlar (
                user_id INTEGER NOT NULL,
                kategoriya TEXT NOT NULL,
                limit_summa REAL NOT NULL,
                PRIMARY KEY (user_id, kategoriya)
            )
        """)


def qoshish(user_id: int, tur: str, summa: float, kategoriya: str):
    """Yangi kirim yoki chiqim yozuvini bazaga qo'shadi."""
    sana = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO tranzaksiyalar (user_id, tur, summa, kategoriya, sana) VALUES (?, ?, ?, ?, ?)",
            (user_id, tur, summa, kategoriya, sana)
        )
        return cursor.lastrowid


def oxirgi_yozuvlar(user_id: int, limit: int = 10):
    """Foydalanuvchining oxirgi N ta yozuvini qaytaradi."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM tranzaksiyalar WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
        return rows


def oxirgisini_ochirish(user_id: int):
    """Foydalanuvchining eng oxirgi yozuvini o'chiradi. O'chirilgan yozuvni qaytaradi yoki None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tranzaksiyalar WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        ).fetchone()
        if row:
            conn.execute("DELETE FROM tranzaksiyalar WHERE id = ?", (row["id"],))
        return row


def kategoriya_holatini_olish(user_id: int, kategoriya: str):
    """Foydalanuvchi uchun kategoriya holatini qaytaradi: 'zarur', 'keraksiz' yoki None (noma'lum)."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT holat FROM kategoriya_holati WHERE user_id = ? AND kategoriya = ?",
            (user_id, kategoriya)
        ).fetchone()
        return row["holat"] if row else None


def kategoriya_holatini_saqlash(user_id: int, kategoriya: str, holat: str):
    """Kategoriya holatini saqlaydi yoki yangilaydi (zarur/keraksiz)."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO kategoriya_holati (user_id, kategoriya, holat) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, kategoriya) DO UPDATE SET holat = excluded.holat",
            (user_id, kategoriya, holat)
        )


def barcha_kategoriyalar_holati(user_id: int):
    """Foydalanuvchining barcha belgilangan kategoriyalarini qaytaradi."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT kategoriya, holat FROM kategoriya_holati WHERE user_id = ? ORDER BY kategoriya",
            (user_id,)
        ).fetchall()
        return rows


def tranzaksiyani_olish(tranzaksiya_id: int):
    """ID bo'yicha bitta tranzaksiyani qaytaradi."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM tranzaksiyalar WHERE id = ?", (tranzaksiya_id,)
        ).fetchone()


UMUMIY_BYUDJET_KALITI = "__umumiy__"


def byudjet_belgilash(user_id: int, kategoriya: str, limit_summa: float):
    """Kategoriya (yoki umumiy) uchun oylik xarajat limitini belgilaydi/yangilaydi."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO byudjetlar (user_id, kategoriya, limit_summa) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, kategoriya) DO UPDATE SET limit_summa = excluded.limit_summa",
            (user_id, kategoriya, limit_summa)
        )


def byudjet_olish(user_id: int, kategoriya: str):
    """Kategoriya uchun belgilangan limitni qaytaradi, agar yo'q bo'lsa None."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT limit_summa FROM byudjetlar WHERE user_id = ? AND kategoriya = ?",
            (user_id, kategoriya)
        ).fetchone()
        return row["limit_summa"] if row else None


def byudjet_ochirish(user_id: int, kategoriya: str):
    """Kategoriya uchun belgilangan limitni o'chiradi."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM byudjetlar WHERE user_id = ? AND kategoriya = ?",
            (user_id, kategoriya)
        )


def barcha_byudjetlar(user_id: int):
    """Foydalanuvchining barcha belgilangan limitlarini qaytaradi."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT kategoriya, limit_summa FROM byudjetlar WHERE user_id = ? ORDER BY kategoriya",
            (user_id,)
        ).fetchall()
        return rows


def kategoriya_oylik_jami(user_id: int, kategoriya: str, yil: int, oy: int) -> float:
    """Berilgan oy uchun bitta kategoriyadagi umumiy chiqimni qaytaradi."""
    oy_str = f"{yil:04d}-{oy:02d}"
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(summa), 0) as s FROM tranzaksiyalar "
            "WHERE user_id = ? AND tur = 'chiqim' AND kategoriya = ? AND sana LIKE ?",
            (user_id, kategoriya, f"{oy_str}%")
        ).fetchone()
        return row["s"]


def oldingi_oy_hisobot(user_id: int, yil: int, oy: int):
    """Taqqoslash uchun avvalgi oyning umumiy kirim/chiqimini qaytaradi."""
    if oy == 1:
        yil, oy = yil - 1, 12
    else:
        oy -= 1
    natija = oylik_hisobot(user_id, yil, oy)
    return natija


def oylik_hisobot(user_id: int, yil: int, oy: int):
    """Berilgan oy uchun kirim/chiqim statistikasini qaytaradi."""
    oy_str = f"{yil:04d}-{oy:02d}"
    with get_connection() as conn:
        umumiy_kirim = conn.execute(
            "SELECT COALESCE(SUM(summa), 0) as s FROM tranzaksiyalar "
            "WHERE user_id = ? AND tur = 'kirim' AND sana LIKE ?",
            (user_id, f"{oy_str}%")
        ).fetchone()["s"]

        umumiy_chiqim = conn.execute(
            "SELECT COALESCE(SUM(summa), 0) as s FROM tranzaksiyalar "
            "WHERE user_id = ? AND tur = 'chiqim' AND sana LIKE ?",
            (user_id, f"{oy_str}%")
        ).fetchone()["s"]

        chiqim_kategoriyalar = conn.execute(
            "SELECT kategoriya, SUM(summa) as jami FROM tranzaksiyalar "
            "WHERE user_id = ? AND tur = 'chiqim' AND sana LIKE ? "
            "GROUP BY kategoriya ORDER BY jami DESC",
            (user_id, f"{oy_str}%")
        ).fetchall()

        kirim_manbalar = conn.execute(
            "SELECT kategoriya, SUM(summa) as jami FROM tranzaksiyalar "
            "WHERE user_id = ? AND tur = 'kirim' AND sana LIKE ? "
            "GROUP BY kategoriya ORDER BY jami DESC",
            (user_id, f"{oy_str}%")
        ).fetchall()

        # Har bir chiqim kategoriyasiga holat (zarur/keraksiz/noma'lum) biriktiramiz
        kategoriyalar_royxati = []
        zarur_jami = 0.0
        keraksiz_jami = 0.0
        for row in chiqim_kategoriyalar:
            kategoriya = row["kategoriya"]
            jami = row["jami"]
            holat = kategoriya_holatini_olish(user_id, kategoriya) or standart_holat(kategoriya)
            if holat == "zarur":
                zarur_jami += jami
            elif holat == "keraksiz":
                keraksiz_jami += jami
            kategoriyalar_royxati.append({
                "kategoriya": kategoriya,
                "jami": jami,
                "holat": holat,
            })

        return {
            "umumiy_kirim": umumiy_kirim,
            "umumiy_chiqim": umumiy_chiqim,
            "balans": umumiy_kirim - umumiy_chiqim,
            "chiqim_kategoriyalar": kategoriyalar_royxati,
            "kirim_manbalar": kirim_manbalar,
            "zarur_jami": zarur_jami,
            "keraksiz_jami": keraksiz_jami,
            "nomalum_jami": umumiy_chiqim - zarur_jami - keraksiz_jami,
        }
