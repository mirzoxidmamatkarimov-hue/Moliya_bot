"""
Xarajatlar tahlili uchun grafik (diagramma) yaratish moduli.
Matplotlib yordamida tushunarli, rangli ustunli diagramma chizadi:
yashil = zarur xarajat, qizil = keraksiz xarajat, kulrang = noma'lum.
"""
import io
import matplotlib
matplotlib.use("Agg")  # Server rejimida ishlash uchun (oyna ochilmaydi)
import matplotlib.pyplot as plt

RANG_ZARUR = "#2ecc71"      # yashil
RANG_KERAKSIZ = "#e74c3c"   # qizil
RANG_NOMALUM = "#95a5a6"    # kulrang


def _summa_qisqa(summa: float) -> str:
    """Katta sonlarni qisqa formatda ko'rsatadi: 1250000 -> 1.25 mln"""
    if summa >= 1_000_000:
        return f"{summa / 1_000_000:.2f} mln"
    if summa >= 1_000:
        return f"{summa / 1_000:.0f} ming"
    return f"{summa:.0f}"


def xarajatlar_grafigi(kategoriyalar: list, oy_nomi: str, yil: int) -> io.BytesIO:
    """
    Xarajatlarni kategoriya bo'yicha gorizontal ustunli diagramma sifatida chizadi.
    kategoriyalar: [{"kategoriya": str, "jami": float, "holat": "zarur"/"keraksiz"/None}, ...]
    Eng katta xarajat yuqorida chiqadi.
    Rasm baytlar (BytesIO) ko'rinishida qaytariladi — to'g'ridan-to'g'ri Telegramga yuborish uchun.
    """
    # Kattadan kichikka saralab, diagrammada yuqoridan pastga to'g'ri tartibda chiqishi uchun teskarisiga aylantiramiz
    data = sorted(kategoriyalar, key=lambda x: x["jami"])

    nomlar = [d["kategoriya"].capitalize() for d in data]
    qiymatlar = [d["jami"] for d in data]
    ranglar = []
    for d in data:
        if d["holat"] == "zarur":
            ranglar.append(RANG_ZARUR)
        elif d["holat"] == "keraksiz":
            ranglar.append(RANG_KERAKSIZ)
        else:
            ranglar.append(RANG_NOMALUM)

    balandlik = max(3, 0.6 * len(nomlar) + 1.5)
    fig, ax = plt.subplots(figsize=(8, balandlik), dpi=150)

    bars = ax.barh(nomlar, qiymatlar, color=ranglar, edgecolor="white", height=0.65)

    # Har bir ustun oxiriga summani yozib qo'yamiz
    maks_qiymat = max(qiymatlar) if qiymatlar else 1
    for bar, qiymat in zip(bars, qiymatlar):
        ax.text(
            bar.get_width() + maks_qiymat * 0.015,
            bar.get_y() + bar.get_height() / 2,
            _summa_qisqa(qiymat),
            va="center", ha="left", fontsize=9, color="#333333"
        )

    ax.set_xlim(0, maks_qiymat * 1.22)
    ax.set_title(f"Xarajatlar tahlili — {oy_nomi} {yil}", fontsize=13, fontweight="bold", pad=14)
    ax.set_xlabel("Summa (so'm)", fontsize=9)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", labelsize=10)
    ax.tick_params(axis="x", labelsize=8)
    ax.xaxis.set_visible(False)
    ax.grid(False)

    # Rang tushuntirish (legend) qo'shamiz
    legend_elementlar = [
        plt.Rectangle((0, 0), 1, 1, color=RANG_ZARUR, label="Zarur xarajat"),
        plt.Rectangle((0, 0), 1, 1, color=RANG_KERAKSIZ, label="Keraksiz xarajat"),
        plt.Rectangle((0, 0), 1, 1, color=RANG_NOMALUM, label="Belgilanmagan"),
    ]
    ax.legend(handles=legend_elementlar, loc="lower right", fontsize=8, frameon=False)

    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def zarur_keraksiz_doira(zarur: float, keraksiz: float, nomalum: float, oy_nomi: str, yil: int) -> io.BytesIO:
    """
    Umumiy chiqimni 'zarur / keraksiz / belgilanmagan' ulushlariga ajratib doira diagramma chizadi.
    """
    qiymatlar = []
    etiketlar = []
    ranglar = []

    if zarur > 0:
        qiymatlar.append(zarur)
        etiketlar.append("Zarur")
        ranglar.append(RANG_ZARUR)
    if keraksiz > 0:
        qiymatlar.append(keraksiz)
        etiketlar.append("Keraksiz")
        ranglar.append(RANG_KERAKSIZ)
    if nomalum > 0:
        qiymatlar.append(nomalum)
        etiketlar.append("Belgilanmagan")
        ranglar.append(RANG_NOMALUM)

    fig, ax = plt.subplots(figsize=(5, 5), dpi=150)
    wedges, texts, autotexts = ax.pie(
        qiymatlar,
        labels=etiketlar,
        colors=ranglar,
        autopct="%1.0f%%",
        startangle=90,
        textprops={"fontsize": 10},
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontweight("bold")

    ax.set_title(f"Umumiy chiqim taqsimoti — {oy_nomi} {yil}", fontsize=12, fontweight="bold", pad=12)
    ax.axis("equal")

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf
