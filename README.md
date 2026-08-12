# 💰 Shaxsiy Moliya Monitoring Boti

Telegram orqali kirim va chiqimlaringizni yozib boring — bot avtomatik ravishda
oylik hisobot, rangli grafik, va **qaysi xarajatlarni qisqartirish kerakligi**
bo'yicha aniq tavsiyalar beradi.

## ✨ Imkoniyatlar

- 📊 Oylik hisobot — kirim, chiqim, balans
- 📈 Rangli grafik — xarajatlar kategoriya bo'yicha (yashil = zarur, qizil = keraksiz)
- 💡 Aqlli tahlil — qaysi xarajatni qisqartirsangiz qancha tejashingiz aniq yozib beriladi
- 💼 Byudjet limiti — kategoriya yoki umumiy oylik limit belgilab, oshib ketganda ogohlantirish
- 💬 Tabiiy til bilan yozish — buyruqsiz "30000 taksi" yozsangiz ham tushunadi
- ⚡ Tez tugmalar — bosish orqali tezkor kategoriya tanlash
- 📅 Oylar solishtirmasi — bu oy o'tgan oyga nisbatan qanday

## 🚀 O'rnatish

### 1-qadam: Bot yaratish
1. Telegramda **@BotFather** ga o'ting
2. `/newbot` buyrug'ini yuboring va ko'rsatmalarga amal qiling
3. Sizga beriladigan **tokenni** saqlab qo'ying (masalan: `123456:ABC-DEF1234...`)

### 2-qadam: Kompyuterda sozlash
```bash
cd moliya_bot
pip install -r requirements.txt

# Tokenni muhit o'zgaruvchisiga yozing (Linux/Mac)
export TELEGRAM_BOT_TOKEN="sizning_tokeningiz"

# Windows uchun (PowerShell)
$env:TELEGRAM_BOT_TOKEN="sizning_tokeningiz"
```

Yoki oddiyroq yo'l: `bot.py` faylini oching va shu qatorni tahrirlang:
```python
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "SIZNING_TOKENINGIZ_SHU_YERGA")
```

### 3-qadam: Ishga tushirish
```bash
python bot.py
```

Bot ishga tushgach, Telegramda botingizni topib `/start` bosing.

## 📋 Buyruqlar

| Buyruq | Vazifasi | Misol |
|---|---|---|
| `/start` | Botni ishga tushirish, asosiy menyu | — |
| `/kirim <summa> <manba>` | Kirim qo'shish | `/kirim 3000000 oylik` |
| `/chiqim <summa> <kategoriya>` | Chiqim qo'shish | `/chiqim 25000 taksi` |
| `/hisobot` | Shu oy uchun umumiy hisobot | — |
| `/grafik` | Xarajatlar diagrammasi (rasm) | — |
| `/tahlil` | Nimani qisqartirish kerakligi bo'yicha tavsiya | — |
| `/byudjet <kategoriya> <summa>` | Oylik limit belgilash | `/byudjet restoran 300000` |
| `/byudjet umumiy <summa>` | Umumiy oylik xarajat limiti | `/byudjet umumiy 5000000` |
| `/byudjetlar` | Belgilangan limitlarni ko'rish | — |
| `/toifa <kategoriya> <zarur/keraksiz>` | Kategoriya turini qo'lda belgilash | `/toifa taksi zarur` |
| `/oxirgi` | Oxirgi 10 ta yozuvni ko'rish | — |
| `/ochir` | Oxirgi yozuvni bekor qilish | — |

### 💬 Buyruqsiz (tabiiy til) yozish
- `30000 taksi` → avtomatik chiqim sifatida qo'shiladi
- `+3000000 oylik` → avtomatik kirim sifatida qo'shiladi ("+" belgisi bilan boshlansa kirim deb tushuniladi)

### ⚡ Tez tugmalar
`/start` bosganingizda pastda doimiy menyu chiqadi: ➕ Chiqim, ➕ Kirim, 📊 Hisobot,
📈 Grafik, 💡 Tahlil, 🧾 Oxirgi. "➕ Chiqim" bossangiz eng ko'p ishlatiladigan
kategoriyalar (Ovqat, Transport, Kommunal va h.k.) tugma sifatida chiqadi —
bosib, keyin faqat summani yozasiz.

## 🟢🔴 "Zarur" va "Keraksiz" qanday ishlaydi?

- Ba'zi keng tarqalgan kategoriyalar (ovqat, kommunal, dori va h.k. → zarur;
  restoran, kofe, o'yin-kulgi va h.k. → keraksiz) avtomatik aniqlanadi.
- Boshqa kategoriyalar uchun birinchi marta chiqim qo'shganingizda bot
  tugmalar orqali so'raydi — bir marta tanlasangiz, o'sha kategoriya uchun eslab qoladi.
- Istalgan vaqt `/toifa <kategoriya> <zarur yoki keraksiz>` bilan o'zgartirish mumkin.
- `/grafik` va `/tahlil` shu belgilar asosida sizga qaysi xarajatlarni
  qisqartirish foydali ekanini ko'rsatadi.

## 🗄️ Ma'lumotlar qayerda saqlanadi?

Barcha yozuvlar `moliya.db` nomli SQLite faylida saqlanadi (bot ishga tushgan
papkada avtomatik yaratiladi). Har bir Telegram foydalanuvchisining ma'lumotlari
alohida saqlanadi — hech kim boshqasining yozuvlarini ko'ra olmaydi.

⚠️ **Eslatma:** tez tugma orqali kategoriya tanlab, summani hali kiritmagan holat
(`KUTILAYOTGAN_KIRITISH`) xotirada (RAM) saqlanadi — bot qayta ishga tushirilsa
bu holat yo'qoladi, lekin allaqachon saqlangan yozuvlar va byudjetlar bazada
xavfsiz qoladi.

## ☁️ 24/7 ishlashi uchun

Botni doim ishlab turishi uchun uni serverda joylashtirish kerak:
- **Railway.app** yoki **Render.com** — oddiy Python loyihalarini bepul (limitlar bilan) joylashtirish
- O'z VPS serveringiz bo'lsa, `systemd` yoki `screen`/`tmux` orqali fonda ishlatish

## 🔧 Keyingi bosqichda qo'shilishi mumkin bo'lgan funksiyalar

- Qarz/qarzdorlik kuzatuvi
- Moliyaviy maqsad qo'yish (masalan "50 mln yig'ish")
- Takrorlanuvchi xarajatlarni avtomatik qo'shish (ijarangiz, internet va h.k.)
- Yozuvlarni tahrirlash va qidirish
- PIN-kod bilan himoyalash
- `/backup` — ma'lumotlarni yuklab olish
- Bir necha valyutada hisob yuritish
- Chek rasmi orqali summani avtomatik o'qish (OCR)

