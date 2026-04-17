import logging
import re
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import (
    PORT,
    TOKEN,
    USE_WEBHOOK,
    WEBHOOK_PATH,
    WEBHOOK_SECRET,
    WEBHOOK_URL,
)
from db import (
    add_transaction,
    check_connection,
    create_tables,
    get_report,
    get_stats,
    get_stats_by_days,
    upsert_user,
)


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


ACTION_LABELS = {
    "kirim": "➕ Kirim qo'shish",
    "chiqim": "➖ Chiqim qo'shish",
    "qarz_berdim": "🤝 Qarz berdim",
    "qarz_oldim": "🤲 Qarz oldim",
}

BUTTON_TO_ACTION = {label: action for action, label in ACTION_LABELS.items()}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ["➕ Kirim qo'shish", "➖ Chiqim qo'shish"],
        ["🤝 Qarz berdim", "🤲 Qarz oldim"],
        ["📊 Analiz", "📜 Report"],
        ["📅 Oylik", "❓ Yordam"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def entry_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [["⬅️ Bekor qilish"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def save_user(update: Update):
    user = update.message.from_user
    upsert_user(
        user_id=user.id,
        full_name=user.full_name or "",
        username=user.username or "",
    )


def parse_amount_note(text: str):
    m = re.match(r"^\s*([0-9]+)(?:\s+(.+))?\s*$", text)
    if not m:
        return None, None
    amount = int(m.group(1))
    note = (m.group(2) or "").strip() or "Izohsiz"
    return amount, note


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    context.user_data.pop("pending_action", None)

    text = (
        "👋 Assalomu alaykum!\n"
        "Shaxsiy moliya botiga xush kelibsiz.\n\n"
        "Bu yerda barcha amallar tugmalar orqali qulay ishlaydi:\n"
        "- ➕ Kirim qo'shish\n"
        "- ➖ Chiqim qo'shish\n"
        "- 🤝 Qarz berdim\n"
        "- 🤲 Qarz oldim\n\n"
        "Pastdagi menyudan kerakli tugmani bosing ✅"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def help_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ Yordam\n\n"
        "1) Eng oson usul: pastdagi tugmalarni bosing.\n"
        "2) Tugmadan keyin yozing: `miqdor izoh`\n"
        "   Masalan: `250000 oylik`\n\n"
        "Qo'lda yozish ham ishlaydi:\n"
        "- `+250000 oylik`\n"
        "- `-80000 market`\n"
        "- `qarz_berdim 300000 Aliga`\n"
        "- `qarz_oldim 100000 ukamdan`\n\n"
        "Hisobotlar:\n"
        "- /analiz\n"
        "- /report\n"
        "- /oylik"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


async def report_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    rows = get_report(uid, limit=10)

    if not rows:
        await update.message.reply_text(
            "📭 Hali yozuv yo'q. Pastdagi tugmalardan biri bilan boshlang.",
            reply_markup=main_menu_keyboard(),
        )
        return

    icon_map = {
        "kirim": "💰",
        "chiqim": "💸",
        "qarz_berdim": "🤝",
        "qarz_oldim": "🤲",
    }

    lines = ["📜 Oxirgi 10 ta amal:\n"]
    for sana, tur, miqdor, izoh in rows:
        icon = icon_map.get(tur, "📌")
        sana_str = sana.strftime("%d.%m.%Y %H:%M")
        lines.append(
            f"{icon} {sana_str}\n"
            f"   {tur.upper()}: {miqdor:,} so'm\n"
            f"   Izoh: {izoh or '—'}\n"
        )

    await update.message.reply_text("\n".join(lines), reply_markup=main_menu_keyboard())


async def analiz_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    stats = get_stats(uid)

    if not stats:
        await update.message.reply_text(
            "📭 Hali ma'lumot yo'q. Avval bir amal kiriting.",
            reply_markup=main_menu_keyboard(),
        )
        return

    kirim = stats.get("kirim", 0) or 0
    chiqim = stats.get("chiqim", 0) or 0
    qarz_berdim = stats.get("qarz_berdim", 0) or 0
    qarz_oldim = stats.get("qarz_oldim", 0) or 0

    balans = kirim - chiqim
    sof_qarz = qarz_berdim - qarz_oldim

    if balans > 0:
        balans_icon = "📈"
    elif balans < 0:
        balans_icon = "📉"
    else:
        balans_icon = "➡️"

    text = (
        "📊 Umumiy hisob:\n\n"
        f"💰 Jami kirim: {kirim:,} so'm\n"
        f"💸 Jami chiqim: {chiqim:,} so'm\n"
        "━━━━━━━━━━━━━━\n"
        f"{balans_icon} Sof balans: {balans:,} so'm\n\n"
        f"🤝 Bergan qarz: {qarz_berdim:,} so'm\n"
        f"🤲 Olgan qarz: {qarz_oldim:,} so'm\n"
        "━━━━━━━━━━━━━━\n"
        f"📌 Qarz saldosi: {sof_qarz:,} so'm"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def oylik_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    stats = get_stats_by_days(uid, kunlar=30)

    if not stats:
        await update.message.reply_text(
            "📭 Oxirgi 30 kunda yozuv topilmadi.",
            reply_markup=main_menu_keyboard(),
        )
        return

    kirim = stats.get("kirim", 0) or 0
    chiqim = stats.get("chiqim", 0) or 0
    qarz_berdim = stats.get("qarz_berdim", 0) or 0
    qarz_oldim = stats.get("qarz_oldim", 0) or 0
    balans = kirim - chiqim

    text = (
        "📅 Oxirgi 30 kun:\n\n"
        f"💰 Kirim: {kirim:,} so'm\n"
        f"💸 Chiqim: {chiqim:,} so'm\n"
        "━━━━━━━━━━━━━━\n"
        f"💳 Balans: {balans:,} so'm\n\n"
        f"🤝 Qarz berdim: {qarz_berdim:,} so'm\n"
        f"🤲 Qarz oldim: {qarz_oldim:,} so'm"
    )
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())


async def handle_guided_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    amount, note = parse_amount_note(update.message.text.strip())
    if amount is None:
        await update.message.reply_text(
            "❌ Format noto'g'ri. Masalan: `150000 oylik`",
            parse_mode="Markdown",
            reply_markup=entry_keyboard(),
        )
        return

    uid = update.message.from_user.id
    ok = add_transaction(uid, action, amount, note)
    if not ok:
        await update.message.reply_text(
            "⚠️ Saqlashda xatolik bo'ldi. Qayta urinib ko'ring.",
            reply_markup=main_menu_keyboard(),
        )
        context.user_data.pop("pending_action", None)
        return

    title = {
        "kirim": "✅ Kirim saqlandi",
        "chiqim": "✅ Chiqim saqlandi",
        "qarz_berdim": "✅ Qarz berdim yozildi",
        "qarz_oldim": "✅ Qarz oldim yozildi",
    }.get(action, "✅ Amal saqlandi")

    await update.message.reply_text(
        f"{title}\n💵 {amount:,} so'm\n📝 {note}",
        reply_markup=main_menu_keyboard(),
    )
    context.user_data.pop("pending_action", None)


async def handle_manual_patterns(update: Update):
    text = update.message.text.strip()
    uid = update.message.from_user.id

    if text.startswith("+"):
        m = re.match(r"\+([0-9]+)(?:\s+(.+))?", text)
        if not m:
            await update.message.reply_text(
                "❌ Format: `+150000 oylik maosh`",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return True

        miqdor = int(m.group(1))
        izoh = (m.group(2) or "").strip() or "Izohsiz"
        if add_transaction(uid, "kirim", miqdor, izoh):
            await update.message.reply_text(
                f"✅ Kirim saqlandi\n💰 {miqdor:,} so'm\n📝 {izoh}",
                reply_markup=main_menu_keyboard(),
            )
        return True

    if text.startswith("-"):
        m = re.match(r"-([0-9]+)(?:\s+(.+))?", text)
        if not m:
            await update.message.reply_text(
                "❌ Format: `-45000 taksi`",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return True

        miqdor = int(m.group(1))
        izoh = (m.group(2) or "").strip() or "Izohsiz"
        if add_transaction(uid, "chiqim", miqdor, izoh):
            await update.message.reply_text(
                f"✅ Chiqim saqlandi\n💸 {miqdor:,} so'm\n📝 {izoh}",
                reply_markup=main_menu_keyboard(),
            )
        return True

    if text.lower().startswith("qarz_berdim"):
        m = re.match(r"qarz_berdim\s+([0-9]+)(?:\s+(.+))?", text, re.IGNORECASE)
        if not m:
            await update.message.reply_text(
                "❌ Format: `qarz_berdim 500000 Sardorga`",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return True

        miqdor = int(m.group(1))
        izoh = (m.group(2) or "").strip() or "Izohsiz"
        if add_transaction(uid, "qarz_berdim", miqdor, izoh):
            await update.message.reply_text(
                f"✅ Qarz berdingiz yozildi\n🤝 {miqdor:,} so'm\n📝 {izoh}",
                reply_markup=main_menu_keyboard(),
            )
        return True

    if text.lower().startswith("qarz_oldim"):
        m = re.match(r"qarz_oldim\s+([0-9]+)(?:\s+(.+))?", text, re.IGNORECASE)
        if not m:
            await update.message.reply_text(
                "❌ Format: `qarz_oldim 200000 ukamdan`",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard(),
            )
            return True

        miqdor = int(m.group(1))
        izoh = (m.group(2) or "").strip() or "Izohsiz"
        if add_transaction(uid, "qarz_oldim", miqdor, izoh):
            await update.message.reply_text(
                f"✅ Qarz oldingiz yozildi\n🤲 {miqdor:,} so'm\n📝 {izoh}",
                reply_markup=main_menu_keyboard(),
            )
        return True

    return False


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    save_user(update)
    text = update.message.text.strip()

    if text == "⬅️ Bekor qilish":
        context.user_data.pop("pending_action", None)
        await update.message.reply_text("Bekor qilindi.", reply_markup=main_menu_keyboard())
        return

    if text in BUTTON_TO_ACTION:
        action = BUTTON_TO_ACTION[text]
        context.user_data["pending_action"] = action
        await update.message.reply_text(
            f"{text} tanlandi.\nEndi yozing: `miqdor izoh`\nMasalan: `150000 oylik`",
            parse_mode="Markdown",
            reply_markup=entry_keyboard(),
        )
        return

    if text == "📊 Analiz":
        await analiz_cmd(update, context)
        return

    if text == "📜 Report":
        await report_cmd(update, context)
        return

    if text == "📅 Oylik":
        await oylik_cmd(update, context)
        return

    if text == "❓ Yordam":
        await help_cmd(update, context)
        return

    pending_action = context.user_data.get("pending_action")
    if pending_action:
        await handle_guided_entry(update, context, pending_action)
        return

    handled = await handle_manual_patterns(update)
    if handled:
        return

    await update.message.reply_text(
        "❓ Xabarni tushunmadim. Pastdagi tugmalardan foydalaning yoki /help ni bosing.",
        reply_markup=main_menu_keyboard(),
    )


def main():
    log.info("Bot ishga tushmoqda...")

    ok, reason = check_connection()
    if not ok:
        log.error("DB ulanish xatosi: %s", reason)
        log.error("Bot to'xtatildi. .env dagi DB sozlamalarini tekshiring.")
        return

    if not create_tables():
        log.error("DB jadvallarini tayyorlab bo'lmadi. Bot to'xtatildi.")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("analiz", analiz_cmd))
    app.add_handler(CommandHandler("oylik", oylik_cmd))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if USE_WEBHOOK:
        if not WEBHOOK_URL:
            log.error("USE_WEBHOOK=true bo'lsa WEBHOOK_URL majburiy.")
            return

        clean_base = WEBHOOK_URL.rstrip("/")
        clean_path = WEBHOOK_PATH if WEBHOOK_PATH.startswith("/") else f"/{WEBHOOK_PATH}"
        full_webhook_url = f"{clean_base}{clean_path}"

        log.info("Bot webhook rejimida ishga tushmoqda...")
        log.info("Webhook URL: %s", full_webhook_url)

        app.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            url_path=clean_path.lstrip("/"),
            webhook_url=full_webhook_url,
            secret_token=WEBHOOK_SECRET or None,
            allowed_updates=Update.ALL_TYPES,
        )
        return

    log.info("Bot polling rejimida boshlandi. To'xtatish: Ctrl+C")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
