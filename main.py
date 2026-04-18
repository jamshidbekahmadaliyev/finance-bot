import logging
import re
from datetime import datetime, time as dt_time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Defaults,
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
    get_daily_expense_series,
    get_loans_by_person,
    get_month_report,
    get_report,
    get_report_by_range,
    get_spent_today,
    get_summary,
    get_user_profile,
    is_reminder_sent_today,
    list_users_for_daily_reminder,
    mark_reminder_sent_today,
    set_opening_balance,
    set_remind_daily,
    set_reminder_time,
    set_spend_limit_daily,
    upsert_user,
)


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
    handlers=[logging.FileHandler("bot.log"), logging.StreamHandler()],
)
log = logging.getLogger(__name__)

try:
    UZ_TZ = ZoneInfo("Asia/Tashkent")
except ZoneInfoNotFoundError:
    UZ_TZ = timezone(timedelta(hours=5), name="Asia/Tashkent")

CATEGORIES = ["ovqat", "transport", "ijara", "oqish", "sogliq", "kommunal", "boshqa"]
ACTION_BUTTONS = {
    "➕ Kirim qo'shish": "kirim",
    "➖ Chiqim qo'shish": "chiqim",
    "🤝 Qarz berdim": "qarz_berdim",
    "💳 Qarz oldim": "qarz_oldim",
}

BOT_SHORT_DESCRIPTION = "Shaxsiy moliya boti: kirim, chiqim, qarz, balans"
BOT_DESCRIPTION = (
    "Shaxsiy pulingizni boshqarish uchun bot.\n"
    "Kirim/chiqim va qarzlarni saqlaydi, balansni avtomatik hisoblaydi.\n"
    "Hisobotlar orqali pul qayerdan kelgani va qayerga ketganini ko'rsatadi."
)


def menu_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        ["➕ Kirim qo'shish", "➖ Chiqim qo'shish"],
        ["🤝 Qarz berdim", "💳 Qarz oldim"],
        ["📊 Dashboard", "📜 Report (50)"],
        ["📅 Oylik", "🧾 Davr bo'yicha"],
        ["💵 Boshlang'ich balans", "🎯 Kunlik limit"],
        ["⏰ Eslatma vaqti", "🔔 Eslatma ON/OFF"],
        ["💰 Balans", "🔔 Eslatma"],
        ["❓ Yordam"],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["⬅️ Bekor qilish"]], resize_keyboard=True)


def fmt_money(amount: int) -> str:
    return f"{amount:,} so'm"


def trx_sign(trx_type: str) -> str:
    if trx_type in {"kirim", "qarz_oldim"}:
        return "+"
    return "-"


def parse_amount_category_note(text: str):
    m = re.match(r"^\s*([0-9]+)(?:\s+([\w'-]+))?(?:\s+(.+))?\s*$", text)
    if not m:
        return None, None, None
    amount = int(m.group(1))
    category = (m.group(2) or "boshqa").lower().strip()
    note = (m.group(3) or "").strip() or "Izohsiz"
    if category not in CATEGORIES:
        note = f"{category} {note}".strip()
        category = "boshqa"
    return amount, category, note


def parse_amount_person_note(text: str):
    m = re.match(r"^\s*([0-9]+)\s+([^\d\s][^\s]*)(?:\s+(.+))?\s*$", text)
    if not m:
        return None, None, None
    amount = int(m.group(1))
    person = m.group(2).strip()
    note = (m.group(3) or "").strip() or "Izohsiz"
    return amount, person, note


def parse_hhmm(value: str) -> bool:
    return re.match(r"^([01]\d|2[0-3]):([0-5]\d)$", value) is not None


def balance_line(user_id: int) -> str:
    profile = get_user_profile(user_id)
    return f"💼 Qolgan balans: {fmt_money(profile['current_balance'])}"


def build_ascii_expense_chart(points: list) -> str:
    if not points:
        return "(ma'lumot yo'q)"
    vals = [int(v or 0) for _, v in points]
    max_val = max(vals) if max(vals) > 0 else 1
    lines = []
    for d, val in points[-14:]:
        bars = int((val / max_val) * 12)
        block = "#" * bars if bars > 0 else "."
        lines.append(f"{d.strftime('%d.%m')} {block} {val:,}")
    return "\n".join(lines)


def render_tx_list(rows: list, title: str, max_items: int = 25) -> str:
    icon = {
        "kirim": "💰",
        "chiqim": "💸",
        "qarz_berdim": "🤝",
        "qarz_oldim": "💳",
    }
    lines = [title]
    for sana, tur, miqdor, kategoriya, counterpart, izoh, balance_after in rows[:max_items]:
        lines.append(f"\n{icon.get(tur, '📌')} {sana.strftime('%d.%m %H:%M')}")
        lines.append(f"- Tur: {tur}")
        lines.append(f"- Miqdor: {trx_sign(tur)}{fmt_money(int(miqdor or 0))}")
        lines.append(f"- Kategoriya: {kategoriya or 'boshqa'}")
        if counterpart:
            lines.append(f"- Kim: {counterpart}")
        lines.append(f"- Izoh: {izoh or '-'}")
        lines.append(f"- Balans: {fmt_money(int(balance_after or 0))}")
    return "\n".join(lines)


def save_user(update: Update):
    user = update.message.from_user
    upsert_user(user.id, user.full_name or "", user.username or "")


async def configure_bot_profile(app):
    try:
        await app.bot.set_my_short_description(BOT_SHORT_DESCRIPTION)
        await app.bot.set_my_description(BOT_DESCRIPTION)
    except Exception as e:
        log.warning("Bot description sozlanmadi: %s", e)


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    context.user_data.pop("pending_action", None)
    uid = update.message.from_user.id
    profile = get_user_profile(uid)
    bal_tip = "Avval balansni kiriting: /setbalans 5000000" if not profile.get("has_opening_balance") else balance_line(uid)
    text = (
        "👋 Assalomu alaykum!\n"
        "Bu botning maqsadi:\n"
        "1) Kirim/chiqim va qarzlarni aniq yuritish\n"
        "2) Har doim qolgan balansni ko'rib borish\n"
        "3) Pul qayerdan kelib, qayerga ketganini hisobotda ko'rish\n\n"
        f"{bal_tip}\n"
        "So'ng pastdagi 4 asosiy tugma bilan ishlaysiz."
    )
    await update.message.reply_text(text, reply_markup=menu_keyboard())


async def help_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    uid = update.message.from_user.id
    text = (
        "❓ Yordam (aniq ishlatish)\n\n"
        "Asosiy 4 amal:\n"
        "- ➕ Kirim\n- ➖ Chiqim\n- 🤝 Qarz berdim\n- 💳 Qarz oldim\n\n"
        "Kirim/Chiqim formati: `miqdor kategoriya izoh`\n"
        "Misol: `120000 ovqat tushlik`\n\n"
        "Qarz formati: `miqdor ism izoh`\n"
        "Misol: `500000 Sardor qaytaradi`\n\n"
        "Tugmalar orqali ishlatsangiz bo'ladi, buyruqlar majburiy emas.\n"
        "Agar buyruq bilan ishlatsangiz:\n"
        "- /setbalans 5000000\n"
        "- /report 50\n"
        "- /oylik 2026-04\n"
        "- /davr 2026-04-01 2026-04-30\n"
        "- /setlimit 300000\n"
        "- /setreminder 21:30\n"
        "- /remindon yoki /remindoff\n\n"
        f"{balance_line(uid)}"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=menu_keyboard())


async def set_balance_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    if not context.args:
        await update.message.reply_text("❌ Format: /setbalans 5000000", reply_markup=menu_keyboard())
        return
    raw = context.args[0].replace("_", "").replace(" ", "")
    if not raw.isdigit():
        await update.message.reply_text("❌ Miqdorni raqam bilan kiriting. Masalan: /setbalans 5000000", reply_markup=menu_keyboard())
        return
    amount = int(raw)
    if amount < 0:
        await update.message.reply_text("❌ Balans manfiy bo'lmaydi.", reply_markup=menu_keyboard())
        return
    ok = set_opening_balance(uid, amount)
    if not ok:
        await update.message.reply_text("⚠️ Balans saqlanmadi.", reply_markup=menu_keyboard())
        return
    await update.message.reply_text(
        f"✅ Boshlang'ich balans saqlandi: {fmt_money(amount)}\n"
        f"💼 Hozirgi balansingiz: {fmt_money(amount)}",
        reply_markup=menu_keyboard(),
    )


def daily_limit_warning(user_id: int) -> str:
    profile = get_user_profile(user_id)
    limit_val = profile.get("spend_limit_daily")
    if not limit_val:
        return ""
    spent_today = get_spent_today(user_id)
    if spent_today > limit_val:
        return f"\n⚠️ Kunlik limitdan oshdingiz: {fmt_money(spent_today)} / {fmt_money(limit_val)}"
    return ""


async def dashboard_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    s = get_summary(uid)
    if not s:
        await update.message.reply_text("📭 Ma'lumot yo'q. Avval amal qo'shing.", reply_markup=menu_keyboard())
        return

    loan_rows = get_loans_by_person(uid)
    loan_lines = []
    for person, bergan, olgan in loan_rows:
        saldo = int(bergan or 0) - int(olgan or 0)
        loan_lines.append(f"- {person}: berdim {fmt_money(int(bergan or 0))}, oldim {fmt_money(int(olgan or 0))}, saldo {fmt_money(saldo)}")
    if not loan_lines:
        loan_lines = ["- Qarz ma'lumoti yo'q"]
    loan_block = "\n".join(loan_lines)

    trend_rows = get_daily_expense_series(uid, 7)
    trend_lines = [f"- {d.strftime('%d.%m')}: {fmt_money(int(v or 0))}" for d, v in trend_rows]
    trend_block = "\n".join(trend_lines)
    text = (
        "📊 DASHBOARD\n\n"
        f"💼 Joriy balans: {fmt_money(s['current_balance'])}\n"
        f"💰 Jami kirim: {fmt_money(s['kirim'])}\n"
        f"💸 Jami chiqim: {fmt_money(s['chiqim'])}\n"
        f"🤝 Jami qarz berdim: {fmt_money(s['qarz_berdim'])}\n"
        f"🤲 Jami qarz oldim: {fmt_money(s['qarz_oldim'])}\n"
        f"📌 Operatsion natija (kirim-chiqim): {fmt_money(s['sof_operatsion'])}\n"
        f"📌 Qarz saldosi (bergan-oldim): {fmt_money(s['qarz_saldo'])}\n\n"
        "👥 Qarzlar odamlar kesimida:\n"
        f"{loan_block}\n\n"
        "📉 Oxirgi 7 kun chiqim:\n"
        f"{trend_block}"
    )
    await update.message.reply_text(text, reply_markup=menu_keyboard())


async def report_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    limit = 50
    if context.args and context.args[0].isdigit():
        limit = max(1, min(200, int(context.args[0])))

    rows = get_report(uid, limit=limit)
    if not rows:
        await update.message.reply_text("📭 Hali amallar yo'q.", reply_markup=menu_keyboard())
        return

    text = render_tx_list(rows, f"📜 Oxirgi {min(limit, len(rows))} ta amal", max_items=limit)
    await update.message.reply_text(text, reply_markup=menu_keyboard())


async def monthly_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id

    now = datetime.now(UZ_TZ)
    year, month = now.year, now.month
    if context.args:
        m = re.match(r"^(\d{4})-(\d{2})$", context.args[0])
        if not m:
            await update.message.reply_text("❌ Format: /oylik YYYY-MM", reply_markup=menu_keyboard())
            return
        year, month = int(m.group(1)), int(m.group(2))

    rows = get_month_report(uid, year, month)
    if not rows:
        await update.message.reply_text("📭 Bu oyda amal topilmadi.", reply_markup=menu_keyboard())
        return

    text = render_tx_list(rows, f"📅 {year}-{month:02d} oylik hisobot", max_items=50)
    await update.message.reply_text(text, reply_markup=menu_keyboard())


async def range_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    if len(context.args) != 2:
        await update.message.reply_text("❌ Format: /davr YYYY-MM-DD YYYY-MM-DD", reply_markup=menu_keyboard())
        return
    start_date, end_date = context.args[0], context.args[1]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start_date) or not re.match(r"^\d{4}-\d{2}-\d{2}$", end_date):
        await update.message.reply_text("❌ Sana formati noto'g'ri.", reply_markup=menu_keyboard())
        return

    rows = get_report_by_range(uid, start_date, end_date)
    if not rows:
        await update.message.reply_text("📭 Bu davrda amal topilmadi.", reply_markup=menu_keyboard())
        return
    text = render_tx_list(rows, f"🧾 {start_date} dan {end_date} gacha", max_items=50)
    await update.message.reply_text(text, reply_markup=menu_keyboard())


async def limit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    if not context.args:
        profile = get_user_profile(uid)
        lim = profile.get("spend_limit_daily")
        lim_text = fmt_money(lim) if lim else "o'rnatilmagan"
        await update.message.reply_text(
            f"🎯 Kunlik limit: {lim_text}\n/setlimit 300000\n/setlimit 0  (o'chirish)",
            reply_markup=menu_keyboard(),
        )
        return
    if not context.args[0].isdigit():
        await update.message.reply_text("❌ Format: /setlimit 300000", reply_markup=menu_keyboard())
        return
    val = int(context.args[0])
    ok = set_spend_limit_daily(uid, None if val == 0 else val)
    if not ok:
        await update.message.reply_text("⚠️ Limit saqlanmadi.", reply_markup=menu_keyboard())
        return
    await update.message.reply_text("✅ Kunlik limit yangilandi.", reply_markup=menu_keyboard())


async def reminder_time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    if not context.args:
        p = get_user_profile(uid)
        await update.message.reply_text(
            f"🔔 Hozirgi eslatma vaqti: {p['reminder_time']}\nFormat: /setreminder 21:30",
            reply_markup=menu_keyboard(),
        )
        return
    hhmm = context.args[0].strip()
    if not parse_hhmm(hhmm):
        await update.message.reply_text("❌ Noto'g'ri vaqt. Format HH:MM", reply_markup=menu_keyboard())
        return
    ok = set_reminder_time(uid, hhmm)
    if not ok:
        await update.message.reply_text("⚠️ Eslatma vaqti saqlanmadi.", reply_markup=menu_keyboard())
        return
    await update.message.reply_text(f"✅ Eslatma vaqti saqlandi: {hhmm}", reply_markup=menu_keyboard())


async def remind_on_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    set_remind_daily(uid, True)
    await update.message.reply_text("✅ Daily eslatma yoqildi.", reply_markup=menu_keyboard())


async def remind_off_cmd(update: Update, _: ContextTypes.DEFAULT_TYPE):
    save_user(update)
    uid = update.message.from_user.id
    set_remind_daily(uid, False)
    await update.message.reply_text("✅ Daily eslatma o'chirildi.", reply_markup=menu_keyboard())


async def reminders_tick(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(UZ_TZ)
    today = now.date()
    now_hhmm = now.strftime("%H:%M")

    for user_id, reminder_time, remind_daily, spend_limit_daily, current_balance in list_users_for_daily_reminder():
        if not remind_daily:
            continue
        if (reminder_time or "21:00") != now_hhmm:
            continue
        if is_reminder_sent_today(user_id, today):
            continue

        spent_today = get_spent_today(user_id)
        warn = ""
        if spend_limit_daily and spent_today > int(spend_limit_daily):
            warn = (
                f"\n⚠️ Siz limitdan oshdingiz: {fmt_money(spent_today)} / {fmt_money(int(spend_limit_daily))}"
            )
        text = (
            "⏰ Eslatma\n"
            f"Bugungi chiqimingiz: {fmt_money(spent_today)}\n"
            f"Joriy balansingiz: {fmt_money(int(current_balance or 0))}"
            f"{warn}"
        )
        try:
            await context.bot.send_message(chat_id=user_id, text=text)
            mark_reminder_sent_today(user_id, today)
        except Exception as e:
            log.warning("Eslatma yuborilmadi (%s): %s", user_id, e)


async def handle_transaction_entry(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    uid = update.message.from_user.id
    text = update.message.text.strip()

    if action in {"kirim", "chiqim"}:
        amount, category, note = parse_amount_category_note(text)
        if amount is None:
            await update.message.reply_text(
                "❌ Format: `miqdor kategoriya izoh`\nMisol: `120000 ovqat tushlik`",
                parse_mode="Markdown",
                reply_markup=cancel_keyboard(),
            )
            return
        ok, new_balance, msg = add_transaction(uid, action, amount, category, note, None)
        source_text = f"🏷 Kategoriya: {category}\n📝 Izoh: {note}"
    else:
        amount, person, note = parse_amount_person_note(text)
        if amount is None:
            await update.message.reply_text(
                "❌ Format: `miqdor ism izoh`\nMisol: `500000 Sardor qaytaradi`",
                parse_mode="Markdown",
                reply_markup=cancel_keyboard(),
            )
            return
        ok, new_balance, msg = add_transaction(uid, action, amount, "qarz", note, person)
        source_text = f"👤 Kim bilan: {person}\n📝 Izoh: {note}"

    if not ok:
        await update.message.reply_text(f"⚠️ Amal saqlanmadi: {msg}", reply_markup=menu_keyboard())
        context.user_data.pop("pending_action", None)
        return

    label = {
        "kirim": "✅ Kirim qo'shildi",
        "chiqim": "✅ Chiqim qo'shildi",
        "qarz_berdim": "✅ Qarz berdingiz",
        "qarz_oldim": "✅ Qarz oldingiz",
    }[action]
    warn = daily_limit_warning(uid) if action == "chiqim" else ""
    flow_text = {
        "kirim": "Pul qo'shildi va balans oshdi.",
        "chiqim": "Pul ishlatildi va balans kamaydi.",
        "qarz_berdim": "Qarz berdingiz, balansdan ayrildi.",
        "qarz_oldim": "Qarz oldingiz, balansga qo'shildi.",
    }[action]
    await update.message.reply_text(
        f"{label}\n{source_text}\n{flow_text}\n💼 Endi qolgan pulingiz: {fmt_money(new_balance)}{warn}",
        reply_markup=menu_keyboard(),
    )
    context.user_data.pop("pending_action", None)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    save_user(update)
    text = update.message.text.strip()
    uid = update.message.from_user.id

    if text == "⬅️ Bekor qilish":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("awaiting_setup", None)
        await update.message.reply_text("Bekor qilindi.", reply_markup=menu_keyboard())
        return

    # Step-based quick setup from buttons
    if context.user_data.get("awaiting_setup") == "setbalans":
        raw = text.replace(" ", "").replace("_", "")
        if not raw.isdigit():
            await update.message.reply_text("❌ Faqat raqam kiriting. Masalan: 5000000", reply_markup=cancel_keyboard())
            return
        amount = int(raw)
        if amount < 0:
            await update.message.reply_text("❌ Balans manfiy bo'lmaydi.", reply_markup=cancel_keyboard())
            return
        ok = set_opening_balance(uid, amount)
        context.user_data.pop("awaiting_setup", None)
        if not ok:
            await update.message.reply_text("⚠️ Balans saqlanmadi.", reply_markup=menu_keyboard())
            return
        await update.message.reply_text(
            f"✅ Boshlang'ich pulingiz saqlandi: {fmt_money(amount)}\n💼 Hozirgi balans: {fmt_money(amount)}",
            reply_markup=menu_keyboard(),
        )
        return

    if context.user_data.get("awaiting_setup") == "setlimit":
        raw = text.replace(" ", "").replace("_", "")
        if not raw.isdigit():
            await update.message.reply_text("❌ Faqat raqam kiriting. Masalan: 300000", reply_markup=cancel_keyboard())
            return
        amount = int(raw)
        ok = set_spend_limit_daily(uid, None if amount == 0 else amount)
        context.user_data.pop("awaiting_setup", None)
        if not ok:
            await update.message.reply_text("⚠️ Limit saqlanmadi.", reply_markup=menu_keyboard())
            return
        await update.message.reply_text("✅ Kunlik limit saqlandi.", reply_markup=menu_keyboard())
        return

    if context.user_data.get("awaiting_setup") == "setreminder":
        hhmm = text.strip()
        if not parse_hhmm(hhmm):
            await update.message.reply_text("❌ Format HH:MM bo'lsin. Masalan: 21:30", reply_markup=cancel_keyboard())
            return
        ok = set_reminder_time(uid, hhmm)
        context.user_data.pop("awaiting_setup", None)
        if not ok:
            await update.message.reply_text("⚠️ Eslatma vaqti saqlanmadi.", reply_markup=menu_keyboard())
            return
        await update.message.reply_text(f"✅ Eslatma vaqti saqlandi: {hhmm}", reply_markup=menu_keyboard())
        return

    if text in ACTION_BUTTONS:
        action = ACTION_BUTTONS[text]
        context.user_data["pending_action"] = action
        if action in {"kirim", "chiqim"}:
            prompt = (
                f"{text} tanlandi.\n"
                "Yozing: `miqdor kategoriya izoh`\n"
                "Misol: `120000 ovqat tushlik`"
            )
        else:
            prompt = (
                f"{text} tanlandi.\n"
                "Yozing: `miqdor ism izoh`\n"
                "Misol: `500000 Sardor qaytaradi`"
            )
        await update.message.reply_text(prompt, parse_mode="Markdown", reply_markup=cancel_keyboard())
        return

    if text == "📊 Dashboard":
        await dashboard_cmd(update, context)
        return
    if text == "📜 Report" or text == "📜 Report (50)":
        await report_cmd(update, context)
        return
    if text == "📅 Oylik":
        await monthly_cmd(update, context)
        return
    if text == "🧾 Davr bo'yicha":
        await update.message.reply_text("Format: /davr 2026-04-01 2026-04-30", reply_markup=menu_keyboard())
        return
    if text == "💰 Balans":
        await update.message.reply_text(
            f"{balance_line(uid)}\nBalans o'rnatish: /setbalans 5000000", reply_markup=menu_keyboard()
        )
        return
    if text == "💵 Boshlang'ich balans":
        context.user_data["awaiting_setup"] = "setbalans"
        await update.message.reply_text("Sizda hozir qancha pul bor? Faqat raqam kiriting.\nMasalan: 5000000", reply_markup=cancel_keyboard())
        return
    if text == "🎯 Kunlik limit":
        context.user_data["awaiting_setup"] = "setlimit"
        await update.message.reply_text("Kunlik limitni kiriting (0 bo'lsa o'chadi).\nMasalan: 300000", reply_markup=cancel_keyboard())
        return
    if text == "⏰ Eslatma vaqti":
        context.user_data["awaiting_setup"] = "setreminder"
        await update.message.reply_text("Qaysi vaqtda eslatsin? HH:MM formatda yozing.\nMasalan: 21:30", reply_markup=cancel_keyboard())
        return
    if text == "🔔 Eslatma ON/OFF":
        p = get_user_profile(uid)
        now_state = "yoqilgan" if p["remind_daily"] else "o'chirilgan"
        await update.message.reply_text(
            f"Hozir eslatma: {now_state}\nYoqish: /remindon\nO'chirish: /remindoff",
            reply_markup=menu_keyboard(),
        )
        return
    if text == "🔔 Eslatma":
        p = get_user_profile(uid)
        remind_state = "yoqilgan" if p["remind_daily"] else "o'chirilgan"
        daily_limit_text = fmt_money(p["spend_limit_daily"]) if p["spend_limit_daily"] else "o'rnatilmagan"
        await update.message.reply_text(
            f"🔔 Eslatma: {remind_state}\n"
            f"Vaqt: {p['reminder_time']}\n"
            f"Kunlik limit: {daily_limit_text}\n\n"
            "Yoqish/o'chirish: /remindon yoki /remindoff\n"
            "Vaqt berish: /setreminder 21:30\n"
            "Limit berish: /setlimit 300000",
            reply_markup=menu_keyboard(),
        )
        return
    if text == "❓ Yordam":
        await help_cmd(update, context)
        return

    pending = context.user_data.get("pending_action")
    if pending:
        await handle_transaction_entry(update, context, pending)
        return

    await update.message.reply_text("Xabar tushunilmadi. Pastdagi menyudan foydalaning.", reply_markup=menu_keyboard())


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.error("Handler xatosi: %s", context.error)


def main():
    log.info("Bot ishga tushmoqda...")

    ok, reason = check_connection()
    if not ok:
        log.error("DB xato: %s", reason)
        return
    if not create_tables():
        log.error("Jadval yaratib bo'lmadi")
        return

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .defaults(Defaults(tzinfo=UZ_TZ))
        .post_init(configure_bot_profile)
        .build()
    )

    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))
    app.add_handler(CommandHandler("report", report_cmd))
    app.add_handler(CommandHandler("oylik", monthly_cmd))
    app.add_handler(CommandHandler("davr", range_cmd))
    app.add_handler(CommandHandler("setbalans", set_balance_cmd))
    app.add_handler(CommandHandler("setlimit", limit_cmd))
    app.add_handler(CommandHandler("setreminder", reminder_time_cmd))
    app.add_handler(CommandHandler("remindon", remind_on_cmd))
    app.add_handler(CommandHandler("remindoff", remind_off_cmd))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    if app.job_queue:
        app.job_queue.run_repeating(reminders_tick, interval=60, first=15, name="per_user_reminders")

    if USE_WEBHOOK:
        if WEBHOOK_URL and WEBHOOK_SECRET and WEBHOOK_URL.startswith("https://"):
            clean_base = WEBHOOK_URL.rstrip("/")
            clean_path = WEBHOOK_PATH if WEBHOOK_PATH.startswith("/") else f"/{WEBHOOK_PATH}"
            log.info("Webhook rejimi yoqildi: %s%s", clean_base, clean_path)
            app.run_webhook(
                listen="0.0.0.0",
                port=PORT,
                url_path=clean_path.lstrip("/"),
                webhook_url=f"{clean_base}{clean_path}",
                secret_token=WEBHOOK_SECRET,
                allowed_updates=Update.ALL_TYPES,
            )
            return
        log.warning("USE_WEBHOOK=true lekin WEBHOOK sozlamasi to'liq emas, polling fallback ishlaydi.")

    log.info("Polling rejimi ishga tushdi")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
