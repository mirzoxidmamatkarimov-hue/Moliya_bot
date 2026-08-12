"""
Shaxsiy moliya monitoring Telegram boti.

Foydalanuvchi kirim va chiqimlarini yozib boradi, bot esa oylik hisobot,
kategoriyalar bo'yicha taqsimot va balansni hisoblab beradi.

Ishga tushirish:
    1. pip install -r requirements.txt
    2. TELEGRAM_BOT_TOKEN muhit o'zgaruvchisini o'rnating (yoki quyida TOKEN ga yozing)
    3. python bot.py
"""
import os
import logging
from datetime import datetime

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardMarkup, InputFile,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

import database as db
import chart

# --- Sozlamalar ---
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

OY_NOMLARI = ["", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
              "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]

TEZKOR_CHIQIM_KATEGORIYALARI = ["Ovqat", "Transport", "Kommunal", "Restoran", "Kofe", "Kiyim", "Boshqa"]
TEZKOR_KIRIM_MANBALARI = ["Oylik", "Biznes", "Frilans", "Sovg'a", "Boshqa"]

ASOSIY_MENYU = ReplyKeyboardMarkup(
    [
        ["➕ Chiqim", "➕ Kirim"],
        ["📊 Hisobot", "📈 Grafik"],
        ["💡 Tahlil", "🧾 Oxirgi"],
    ],
    resize_keyboard=True
)

# Foydalanuvchi "➕ Chiqim"/"➕ Kirim" tugmasini bosgach, keyingi raqamli xabarni
# qaysi kategoriya/tur uchun kutayotganimizni shu yerda saqlaymiz (xotirada, RAM ichida).
KUTILAYOTGAN_KIRITISH = {}


def summa_formatlash(summa: float) -> str:
    """Summani chiroyli formatda ko'rsatadi: 1000000 -> 1 000 000"""
    return f"{summa:,.0f}".replace(",", " ")


# --- Buyruqlar ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    matn = (
        "👋 Salom! Men sizning shaxsiy moliyaviy yordamchingizman.\n\n"
        "Men orqali kirim va chiqimlaringizni yozib borishingiz mumkin, "
        "men esa oy davomida qancha pul topganingiz, sarflaganingizni va "
        "qaysi xarajatlarni qisqartirish kerakligini hisoblab beraman.\n\n"
        "📌 *Asosiy buyruqlar:*\n"
        "/kirim <summa> <manba> — kirim qo'shish\n"
        "/chiqim <summa> <kategoriya> — chiqim qo'shish\n"
        "/hisobot — shu oy uchun umumiy hisobot\n"
        "/grafik — xarajatlar diagrammasi\n"
        "/tahlil — nimani qisqartirish kerakligi bo'yicha tavsiya\n"
        "/byudjet <kategoriya> <summa> — oylik limit belgilash\n"
        "/byudjetlar — belgilangan limitlarni ko'rish\n"
        "/toifa <kategoriya> <zarur/keraksiz> — kategoriya turini belgilash\n"
        "/oxirgi — oxirgi 10 ta yozuv\n"
        "/ochir — oxirgi yozuvni bekor qilish\n\n"
        "💬 *Tez yozish:* buyruqsiz ham yozishingiz mumkin — shunchaki "
        "\"30000 taksi\" deb yozsangiz chiqim, \"+3000000 oylik\" deb yozsangiz "
        "kirim sifatida qo'shiladi.\n\n"
        "Pastdagi menyudan ham foydalanishingiz mumkin 👇"
    )
    await update.message.reply_text(matn, parse_mode="Markdown", reply_markup=ASOSIY_MENYU)


async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def kirim_qoshish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _tranzaksiya_qoshish(update, context, tur="kirim")


async def chiqim_qoshish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await _tranzaksiya_qoshish(update, context, tur="chiqim")


async def _tranzaksiya_qoshish(update: Update, context: ContextTypes.DEFAULT_TYPE, tur: str):
    """/kirim va /chiqim buyruqlari uchun argumentlarni o'qib, asosiy funksiyani chaqiradi."""
    args = context.args
    buyruq = "/kirim" if tur == "kirim" else "/chiqim"

    if len(args) == 0:
        if tur == "chiqim":
            await menyu_chiqim_boshlash(update, context)
        else:
            await menyu_kirim_boshlash(update, context)
        return

    if len(args) < 2:
        await update.message.reply_text(
            f"⚠️ Noto'g'ri format. Masalan:\n{buyruq} 50000 {'oylik' if tur == 'kirim' else 'ovqat'}"
        )
        return

    try:
        summa = float(args[0].replace(",", "").replace(" ", ""))
        if summa <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Summa noto'g'ri. Musbat son kiriting, masalan: 50000")
        return

    kategoriya = " ".join(args[1:]).strip().lower()
    user_id = update.effective_user.id
    await _tranzaksiya_saqlash_va_javob(update, context, user_id, tur, summa, kategoriya)


async def _tranzaksiya_saqlash_va_javob(update: Update, context: ContextTypes.DEFAULT_TYPE,
                                         user_id: int, tur: str, summa: float, kategoriya: str):
    """Tranzaksiyani bazaga yozadi, klassifikatsiya so'raydi va byudjet limitini tekshiradi.
    Bu funksiya buyruq, tez tugma va tabiiy til orqali kiritilgan barcha yozuvlar uchun umumiy ishlatiladi."""
    tranzaksiya_id = db.qoshish(user_id, tur, summa, kategoriya)

    emoji = "💰" if tur == "kirim" else "💸"
    soz = "Kirim" if tur == "kirim" else "Chiqim"
    matn = f"{emoji} {soz} qo'shildi: {summa_formatlash(summa)} so'm — {kategoriya}"

    if tur == "chiqim":
        # Byudjet limitini tekshiramiz (kategoriya va umumiy oylik limit)
        ogohlantirish = _byudjet_tekshirish(user_id, kategoriya)
        if ogohlantirish:
            matn += "\n\n" + ogohlantirish

        # Kategoriya hali "zarur/keraksiz" deb belgilanmagan bo'lsa, so'raymiz
        mavjud_holat = db.kategoriya_holatini_olish(user_id, kategoriya) or db.standart_holat(kategoriya)
        if mavjud_holat is None:
            keyboard = InlineKeyboardMarkup([[
                InlineKeyboardButton("🟢 Zarur", callback_data=f"toifa:zarur:{tranzaksiya_id}"),
                InlineKeyboardButton("🔴 Keraksiz", callback_data=f"toifa:keraksiz:{tranzaksiya_id}"),
            ]])
            await update.message.reply_text(
                matn + f"\n\n❓ \"{kategoriya}\" — bu zarur xarajatmi yoki keraksizmi? "
                "(Bu tanlov keyingi shu turdagi xarajatlarga ham tegishli boʻladi)",
                reply_markup=keyboard
            )
            return

    await update.message.reply_text(matn)


def _byudjet_tekshirish(user_id: int, kategoriya: str) -> str:
    """Kategoriya va umumiy oylik byudjet limitlarini tekshiradi, kerak bo'lsa ogohlantirish matnini qaytaradi."""
    hozir = datetime.now()
    ogohlantirishlar = []

    # Kategoriya limiti
    limit = db.byudjet_olish(user_id, kategoriya)
    if limit:
        jami = db.kategoriya_oylik_jami(user_id, kategoriya, hozir.year, hozir.month)
        foiz = jami / limit * 100
        if jami > limit:
            ogohlantirishlar.append(
                f"🚨 Diqqat! \"{kategoriya}\" uchun byudjet limiti "
                f"({summa_formatlash(limit)} so'm) oshib ketdi — hozir {summa_formatlash(jami)} so'm ({foiz:.0f}%)"
            )
        elif foiz >= 80:
            ogohlantirishlar.append(
                f"⚠️ \"{kategoriya}\" byudjetining {foiz:.0f}% i sarflandi "
                f"({summa_formatlash(jami)} / {summa_formatlash(limit)} so'm)"
            )

    # Umumiy oylik limit
    umumiy_limit = db.byudjet_olish(user_id, db.UMUMIY_BYUDJET_KALITI)
    if umumiy_limit:
        natija = db.oylik_hisobot(user_id, hozir.year, hozir.month)
        jami = natija["umumiy_chiqim"]
        foiz = jami / umumiy_limit * 100
        if jami > umumiy_limit:
            ogohlantirishlar.append(
                f"🚨 Diqqat! Umumiy oylik byudjet limiti "
                f"({summa_formatlash(umumiy_limit)} so'm) oshib ketdi — hozir {summa_formatlash(jami)} so'm ({foiz:.0f}%)"
            )
        elif foiz >= 80:
            ogohlantirishlar.append(
                f"⚠️ Umumiy oylik byudjetning {foiz:.0f}% i sarflandi "
                f"({summa_formatlash(jami)} / {summa_formatlash(umumiy_limit)} so'm)"
            )

    return "\n".join(ogohlantirishlar)


async def toifa_tanlash_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi inline tugma orqali kategoriya turini tanlaganda ishlaydi."""
    query = update.callback_query
    await query.answer()

    _, holat, tranzaksiya_id = query.data.split(":")
    tranzaksiya = db.tranzaksiyani_olish(int(tranzaksiya_id))

    if not tranzaksiya:
        await query.edit_message_text("⚠️ Bu yozuv topilmadi (o'chirilgan bo'lishi mumkin).")
        return

    user_id = tranzaksiya["user_id"]
    kategoriya = tranzaksiya["kategoriya"]
    db.kategoriya_holatini_saqlash(user_id, kategoriya, holat)

    holat_matni = "🟢 Zarur" if holat == "zarur" else "🔴 Keraksiz"
    yangi_matn = query.message.text.split("\n\n❓")[0]
    await query.edit_message_text(
        f"{yangi_matn}\n\n✅ \"{kategoriya}\" — {holat_matni} deb belgilandi."
    )


async def toifa_qoyish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/toifa buyrug'i orqali kategoriya turini qo'lda belgilash yoki o'zgartirish."""
    args = context.args
    if len(args) < 2 or args[-1].lower() not in ("zarur", "keraksiz"):
        await update.message.reply_text(
            "⚠️ Format: /toifa <kategoriya> <zarur yoki keraksiz>\n"
            "Masalan: /toifa taksi zarur"
        )
        return

    holat = args[-1].lower()
    kategoriya = " ".join(args[:-1]).strip().lower()
    user_id = update.effective_user.id

    db.kategoriya_holatini_saqlash(user_id, kategoriya, holat)
    holat_matni = "🟢 Zarur" if holat == "zarur" else "🔴 Keraksiz"
    await update.message.reply_text(f"✅ \"{kategoriya}\" endi {holat_matni} deb belgilandi.")


async def hisobot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hozir = datetime.now()
    natija = db.oylik_hisobot(user_id, hozir.year, hozir.month)
    oy_nomi = OY_NOMLARI[hozir.month]

    if natija["umumiy_kirim"] == 0 and natija["umumiy_chiqim"] == 0:
        await update.message.reply_text(
            f"📊 {oy_nomi} oyi uchun hali hech qanday yozuv yo'q.\n"
            "/kirim yoki /chiqim buyrug'i bilan boshlang."
        )
        return

    balans = natija["balans"]
    balans_emoji = "✅" if balans >= 0 else "🔴"

    matn = f"📊 *{oy_nomi} {hozir.year} oyi uchun hisobot*\n\n"
    matn += f"💰 Umumiy kirim: {summa_formatlash(natija['umumiy_kirim'])} so'm\n"
    matn += f"💸 Umumiy chiqim: {summa_formatlash(natija['umumiy_chiqim'])} so'm\n"
    matn += f"{balans_emoji} Balans: {summa_formatlash(balans)} so'm\n"

    if natija["umumiy_chiqim"] > 0:
        matn += (
            f"\n🟢 Zarur xarajatlar: {summa_formatlash(natija['zarur_jami'])} so'm\n"
            f"🔴 Keraksiz xarajatlar: {summa_formatlash(natija['keraksiz_jami'])} so'm\n"
        )
        if natija["nomalum_jami"] > 0:
            matn += f"⚪ Belgilanmagan: {summa_formatlash(natija['nomalum_jami'])} so'm\n"

    if natija["chiqim_kategoriyalar"]:
        matn += "\n📉 *Chiqimlar kategoriya bo'yicha:*\n"
        for row in sorted(natija["chiqim_kategoriyalar"], key=lambda x: x["jami"], reverse=True):
            foiz = (row["jami"] / natija["umumiy_chiqim"] * 100) if natija["umumiy_chiqim"] else 0
            belgi = "🟢" if row["holat"] == "zarur" else ("🔴" if row["holat"] == "keraksiz" else "⚪")
            matn += f"  {belgi} {row['kategoriya']}: {summa_formatlash(row['jami'])} so'm ({foiz:.0f}%)\n"
        matn += "\n📊 Batafsil grafik uchun /grafik, tavsiyalar uchun /tahlil buyrug'ini yuboring."

    if natija["kirim_manbalar"]:
        matn += "\n📈 *Kirim manbalari:*\n"
        for row in natija["kirim_manbalar"]:
            matn += f"  • {row['kategoriya']}: {summa_formatlash(row['jami'])} so'm\n"

    await update.message.reply_text(matn, parse_mode="Markdown")


async def grafik(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hozir = datetime.now()
    natija = db.oylik_hisobot(user_id, hozir.year, hozir.month)
    oy_nomi = OY_NOMLARI[hozir.month]

    if not natija["chiqim_kategoriyalar"]:
        await update.message.reply_text(
            f"📈 {oy_nomi} oyi uchun hali chiqim yozuvi yo'q. Avval /chiqim bilan qo'shing."
        )
        return

    await update.message.reply_text("📈 Grafik tayyorlanmoqda...")

    # 1) Kategoriyalar bo'yicha ustunli diagramma (eng katta xarajatlar yuqorida)
    bar_buf = chart.xarajatlar_grafigi(natija["chiqim_kategoriyalar"], oy_nomi, hozir.year)
    await update.message.reply_photo(
        photo=InputFile(bar_buf, filename="xarajatlar.png"),
        caption="🟢 Yashil — zarur, 🔴 Qizil — keraksiz, ⚪ Kulrang — belgilanmagan"
    )

    # 2) Umumiy taqsimot doira diagrammasi
    if natija["umumiy_chiqim"] > 0:
        pie_buf = chart.zarur_keraksiz_doira(
            natija["zarur_jami"], natija["keraksiz_jami"], natija["nomalum_jami"],
            oy_nomi, hozir.year
        )
        await update.message.reply_photo(
            photo=InputFile(pie_buf, filename="taqsimot.png"),
            caption="Xarajatlaringizning zarur/keraksiz nisbati"
        )

    await update.message.reply_text("💡 Tavsiyalar uchun /tahlil buyrug'ini yuboring.")


async def tahlil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hozir = datetime.now()
    natija = db.oylik_hisobot(user_id, hozir.year, hozir.month)
    oy_nomi = OY_NOMLARI[hozir.month]

    if natija["umumiy_chiqim"] == 0:
        await update.message.reply_text(f"💡 {oy_nomi} oyi uchun hali chiqim yozuvi yo'q.")
        return

    matn = f"💡 *{oy_nomi} oyi uchun moliyaviy tahlil*\n\n"

    # 1) Umumiy zarur/keraksiz nisbati
    umumiy_chiqim = natija["umumiy_chiqim"]
    keraksiz_foiz = natija["keraksiz_jami"] / umumiy_chiqim * 100 if umumiy_chiqim else 0
    matn += (
        f"Xarajatlaringizning *{keraksiz_foiz:.0f}%* i (\u2248{summa_formatlash(natija['keraksiz_jami'])} so'm) "
        f"keraksiz toifasiga kiradi.\n\n"
    )

    # 2) Eng katta keraksiz kategoriyalar bo'yicha aniq tavsiya
    keraksiz_kategoriyalar = sorted(
        [k for k in natija["chiqim_kategoriyalar"] if k["holat"] == "keraksiz"],
        key=lambda x: x["jami"], reverse=True
    )
    if keraksiz_kategoriyalar:
        matn += "🔻 *Qisqartirish tavsiya etiladigan xarajatlar:*\n"
        jami_tejash = 0
        for row in keraksiz_kategoriyalar[:3]:
            yarim = row["jami"] / 2
            jami_tejash += yarim
            matn += (
                f"  • *{row['kategoriya']}*: {summa_formatlash(row['jami'])} so'm — "
                f"yarmiga tushirsangiz, oyiga {summa_formatlash(yarim)} so'm tejaysiz\n"
            )
        matn += (
            f"\nUshbu 3 ta kategoriyani yarmiga qisqartirsangiz, oyiga taxminan "
            f"*{summa_formatlash(jami_tejash)} so'm*, yilda esa *{summa_formatlash(jami_tejash * 12)} so'm* tejaysiz.\n\n"
        )
    else:
        matn += "✅ Hozircha \"keraksiz\" deb belgilangan xarajatlaringiz yo'q — ajoyib!\n\n"

    # 3) Belgilanmagan kategoriyalar haqida eslatma
    nomalum_kategoriyalar = [k for k in natija["chiqim_kategoriyalar"] if k["holat"] is None]
    if nomalum_kategoriyalar:
        nomlar = ", ".join(k["kategoriya"] for k in nomalum_kategoriyalar[:5])
        matn += (
            f"⚪ Quyidagi kategoriyalar hali belgilanmagan: {nomlar}.\n"
            f"/toifa buyrug'i bilan belgilasangiz, tahlil aniqroq bo'ladi.\n\n"
        )

    # 4) Kirim/chiqim nisbati bo'yicha umumiy baho
    if natija["umumiy_kirim"] > 0:
        nisbat = umumiy_chiqim / natija["umumiy_kirim"] * 100
        if nisbat >= 100:
            matn += "🚨 Bu oy xarajatlaringiz kirimingizdan oshib ketdi — jamg'arish imkoni yo'q.\n\n"
        elif nisbat >= 90:
            matn += f"⚠️ Kirimingizning {nisbat:.0f}% ini sarfladingiz — jamg'arish uchun deyarli joy qolmadi.\n\n"
        elif nisbat <= 60:
            matn += f"✅ Kirimingizning atigi {nisbat:.0f}% ini sarfladingiz — jamg'arish yaxshi ketmoqda!\n\n"

    # 5) Oldingi oy bilan solishtirish
    oldingi = db.oldingi_oy_hisobot(user_id, hozir.year, hozir.month)
    if oldingi["umumiy_chiqim"] > 0:
        farq = umumiy_chiqim - oldingi["umumiy_chiqim"]
        farq_foiz = abs(farq) / oldingi["umumiy_chiqim"] * 100
        if farq > 0:
            matn += f"📈 O'tgan oyga nisbatan xarajatlaringiz {farq_foiz:.0f}% ga oshgan.\n"
        elif farq < 0:
            matn += f"📉 O'tgan oyga nisbatan xarajatlaringiz {farq_foiz:.0f}% ga kamaygan. Ajoyib!\n"

    await update.message.reply_text(matn, parse_mode="Markdown")


async def byudjet_belgilash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Format: /byudjet <kategoriya yoki 'umumiy'> <summa>\n"
            "Masalan: /byudjet restoran 300000\n"
            "Yoki: /byudjet umumiy 5000000"
        )
        return

    try:
        limit_summa = float(args[-1].replace(",", "").replace(" ", ""))
        if limit_summa <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text("⚠️ Summa noto'g'ri. Musbat son kiriting.")
        return

    kategoriya_matni = " ".join(args[:-1]).strip().lower()
    kategoriya = db.UMUMIY_BYUDJET_KALITI if kategoriya_matni == "umumiy" else kategoriya_matni
    user_id = update.effective_user.id

    db.byudjet_belgilash(user_id, kategoriya, limit_summa)
    nomi = "Umumiy oylik byudjet" if kategoriya == db.UMUMIY_BYUDJET_KALITI else f"\"{kategoriya_matni}\" uchun byudjet"
    await update.message.reply_text(f"✅ {nomi} {summa_formatlash(limit_summa)} so'm qilib belgilandi.")


async def byudjetlar_royxati(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    hozir = datetime.now()
    limitlar = db.barcha_byudjetlar(user_id)

    if not limitlar:
        await update.message.reply_text(
            "Hali byudjet limiti belgilanmagan.\n"
            "Masalan: /byudjet restoran 300000"
        )
        return

    matn = "💼 *Belgilangan byudjet limitlari:*\n\n"
    for row in limitlar:
        kategoriya = row["kategoriya"]
        limit_summa = row["limit_summa"]
        nomi = "Umumiy oylik byudjet" if kategoriya == db.UMUMIY_BYUDJET_KALITI else kategoriya

        if kategoriya == db.UMUMIY_BYUDJET_KALITI:
            natija = db.oylik_hisobot(user_id, hozir.year, hozir.month)
            jami = natija["umumiy_chiqim"]
        else:
            jami = db.kategoriya_oylik_jami(user_id, kategoriya, hozir.year, hozir.month)

        foiz = jami / limit_summa * 100 if limit_summa else 0
        belgi = "🚨" if foiz > 100 else ("⚠️" if foiz >= 80 else "✅")
        matn += f"{belgi} {nomi}: {summa_formatlash(jami)} / {summa_formatlash(limit_summa)} so'm ({foiz:.0f}%)\n"

    await update.message.reply_text(matn, parse_mode="Markdown")


async def oxirgi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    yozuvlar = db.oxirgi_yozuvlar(user_id, limit=10)

    if not yozuvlar:
        await update.message.reply_text("Hali hech qanday yozuv yo'q.")
        return

    matn = "🧾 *Oxirgi yozuvlar:*\n\n"
    for row in yozuvlar:
        emoji = "💰" if row["tur"] == "kirim" else "💸"
        sana = row["sana"].split(" ")[0]
        matn += f"{emoji} {sana} — {summa_formatlash(row['summa'])} so'm — {row['kategoriya']}\n"

    await update.message.reply_text(matn, parse_mode="Markdown")


async def ochir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ochirilgan = db.oxirgisini_ochirish(user_id)

    if not ochirilgan:
        await update.message.reply_text("O'chirish uchun yozuv topilmadi.")
        return

    emoji = "💰" if ochirilgan["tur"] == "kirim" else "💸"
    await update.message.reply_text(
        f"🗑 O'chirildi: {emoji} {summa_formatlash(ochirilgan['summa'])} so'm — {ochirilgan['kategoriya']}"
    )


# --- Tez menyu tugmalari ---

async def menyu_chiqim_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'➕ Chiqim' tugmasi bosilganda tezkor kategoriya tugmalarini ko'rsatadi."""
    tugmalar = [
        InlineKeyboardButton(nomi, callback_data=f"tezkat:chiqim:{nomi.lower()}")
        for nomi in TEZKOR_CHIQIM_KATEGORIYALARI
    ]
    qatorlar = [tugmalar[i:i + 3] for i in range(0, len(tugmalar), 3)]
    await update.message.reply_text(
        "Qaysi toifaga xarajat qildingiz?\n"
        "(yoki shunchaki \"30000 taksi\" deb yozing)",
        reply_markup=InlineKeyboardMarkup(qatorlar)
    )


async def menyu_kirim_boshlash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'➕ Kirim' tugmasi bosilganda tezkor manba tugmalarini ko'rsatadi."""
    tugmalar = [
        InlineKeyboardButton(nomi, callback_data=f"tezkat:kirim:{nomi.lower()}")
        for nomi in TEZKOR_KIRIM_MANBALARI
    ]
    qatorlar = [tugmalar[i:i + 3] for i in range(0, len(tugmalar), 3)]
    await update.message.reply_text(
        "Qayerdan kirim keldi?\n"
        "(yoki shunchaki \"+3000000 oylik\" deb yozing)",
        reply_markup=InlineKeyboardMarkup(qatorlar)
    )


async def tezkor_kategoriya_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tez tugmalardan kategoriya tanlanganda, summani kutish holatiga o'tadi."""
    query = update.callback_query
    await query.answer()

    _, tur, kategoriya = query.data.split(":")
    user_id = query.from_user.id

    KUTILAYOTGAN_KIRITISH[user_id] = {"tur": tur, "kategoriya": kategoriya}
    await query.edit_message_text(f"✅ Tanlandi: {kategoriya}\n\n💬 Endi summani yozing (masalan: 30000)")


async def matn_qabul_qilish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyruqsiz yuborilgan har qanday matnni qayta ishlaydi:
    1) Asosiy menyu tugmalari bosilganini aniqlaydi
    2) Tez tugmadan keyin kutilayotgan summani qabul qiladi
    3) Tabiiy tildagi "summa kategoriya" formatini avtomatik taniydi
    """
    matn = update.message.text.strip()
    user_id = update.effective_user.id

    # 1) Asosiy menyu tugmalari
    menyu_amallari = {
        "➕ Chiqim": menyu_chiqim_boshlash,
        "➕ Kirim": menyu_kirim_boshlash,
        "📊 Hisobot": hisobot,
        "📈 Grafik": grafik,
        "💡 Tahlil": tahlil,
        "🧾 Oxirgi": oxirgi,
    }
    if matn in menyu_amallari:
        await menyu_amallari[matn](update, context)
        return

    # 2) Tez tugmadan keyin faqat summa kutilayotgan bo'lsa
    if user_id in KUTILAYOTGAN_KIRITISH:
        try:
            summa = float(matn.replace(",", "").replace(" ", ""))
            if summa <= 0:
                raise ValueError
        except ValueError:
            await update.message.reply_text("⚠️ Iltimos, faqat summani raqam bilan yozing. Masalan: 30000")
            return

        kutilayotgan = KUTILAYOTGAN_KIRITISH.pop(user_id)
        await _tranzaksiya_saqlash_va_javob(
            update, context, user_id, kutilayotgan["tur"], summa, kutilayotgan["kategoriya"]
        )
        return

    # 3) Tabiiy til: "30000 taksi" -> chiqim, "+3000000 oylik" -> kirim
    tur = "kirim" if matn.startswith("+") else "chiqim"
    matn_tozalangan = matn.lstrip("+").strip()
    qismlar = matn_tozalangan.split(maxsplit=1)

    if len(qismlar) == 2:
        try:
            summa = float(qismlar[0].replace(",", "").replace(" ", ""))
            if summa <= 0:
                raise ValueError
        except ValueError:
            await _nomashum_matn_javobi(update)
            return

        kategoriya = qismlar[1].strip().lower()
        await _tranzaksiya_saqlash_va_javob(update, context, user_id, tur, summa, kategoriya)
        return

    await _nomashum_matn_javobi(update)


async def _nomashum_matn_javobi(update: Update):
    await update.message.reply_text(
        "🤔 Tushunmadim. Quyidagicha yozib ko'ring:\n"
        "• Chiqim: \"30000 taksi\"\n"
        "• Kirim: \"+3000000 oylik\"\n"
        "Yoki pastdagi menyudan foydalaning."
    )


def main():
    if TOKEN == "SIZNING_BOT_TOKENINGIZ_BU_YERGA":
        print("⚠️  DIQQAT: TELEGRAM_BOT_TOKEN o'rnatilmagan!")
        print("BotFather orqali token oling va TELEGRAM_BOT_TOKEN muhit o'zgaruvchisiga yozing,")
        print("yoki bot.py faylida TOKEN qatorini to'g'ridan-to'g'ri tahrirlang.")
        return

    db.init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("yordam", yordam))
    app.add_handler(CommandHandler("kirim", kirim_qoshish))
    app.add_handler(CommandHandler("chiqim", chiqim_qoshish))
    app.add_handler(CommandHandler("hisobot", hisobot))
    app.add_handler(CommandHandler("grafik", grafik))
    app.add_handler(CommandHandler("tahlil", tahlil))
    app.add_handler(CommandHandler("byudjet", byudjet_belgilash))
    app.add_handler(CommandHandler("byudjetlar", byudjetlar_royxati))
    app.add_handler(CommandHandler("toifa", toifa_qoyish))
    app.add_handler(CommandHandler("oxirgi", oxirgi))
    app.add_handler(CommandHandler("ochir", ochir))

    app.add_handler(CallbackQueryHandler(toifa_tanlash_callback, pattern="^toifa:"))
    app.add_handler(CallbackQueryHandler(tezkor_kategoriya_callback, pattern="^tezkat:"))

    # Buyruq bo'lmagan har qanday matnli xabar (menyu tugmalari, tez kiritish, tabiiy til)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, matn_qabul_qilish))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
