# 🚀 Shaxsiy Moliya Boti — O'rnatish Yo'riqnomasi

## 📁 Fayl tuzilmasi
```
finance_bot/
├── config.py           ← Token va DB sozlamalari
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

### Yozish formati:
```
+150000 oylik maosh       ← Kirim
-45000 supermarket        ← Chiqim
qarz_berdim 300000 Aliga  ← Qarz berdim
qarz_oldim 100000 ukamdan ← Qarz oldim
```
