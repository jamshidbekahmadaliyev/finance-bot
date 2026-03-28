# =====================================================
# main.py — Telegram Bot asosiy fayli
# =====================================================

import re
import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from config import TOKEN
from db import create_tables, upsert_user, add_transaction, get_report, get_stats, get_stats_by_days

# Log — xatolarni ko'rish uchun
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),   # bot.log fayliga yozadi
        logging.StreamHandler()            # terminalga ham chiqaradi
    ]
)
log = logging.getLogger(__name__)


# ======================================================
# YORDAMCHI: Foydalanuvchini bazaga yozib olish
# ======================================================
def save_user(update: Update):
    """Har safar xabar kelganda foydalanuvchini saqlab qo'yadi."""
    user = update.message.from_user
    upsert_user(
        user_id=user.id,
        full_name=user.full_name or "",
        username=user.username or ""
    )


# ======================================================
# /start buyrug'i
# ======================================================
async def start(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    text = (
        "👋 Assalomu alaykum!\n"
        "Shaxsiy moliya botingizga xush kelibsiz! 💰\n\n"
        "📌 *Qanday ishlatiladi:*\n\n"
        "➕ Kirim:       +150000 oylik maosh\n"
        "➖ Chiqim:      -45000 supermarket\n"
        "🤝 Qarz berdim: qarz_berdim 500000 Sardorga\n"
        "🤲 Qarz oldim:  qarz_oldim 200000 Sardordan\n\n"
        "📊 Buyruqlar:\n"
        "/analiz — Umumiy hisob\n"
        "/report — Oxirgi 10 ta amal\n"
        "/oylik  — Shu oylik hisobot\n"
        "/help   — Yordam\n\n"
        "Boshladikmi? 🚀"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ======================================================
# /help buyrug'i
# ======================================================
async def help_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    text = (
        "📖 *Yordam:*\n\n"
        "*Kirim qo'shish:*\n"
        "`+miqdor izoh`\n"
        "Misol: `+2500000 oylik maosh`\n\n"
        "*Chiqim qo'shish:*\n"
        "`-miqdor izoh`\n"
        "Misol: `-80000 restoran`\n\n"
        "*Qarz berganingiz:*\n"
        "`qarz_berdim miqdor izoh`\n"
        "Misol: `qarz_berdim 300000 Alishirga`\n\n"
        "*Qarz olganingiz:*\n"
        "`qarz_oldim miqdor izoh`\n"
        "Misol: `qarz_oldim 500000 ukamdan`\n\n"
        "*Hisobotlar:*\n"
        "/analiz — Umumiy balans\n"
        "/report — Oxirgi 10 ta yozuv\n"
        "/oylik  — Oxirgi 30 kunlik statistika"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ======================================================
# Xabarlarni qayta ishlash (kirim/chiqim/qarz)
# ======================================================
async def handle_message(update: Update, _: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    save_user(update)
    text = update.message.text.strip()
    uid = update.message.from_user.id

    # 1. Kirim: +150000 oylik
    if text.startswith("+"):
        m = re.match(r"\+([0-9]+)(?:\s+(.+))?", text)
        if m:
            miqdor = int(m.group(1))
            izoh = (m.group(2) or "").strip() or "Izohsiz"
            ok = add_transaction(uid, "kirim", miqdor, izoh)
            if ok:
                await update.message.reply_text(
                    f"✅ *Kirim saqlandi!*\n"
                    f"💰 {miqdor:,} so'm\n"
                    f"📝 {izoh}",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ Format: `+150000 oylik maosh`", parse_mode="Markdown")
        return

    # 2. Chiqim: -45000 taksi
    if text.startswith("-"):
        m = re.match(r"-([0-9]+)(?:\s+(.+))?", text)
        if m:
            miqdor = int(m.group(1))
            izoh = (m.group(2) or "").strip() or "Izohsiz"
            ok = add_transaction(uid, "chiqim", miqdor, izoh)
            if ok:
                await update.message.reply_text(
                    f"✅ *Chiqim saqlandi!*\n"
                    f"💸 {miqdor:,} so'm\n"
                    f"📝 {izoh}",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ Format: `-45000 taksi`", parse_mode="Markdown")
        return

    # 3. Qarz berdim: qarz_berdim 500000 Sardorga
    if text.lower().startswith("qarz_berdim"):
        m = re.match(r"qarz_berdim\s+([0-9]+)(?:\s+(.+))?", text, re.IGNORECASE)
        if m:
            miqdor = int(m.group(1))
            izoh = (m.group(2) or "").strip() or "Izohsiz"
            ok = add_transaction(uid, "qarz_berdim", miqdor, izoh)
            if ok:
                await update.message.reply_text(
                    f"✅ *Qarz berganingiz yozildi!*\n"
                    f"🤝 {miqdor:,} so'm\n"
                    f"📝 {izoh}",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ Format: `qarz_berdim 500000 Sardorga`", parse_mode="Markdown")
        return

    # 4. Qarz oldim: qarz_oldim 200000 onamdan
    if text.lower().startswith("qarz_oldim"):
        m = re.match(r"qarz_oldim\s+([0-9]+)(?:\s+(.+))?", text, re.IGNORECASE)
        if m:
            miqdor = int(m.group(1))
            izoh = (m.group(2) or "").strip() or "Izohsiz"
            ok = add_transaction(uid, "qarz_oldim", miqdor, izoh)
            if ok:
                await update.message.reply_text(
                    f"✅ *Qarz olganingiz yozildi!*\n"
                    f"🤲 {miqdor:,} so'm\n"
                    f"📝 {izoh}",
                    parse_mode="Markdown"
                )
        else:
            await update.message.reply_text("❌ Format: `qarz_oldim 200000 onamdan`", parse_mode="Markdown")
        return

    # Tushunilmagan xabar
    await update.message.reply_text(
        "❓ Xabarni tushunmadim.\n\n"
        "Ko'rsatmalar uchun /help buyrug'ini bering."
    )


# ======================================================
# /report — Oxirgi 10 ta yozuv
# ======================================================
async def report_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    rows = get_report(uid, limit=10)

    if not rows:
        await update.message.reply_text(
            "📭 Hali hech qanday yozuv yo'q.\n"
            "Birinchi yozuvni qo'shing: `+100000 maosh`",
            parse_mode="Markdown"
        )
        return

    # Ikonkalar tur bo'yicha
    ikonka = {
        "kirim":       "💰",
        "chiqim":      "💸",
        "qarz_berdim": "🤝",
        "qarz_oldim":  "🤲",
    }

    lines = ["📜 *Oxirgi 10 ta amal:*\n"]
    for sana, tur, miqdor, izoh in rows:
        icon = ikonka.get(tur, "📌")
        sana_str = sana.strftime("%d.%m.%Y %H:%M")
        lines.append(
            f"{icon} `{sana_str}`\n"
            f"   {tur.upper()}: *{miqdor:,} so'm*\n"
            f"   📝 {izoh or '—'}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


# ======================================================
# /analiz — Umumiy balans va statistika
# ======================================================
async def analiz_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    stats = get_stats(uid)

    if not stats:
        await update.message.reply_text(
            "📭 Hali ma'lumot yo'q. Biror narsa yozing:\n`+100000 maosh`",
            parse_mode="Markdown"
        )
        return

    kirim      = stats.get("kirim", 0) or 0
    chiqim     = stats.get("chiqim", 0) or 0
    qarz_berdim = stats.get("qarz_berdim", 0) or 0
    qarz_oldim  = stats.get("qarz_oldim", 0) or 0

    balans = kirim - chiqim
    sof_qarz = qarz_berdim - qarz_oldim   # men boshqalarga bergan qarz

    # Balans ko'rsatkichi
    if balans > 0:
        balans_icon = "📈"
    elif balans < 0:
        balans_icon = "📉"
    else:
        balans_icon = "➡️"

    text = (
        f"📊 *Sizning umumiy hisobingiz:*\n\n"
        f"💰 Jami kirim:   *{kirim:,} so'm*\n"
        f"💸 Jami chiqim:  *{chiqim:,} so'm*\n"
        f"━━━━━━━━━━━━━━\n"
        f"{balans_icon} Sof balans:  *{balans:,} so'm*\n\n"
        f"🤝 Bergan qarzlarim: *{qarz_berdim:,} so'm*\n"
        f"🤲 Olgan qarzlarim:  *{qarz_oldim:,} so'm*\n"
        f"━━━━━━━━━━━━━━\n"
        f"📌 Qarz saldosi: *{sof_qarz:,} so'm*\n"
        f"_(men boshqalarga bergan, hali qaytmagan)_"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ======================================================
# /oylik — Oxirgi 30 kunlik hisobot
# ======================================================
async def oylik_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    stats = get_stats_by_days(uid, kunlar=30)

    if not stats:
        await update.message.reply_text("📭 Oxirgi 30 kunda yozuv topilmadi.")
        return

    kirim      = stats.get("kirim", 0) or 0
    chiqim     = stats.get("chiqim", 0) or 0
    qarz_berdim = stats.get("qarz_berdim", 0) or 0
    qarz_oldim  = stats.get("qarz_oldim", 0) or 0
    balans = kirim - chiqim

    text = (
        f"📅 *Oxirgi 30 kunlik hisobot:*\n\n"
        f"💰 Kirim:   *{kirim:,} so'm*\n"
        f"💸 Chiqim:  *{chiqim:,} so'm*\n"
        f"━━━━━━━━━━━━━━\n"
        f"💳 Balans:  *{balans:,} so'm*\n\n"
        f"🤝 Qarz berdim: *{qarz_berdim:,} so'm*\n"
        f"🤲 Qarz oldim:  *{qarz_oldim:,} so'm*"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ======================================================
# ASOSIY FUNKSIYA
# ======================================================
def main():
    log.info("Bot ishga tushmoqda...")

    # Jadvallarni yaratish (birinchi ishga tushishda)
    create_tables()

    # Bot ilovasi
    app = ApplicationBuilder().token(TOKEN).build()

    # Buyruqlar
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("help",   help_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("analiz", analiz_cmd))
    app.add_handler(CommandHandler("oylik",  oylik_cmd))

    # Oddiy xabarlar
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    log.info("Bot polling boshlandi. To'xtatish: Ctrl+C")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
