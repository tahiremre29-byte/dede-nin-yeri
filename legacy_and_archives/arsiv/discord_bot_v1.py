"""
tools/discord_bot/bot.py
DD1 Discord Botu — DD1 /chat/ endpoint'ine köprü.

Komutlar:
  !reset    → konuşmayı sıfırla
  !durum    → toplanan bilgileri göster
  Normal mesaj → DD1 Ses Ustasına gider
"""
from __future__ import annotations
import logging
from collections import defaultdict

import discord
import httpx

from config import DD1_CHAT_URL, BOT_NAME, MAX_HISTORY, TIMEOUT_S, PREFIX

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dd1.discord")

# Kanal bazlı geçmiş + CI state
_history: dict[int, list[dict]] = defaultdict(list)
_ci: dict[int, dict]            = defaultdict(dict)


class DD1Bot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"[DD1] ⚡ {self.user} açıldı — {BOT_NAME} hazır.")

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        cid  = message.channel.id
        text = message.content.strip()

        # ── Komutlar ─────────────────────────────────────────────────
        if text.startswith(PREFIX + "reset"):
            _history[cid].clear()
            _ci[cid].clear()
            await message.channel.send("🔄 Konuşma sıfırlandı. Baştan anlat.")
            return

        if text.startswith(PREFIX + "durum"):
            ci = _ci[cid]
            if not ci:
                await message.channel.send("Henüz bilgi toplanmadı.")
                return
            mapping = {
                "vehicle_type":   "Araç",
                "goal":           "Hedef",
                "trunk_width_cm": "Bagaj En",
                "trunk_height_cm":"Bagaj Boy",
                "trunk_depth_cm": "Bagaj Derinlik",
                "driver_info":    "Sürücü",
            }
            lines = ["📋 **Toplanan Bilgiler:**"]
            for k, lbl in mapping.items():
                if ci.get(k):
                    lines.append(f"  • {lbl}: `{ci[k]}`")
            await message.channel.send("\n".join(lines))
            return

        if text.startswith(PREFIX):
            return  # Bilinmeyen komut, atla

        # ── DD1 Chat ─────────────────────────────────────────────────
        async with message.channel.typing():
            reply = await self._dd1_chat(cid, text)
        await message.channel.send(reply)

    async def _dd1_chat(self, cid: int, text: str) -> str:
        history = _history[cid]
        ci      = _ci[cid]
        payload = {
            "message": text,
            "context": {
                "vehicle":         ci.get("vehicle_type"),
                "driver_info":     ci.get("driver_info"),
                "goal":            ci.get("goal"),
                "trunk_width_cm":  ci.get("trunk_width_cm"),
                "trunk_height_cm": ci.get("trunk_height_cm"),
                "trunk_depth_cm":  ci.get("trunk_depth_cm"),
            },
            "history": history[-(MAX_HISTORY * 2):-1] if len(history) > 1 else [],
        }
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:
                res = await client.post(DD1_CHAT_URL, json=payload)
                res.raise_for_status()
                data = res.json()
        except httpx.TimeoutException:
            return "⏳ Sunucu cevap vermedi, biraz bekle."
        except httpx.ConnectError:
            return "🔌 DD1 sunucusuna bağlanamıyorum. Sunucunun çalıştığından emin ol."
        except Exception as e:
            logger.error("DD1 hata: %s", e)
            return f"⚠️ Hata: {e}"

        # CI güncelle
        panel = data.get("normalized_panel") or {}
        for k in ("vehicle_type", "goal", "trunk_width_cm", "trunk_height_cm", "trunk_depth_cm"):
            if panel.get(k):
                _ci[cid][k] = panel[k]

        reply = data.get("user_visible_response") or data.get("reply") or "..."

        # Geçmiş
        _history[cid].append({"role": "user",      "content": text})
        _history[cid].append({"role": "assistant",  "content": reply})
        if len(_history[cid]) > MAX_HISTORY * 2:
            _history[cid] = _history[cid][-(MAX_HISTORY * 2):]

        return reply
