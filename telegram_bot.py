"""
DD1 Telegram Botu - Groq Direkt Baglanti
==========================================
DD1 sunucusuna gerek yok. Groq Llama 3.3 70B ile direkt konusur.

Komutlar:
    /start  - Karsilama
    /reset  - Konusmayı sifirla
    /bilgi  - Bot hakkinda

Calistir:
    python telegram_bot.py
"""
import os
import sys
import logging
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# .env yukle
ENV_PATH = Path(__file__).parent / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("dd1.telegram")

# ── Config ────────────────────────────────────────────────────────────────────

TELEGRAM_TOKEN = os.environ.get("DDSOUND_BOT_TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY   = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL     = "llama-3.3-70b-versatile"
MAX_HISTORY    = 20

if not TELEGRAM_TOKEN:
    logger.error("DDSOUND_BOT_TOKEN bulunamadi! .env dosyasini kontrol edin.")
    sys.exit(1)

if not GROQ_API_KEY:
    logger.error("GROQ_API_KEY bulunamadi! .env dosyasini kontrol edin.")
    sys.exit(1)

logger.info("Bot baslatiliyor — model: %s", GROQ_MODEL)

# ── Sistem Promptu ────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sen DDSOUND'un kisisel araba ses sistemi ustasisin. Adin: DDSOUND Usta.
10+ yillik deneyimli bir teknisyen gibi konusursun — Turkce, kisa, net, dogru.

== TEMEL KURAL ==
YALNIZCA DOGRU BILGI VER. Bilmiyorsan "bilmiyorum, hesaplamam lazim" de.
Tahmin yapma, uydurama. Yanlis bilgi vermek musteri kayiptirir.

== KABIN TIPLERI VE OZELLIKLERI ==
KAPALI (Sealed):
- En sade yapı, tum ses iceri hapsolur
- Siki, sert bas — SQL/SQ icin ideal
- Hacim kuralı: woofer Vas degerinin 0.3-1.0x arasi
- Kucuk hacim = sert bas, buyuk hacim = derin bas

PORTLU (Ported / Bass-Reflex):
- Port (boru/slot) ek SPL saglar
- Tuning frekansı (Fb) = port ile ayarlanır
- Helmholtz formulu: Fb = (c/2π) × √(Av / (Vb × Lv))
- c=343m/s, Av=port alani(m2), Vb=hacim(m3), Lv=port boyu(m)
- Genel kural: Fb = Fs × 0.7-1.2 arasi
- Port hizi max 20m/s olmali (tıslama onlemek icin)

4. DERECE BANDPASS:
- ic oda: kapali (woofer burada)
- dis oda: portlu (ses sadece porttan cikar)
- Oran: ic/toplam = 0.4-0.55
- Yuksek SPL, dar bant — yarışma icin ideal

6. DERECE BANDPASS:
- Her iki oda da portlu
- En genis bant, en yuksek SPL
- Profi sistemler icin

== DOGRU WIRING KURALLARI ==
Seri baglanti: R_toplam = R1 + R2 (ohm artar)
Paralel baglanti: 1/R = 1/R1 + 1/R2 (ohm duşer)
Amfi min impedansi: genellikle 2 ohm (bazi amfiler 1 ohm)
Ornek: 2x 4-ohm woofer paralel = 2 ohm ✓
Ornek: 2x 4-ohm woofer seri = 8 ohm (amfi verim duşer ✗)
DVC (cift sargili) woofer: seri=iki katı ohm, paralel=yarisi ohm

== GUC HESABI ==
RMS guc onemlidir, peak guc aldatmaca olablir.
Amfi RMS >= woofer RMS (max %150 ustu ozaman sigortaya bak)
Gain ayari: klibin altında kalmak sart (distorsyon ses sistemini oldurup biter)

== TURKIYE PIYASASI ==
Guvenilir markalar (Turkiye'de bulunabilir):
- Subwoofer: JL Audio, Rockford Fosgate, Sundown, DD Audio, American Bass, Memphis
- Amfi: Rockford, JL Audio, Soundigital (Brezilya), Hertz, Mosconi
- Kablo/aksesuar: Stinger, KnuKonceptz, Metra
Satici: Hifilife, Zuhal Muzik, yerel oto aksesuar magazalari

== KURULUM KURALLARI ==
Aki guclendurmesi: 100W RMS basi 1000W RMS icin Lithium/Agm gerekli
Kablo kesiti: her 1000W icin min 4AWG (21mm2)
Topraklama: en kisa mesafe, guvde metal noktasi (boya yok)
Sigorta: aki kutbundan max 50cm uzakliga koy

== TURKIYE SES CEZALARI ==
- Trafik Kanunu 2918: 993 TL (ses sistemi genel)
- Modifiye ses/ekran sistemi sonradan takilmis: 21.000 TL
- Cevre Kanunu gurultu: 11.000 TL

== ILETISIM TARZI ==
- Kisa cevap, pratik bilgi
- Saha dili: kabin, port, amfi, woofer, twit, orta range, crossover, gain, kopru, paralel, seri
- Muzahhas ol: "orta boy woofer" degil, "25cm (10 inc) woofer"
- Hesap sorduysa formul uygula, sonucu ver
- Musteri ne kullandigini bilmiyorsan sor (marka, model, ohm, RMS)
"""

# ── Groq API ──────────────────────────────────────────────────────────────────

def groq_chat(messages: list) -> str:
    """Groq Llama 3.3 70B API cagrisi."""
    try:
        from groq import Groq
        client = Groq(api_key=GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.7,
            max_tokens=1024,
        )
        return resp.choices[0].message.content or "Cevap alinamadi."
    except Exception as e:
        logger.error("Groq hatasi: %s", e)
        return f"Hata: {e}"


# ── Kullanici Gecmisi ─────────────────────────────────────────────────────────

_histories: dict[int, list] = {}

def get_messages(user_id: int, new_msg: str) -> list:
    """Sistem promptu + gecmis + yeni mesaj listesi."""
    hist = _histories.get(user_id, [])
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs.extend(hist[-MAX_HISTORY:])
    msgs.append({"role": "user", "content": new_msg})
    return msgs

def add_pair(user_id: int, user_msg: str, assistant_msg: str):
    if user_id not in _histories:
        _histories[user_id] = []
    _histories[user_id].append({"role": "user",      "content": user_msg})
    _histories[user_id].append({"role": "assistant", "content": assistant_msg})
    # Limit
    if len(_histories[user_id]) > MAX_HISTORY:
        _histories[user_id] = _histories[user_id][-MAX_HISTORY:]

def clear_history(user_id: int):
    _histories[user_id] = []


# ── Telegram Handlers ─────────────────────────────────────────────────────────

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    clear_history(user.id)
    await update.message.reply_text(
        f"Merhaba {user.first_name}!\n\n"
        "Ben DDSOUND Asistan. Araba ses sistemi, subwoofer kabin tasarimi, "
        "amplifikator ve montaj konularinda yardim ederim.\n\n"
        "Direkt yazabilirsin!\n"
        "/reset - Konusmayi sifirla\n"
        "/bilgi - Bot hakkinda"
    )


async def cmd_reset(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    clear_history(update.effective_user.id)
    await update.message.reply_text("Konusma sifirlandi. Yeni sorunla baslayabilirsin.")


async def cmd_bilgi(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "DDSOUND Asistan\n"
        f"Model: Groq {GROQ_MODEL}\n"
        "Alan: Araba ses sistemi, kabin tasarimi"
    )


async def on_voice(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Sesli mesaj gelince uyari ver."""
    await update.message.reply_text(
        "Sesli mesaj alamiyorum simdilik. Lutfen ayni soruyu yazarak gonder!"
    )


async def on_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user    = update.effective_user
    message = update.message.text.strip()

    if not message:
        return

    logger.info("[%d] %s: %s", user.id, user.username or user.first_name, message[:80])

    # "Yaziyor..." goster
    await ctx.bot.send_chat_action(update.effective_chat.id, "typing")

    # Groq'a gonder
    msgs  = get_messages(user.id, message)
    reply = await asyncio.get_event_loop().run_in_executor(
        None, groq_chat, msgs
    )

    add_pair(user.id, message, reply)
    await update.message.reply_text(reply)


# ── Ana ───────────────────────────────────────────────────────────────────────

async def on_startup(app):
    """Baslarken webhook'u sil — Conflict hatasini onler."""
    await app.bot.delete_webhook(drop_pending_updates=True)
    logger.info("Webhook silindi, polling basliyor...")


def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("bilgi", cmd_bilgi))
    app.add_handler(MessageHandler(filters.VOICE, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    logger.info("=== DD Sound Garage Bot Aktif ===")
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
