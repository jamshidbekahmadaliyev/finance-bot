# 🚀 Shaxsiy Moliya Boti — O'rnatish Yo'riqnomasi

## Muhim: maxfiy ma'lumotlar
- Endi `config.py` ichiga token yoki DB parol yozilmaydi.
- Barcha maxfiy qiymatlar `.env` faylida saqlanadi.
- `.env` git ga kirmaydi (`.gitignore` da bor).

### `.env` tayyorlash
1. `.env.example` nusxasini oling va `.env` nomi bilan saqlang.
2. Ichiga o'zingizning real qiymatlarni kiriting:

```env
BOT_TOKEN=...
DB_HOST=...
DB_PORT=5432
DB_NAME=postgres
DB_USER=...
DB_PASSWORD=...
```

## 📁 Fayl tuzilmasi
```
finance_bot/
├── config.py           ← .env dan sozlamalarni o'qiydi
├── .env.example        ← .env uchun namuna
├── db.py               ← Database funksiyalari
├── main.py             ← Bot asosiy kodi
├── requirements.txt    ← Kerakli kutubxonalar
└── finance_bot.service ← VPS uchun systemd fayli
```

---

## 1️⃣ Supabase DB sozlash

1. https://supabase.com ga kiring → "New project" yarating
2. Loyiha yaratilgach: **Settings → Database** bo'limiga o'ting
3. **Connection parameters** bo'limidan quyidagilarni oling:
   - Host (masalan: `db.abcdefgh.supabase.co`)
   - Password (loyiha yaratishda berganiingiz)
4. `config.py` faylini oching va qiymatlarni to'ldiring

---

## 2️⃣ Telegram Bot Token olish

1. Telegramda **@BotFather** ga yozing
2. `/newbot` buyrug'ini bering
3. Bot nomi va username bering
4. Berilgan TOKEN ni `config.py` ga qo'ying

---

## 3️⃣ VPS ga joylash (Ubuntu)

### VPS sotib olish
- Hetzner (hetzner.com) — oyiga ~$4 — tavsiya etiladi
- DigitalOcean — oyiga $6
- Eng arzon: Ubuntu 22.04, 1 CPU, 1GB RAM yetarli

### VPS ga ulanish
```bash
ssh ubuntu@SERVER_IP_MANZILI
```

### O'rnatish
```bash
# Yangilash
sudo apt update && sudo apt upgrade -y

# Python va pip
sudo apt install python3 python3-pip -y

# Bot fayllarini yuklash
mkdir ~/finance_bot
cd ~/finance_bot
# (fayllarni SCP yoki SFTP orqali yuklang)

# Kutubxonalarni o'rnatish
pip3 install -r requirements.txt
```

### Sinov uchun ishga tushirish
```bash
cd ~/finance_bot
python3 main.py
# Bot ishlayotganini tekshiring, keyin Ctrl+C bilan to'xtating
```

### 24/7 ishlash uchun systemd sozlash
```bash
# Service faylini ko'chiring
sudo cp finance_bot.service /etc/systemd/system/

# finance_bot.service ichidagi yo'llarni o'zingiznikiga moslashtiring!
# WorkingDirectory va ExecStart

# Yoqish
sudo systemctl daemon-reload
sudo systemctl enable finance_bot   # server qayta yonganda ham ishlasin
sudo systemctl start finance_bot    # hozir ishga tushir

# Holat tekshirish
sudo systemctl status finance_bot
```

---

## 4️⃣ Foydali buyruqlar

```bash
# Bot loglarini ko'rish (jonli)
sudo journalctl -u finance_bot -f

# Botni to'xtatish
sudo systemctl stop finance_bot

# Botni qayta ishga tushirish (kod o'zgartirilganda)
sudo systemctl restart finance_bot

# Bot xato qilib to'xtab qolsa — avtomatik qayta ishga tushadi (Restart=always)
```

---

## 5️⃣ Bot buyruqlari

| Buyruq | Vazifa |
|--------|--------|
| `/start` | Botni boshlash |
| `/help` | Yordam |
| `/analiz` | Umumiy balans va statistika |
| `/report` | Oxirgi 10 ta yozuv |
| `/oylik` | Oxirgi 30 kunlik hisobot |
| `/bugun` | Bugungi chiqim |
| `/oyqoldiq` | Shu oydagi qoldiq |
| `/setbudget` | Limit o'rnatish |
| `/budgets` | Limitlarni ko'rish |
| `/reminders` | Eslatma sozlash |

### Yozish formati:
```
+150000 oylik maosh       ← Kirim
-45000 supermarket        ← Chiqim
qarz_berdim 300000 Aliga  ← Qarz berdim
qarz_oldim 100000 ukamdan ← Qarz oldim
```

Yangi tugmali format (tavsiya):
```
150000 ovqat tushlik
90000 transport taksi
```

Budjet limiti misoli:
```bash
/setbudget daily 200000
/setbudget weekly 1200000
/setbudget monthly 4000000
```

Eslatma sozlash:
```bash
/reminders on daily
/reminders off weekly
```

---

## 6️⃣ Tekin serverga qo'yish (Render)

Bu usulda bot 24/7 ga yaqin ishlaydi va webhook rejimida yuradi.

1. Kodni GitHub repoga joylang.
2. https://render.com ga kiring va akkaunt oching.
3. **New +** → **Web Service** → GitHub repo ni ulang.
4. Render sozlamalari:
   - Runtime: Python
   - Build command: `pip install -r requirements.txt`
   - Start command: `python main.py`
   - Plan: Free
5. Environment Variables bo'limida quyidagilarni kiriting:
   - `BOT_TOKEN`
   - `DB_HOST`
   - `DB_PORT`
   - `DB_NAME`
   - `DB_USER`
   - `DB_PASSWORD`
   - `USE_WEBHOOK=true`
   - `WEBHOOK_PATH=/telegram`
   - `WEBHOOK_SECRET=<ixtiyoriy-maxfiy-token>`
6. Deploy qiling.
7. Deploy bo'lgach servis URL chiqadi, masalan:
   - `https://your-service-name.onrender.com`
8. Shu URL ni `WEBHOOK_URL` sifatida Render env ga qo'shing va qayta deploy qiling.

Misol:
- `WEBHOOK_URL=https://your-service-name.onrender.com`
- Bot webhook endpoint: `https://your-service-name.onrender.com/telegram`

Eslatma:
- Agar `USE_WEBHOOK=true` bo'lsa, `WEBHOOK_URL` bo'sh bo'lmasligi shart.
- `WEBHOOK_URL` faqat `https://` bilan bo'lishi kerak.
- `WEBHOOK_SECRET` bo'sh qoldirmang (uzun, tasodifiy secret bering).
- Localda ishlatishda `USE_WEBHOOK=false` qoldiring, bot polling rejimida ishlaydi.

---

## 7️⃣ Xavfsizlik checklist

- `.env` hech qachon GitHub ga yuklanmasin.
- Bot token va DB parolni muntazam yangilang (rotate).
- Supabase da kuchli parol va kerak bo'lsa IP/network cheklovlardan foydalaning.
- `bot.log` ni public joyga chiqarmang.
- Render'da barcha maxfiy qiymatlarni faqat Environment Variables ga kiriting.
