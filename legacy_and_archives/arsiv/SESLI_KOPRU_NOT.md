# 📦 Arşiv: Sesli Komut Köprüsü v3.0

**Arşivleme tarihi:** 21 Mart 2026  
**Dosya:** `sesli_kopru_v3.py`  
**Orijinal konum:** `.gemini/antigravity/scratch/sesli_kopru.py`

---

## Neden Arşivlendi?

Sistem iletişim köprüsü olarak kurulmuştu ama Telegram çözümü daha stabil çalıştı. Sistem çalışıyor — silinmedi, gelecekteki entegrasyonlar için burada duruyor.

## Ne Yapıyor?

- Port 8888'de FastAPI sunucusu
- Telefondan sesli komut → OpenAI GPT-4o-mini → TTS yanıt
- `/ajan` endpoint: function calling ile araçlar (dosya_oku, dosya_yaz, komut_calistir...)
- `/gonder` endpoint: GPT-4o Vision + screenshot ile Antigravity yanıtı okuma

## İleride Kullanım

- Ekran okuma (screenshot → GPT-4o vision) başka otomasyonlarda işe yarar
- `/ajan` endpoint'i başka projelere kolayca entegre edilebilir
- `baslat.bat` ile port 8888'de başlatılır, Cloudflare tunnel açılır
