# cooperation-watcher-bot

cooperation.uz va new.cooperation.uz saytlarini kuzatib, mos mahsulotlar topilganda Telegram orqali xabar beruvchi bot.

## O'rnatish (Ubuntu VPS)

### 1. Telegram bot yaratish
1. Telegramda `@BotFather` ni oching
2. `/newbot` yozing → nom va username bering
3. Token olasiz: `123456:ABCdef...`

### 2. Telegram User ID olish
1. `@userinfobot` ga `/start` yuboring
2. Sizning numeric ID ingiz ko'rinadi (masalan: `123456789`)

### 3. Serverga yuklash
```bash
git clone <repo-url> cooperation-watcher-bot
cd cooperation-watcher-bot
```

### 4. O'rnatish
```bash
chmod +x scripts/install.sh
./scripts/install.sh
```

### 5. .env to'ldirish
```bash
nano .env
```
```
TELEGRAM_BOT_TOKEN=123456:ABCdef...
TELEGRAM_ADMIN_USER_ID=123456789
DATABASE_URL=sqlite:///data/cooperation.db
CHECK_INTERVAL_MINUTES=10
LOG_LEVEL=INFO
COOPERATION_BASE_URL=https://cooperation.uz
NEW_COOPERATION_BASE_URL=https://new.cooperation.uz
TIMEZONE=Asia/Tashkent
```

### 6. Qo'lda ishga tushirish (test)
```bash
source .venv/bin/activate
python -m app.main
```

### 7. Systemd service o'rnatish
```bash
# Service faylini ko'chirish
sudo cp systemd/cooperation-watcher.service /etc/systemd/system/

# Faylda user va path ni tekshiring:
sudo nano /etc/systemd/system/cooperation-watcher.service
# User=ubuntu → sizning username ingiz
# WorkingDirectory=/home/ubuntu/cooperation-watcher-bot → to'g'ri path

# Aktivlashtirish
sudo systemctl daemon-reload
sudo systemctl enable cooperation-watcher
sudo systemctl start cooperation-watcher
```

### 8. Boshqarish
```bash
sudo systemctl start cooperation-watcher    # ishga tushirish
sudo systemctl stop cooperation-watcher     # to'xtatish
sudo systemctl restart cooperation-watcher  # qayta ishga tushirish
sudo systemctl status cooperation-watcher   # holat
sudo journalctl -u cooperation-watcher -f   # live log
```

### 9. Yangilash
```bash
./scripts/update.sh
```

## Telegram buyruqlari

| Buyruq | Vazifa |
|--------|--------|
| /start | Bosh menyu |
| /add | Kuzatuv qo'shish |
| /list | Kuzatuvlar ro'yxati |
| /cheap [so'z] | Eng arzon savdolar |
| /latest | Yangi savdolar |
| /search | Qidirish |
| /status | Bot holati |
| /help | Yordam |

## Data manbalar

### cooperation.uz
- **Tur:** Server-side HTML (scraping)
- **Qidiruv:** `https://cooperation.uz/products/search?query={keyword}&catalog=`
- **Mahsulot:** `https://cooperation.uz/products/product/{id}`
- **Eslatma:** Sayt yangi versiyaga ko'chmoqda

### new.cooperation.uz
- **Tur:** HTML scraping
- **Asosiy sahifa:** `https://new.cooperation.uz/plan-schedule`
- **Kuzatiladigan:** xarid rejalari, katalog, lotlar

## Muammolarni hal qilish

**Bot ishlamayapti:**
```bash
sudo journalctl -u cooperation-watcher -n 50
```

**Token xato:**
`.env` faylidagi `TELEGRAM_BOT_TOKEN` ni tekshiring.

**Saytga ulanish muammosi:**
VPS dan saytga ping: `curl -I https://cooperation.uz`

**Testlar:**
```bash
source .venv/bin/activate
pytest
```

**Manba debug:**
```bash
python -m app.sources.debug
python -m app.sources.debug cooperation
python -m app.sources.debug new
```
