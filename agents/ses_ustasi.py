"""
agents/ses_ustasi.py
DD1 Ses Ustası — İlk Temas ve Yönlendirme Ajanı

YETKİ SINIRI:
- Akustik hesap YAPAMAZ
- DXF/STL üretimi YAPAMAZ
- IntakePacket üretir ve router'a teslim eder

AI ERİŞİMİ:
- Doğrudan google-genai kullanmaz.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Any

from schemas.intake_packet import IntakePacket, TSParams, build_intake
from core.router import quick_route, route, classify_intent
from core.router import request_missing_fields

logger = logging.getLogger("dd1.ses_ustasi")

# Prompt dosyasını bir kez yükle (token tekrarını önler)
_PROMPT_PATH = Path(__file__).parent / "prompts" / "ses_ustasi.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")


def _sanitize_reply(text: str) -> str:
    """
    GPT çıktısını kullanıcıya göndermeden önce temizler.
    - SQL/SPL/SQ/LowBass/Daily kısaltmaları sade Türkçeye çevirir
    - T/S parametresi (Fs, Qts, Vas) soru cümlelerini kaldırır
    - Birden fazla soru varsa sadece ilkini tutar
    - Formal kalipları temizler
    """
    import re
    if not text:
        return text

    # 1. SQL / SPL / SQ / LowBass / Daily terim dönüşümleri
    replacements = [
        (r'\bSQL\b', 'dengeli ses'),
        (r'\bSPL\b', 'yüksek hacim'),
        (r'\bSQ\b',  'ses kalitesi'),
        (r'\bLowBass\b', 'derin bas'),
        (r'\bDaily\b', 'günlûk'),
        (r'\(SQL/SPL/LowBass/Daily\)', ''),
        (r'\(SQL/SPL/[\w/]+\)', ''),
        (r'SQL/SPL/LowBass/Daily', 'günlûk tok bas ya da yüksek hacim'),
        (r'SQL/SPL', 'dengeli ya da yüksek hacimli'),
    ]
    for pat, rep in replacements:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    # 2. T/S parametresi içeren cümleleri çıkar
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    filtered = [
        s for s in sentences
        if not re.search(
            r'[Tt]/[Ss]\s*param|[Ff]s[,\s]|[Qq]ts[,\s]|[Vv]as[,\s]|t/s de\u011fer|t/s bilgi|t/s parametrel',
            s, re.IGNORECASE
        )
    ]
    text = ' '.join(filtered) if filtered else text

    # 3. Birden fazla soru işareti varsa sadece ilk soruya kadar kes
    question_marks = [i for i, c in enumerate(text) if c == '?']
    if len(question_marks) > 1:
        text = text[:question_marks[0] + 1].strip()

    # 4. Formal kalipları temizle
    formal_patterns = [
        (r"belirtir misiniz\?", "?"),
        (r"payla\u015f\u0131r m\u0131s\u0131n\u0131z\?", "?"),
        (r"\u00f6\u011frenebilir miyim\?", "?"),
        (r"sa\u011flayabilir misiniz\?", "?"),
        (r"bana s\u00f6yleyebilir misiniz\?", "?"),
        (r"\bAyr\u0131ca\b,?\.?\s*", ""),
        (r"\bE\u011fer yoksa sorun de\u011fil\b,?\.?\s*", ""),
    ]
    for pat, rep in formal_patterns:
        text = re.sub(pat, rep, text, flags=re.IGNORECASE)

    return text.strip()


class SesUstasi:
    """
    DD1 İlk Temas Ajanı.
    Kullanıcı mesajını alır, niyet sınıflar, IntakePacket üretir.
    Akustik veya üretim kararı VERMEZ.
    """

    def __init__(self, api_key: str | None = None):
        self._api_key = api_key
        self._chat_history: list[dict] = []
        
        from core.llm_engine import get_engine
        self._llm = get_engine()
        logger.info("[SES USTASI] Başlatıldı")
    # ── Ana Giriş Noktası ─────────────────────────────────────────

    def process(
        self,
        message: str,
        context: dict | None = None,
        history: list | None = None,
    ) -> dict:
        """
        Kullanıcı mesajını işler.
        Döner:
          {
            "reply": str,          ← Kullanıcıya cevap
            "intake": IntakePacket | None,
            "route_to": agent_name | None,
            "needs_more_info": bool,
            "questions": str,
            "intent_match": dict | None,  ← Niyet sözlüğü eşleşmesi
          }
        """
        ctx = context or {}

        # ── Adım 1: Niyet sözlüğü eşleşmesi (sokak dili öncelikli) ──
        try:
            from core.intent_matcher import match_intent, get_clarification_question
            im = match_intent(message)
        except Exception:
            im = None

        if im and im.confidence >= 0.6:
            # Context'e intent bilgilerini yaz (downstream kullanım için)
            ctx.update({
                "user_intent":               im.user_intent,
                "listening_goal":            im.listening_goal,
                "system_style":              im.system_style,
                "inside_vs_outside_priority": im.inside_vs_outside_priority,
                "spl_vs_sq_profile":         im.spl_vs_sq_profile,
            })
            # ERKEN DÖNÜŞ İPTAL: Kullanıcı "GT12, sedan" gibi veriler de girmiş olabilir.
            # Veri kaybını önlemek ve direkt üretime paslamak için akışa devam ediyoruz.

        # ── Adım 2: Klasik intent sınıflandırması ─────────────────────
        intent, confidence = classify_intent(message)

        # Genel tavsiye veya bilgi sorularında direkt cevap ver
        if intent in ("genel_tavsiye", "woofer_sorgu"):
            reply = self._ask_gemini(message, ctx=ctx, history=history)
            return {
                "reply": reply,
                "intake": None,
                "route_to": "ses_ustasi",
                "needs_more_info": False,
                "questions": "",
                "intent_match": None,
            }

        # Akustik veya üretim niyetinde paket oluştur
        intake = self._build_intake_from_message(message, intent, confidence, ctx)
        
        # Eğer geçmiş konuşmalar sayesinde eksik veri kalmadıysa, artık genel sohbet yerine tasarıma geçmesi gerekir.
        normalized_panel = ctx.get("normalized_panel", {})
        missing_f = normalized_panel.get("missing_fields", ["fallback"])
        has_diameter = normalized_panel.get("diameter_inch", 0) > 0
        
        is_ready = False
        if len(missing_f) == 0 and has_diameter:
            # Kabin hesabı için her şey hazır!
            intake.user_intent = "kabin_tasarim"
            is_ready = True
            
        missing_q = ""
        if not is_ready and intake.user_intent in ("kabin_tasarim", "uretim_dosyasi"):
            nq = ctx.get("normalized_panel", {}).get("next_questions", [])
            if nq:
                missing_q = " ".join(nq)
            else:
                missing_q = "Lütfen kullanmak istediğiniz tam cihaz modelini veya T/S parametrelerini belirtiniz."

        # ── YENİ: TS Parametre Lookup Akışı (ARTIK HER ZAMAN ÇALIŞIR) ──
        ts_fetched = False
        ts_message = ""
        ts_technical_info = ""
        
        if intake.woofer_model and not intake.has_ts_params:
            brand_str = ctx.get("brand", "")
            model_str = intake.woofer_model
            lookup_prompt = (
                f"{brand_str} {model_str} subwoofer (car audio) için fabrika T/S parametrelerinden "
                f"Fs, Qts, Vas ve cihazın RMS Güç (Watt) değerini kesin olarak biliyor musun? Eğitildiğin verilerde net fabrikatör verisi varsa "
                f"SADECE JSON formatında dön: {{\"fs\": 34.0, \"qts\": 0.45, \"vas\": 55.0, \"rms\": 2000, \"xmax\": 18.0}}. BİLMİYORSAN VEYA EMİN DEĞİLSEN "
                f"SADECE 'BİLİNMİYOR' dön. Asla yaklaşık (approximate) tahmin yürütme."
            )
            
            # YENİ: URL kontrolü — Kullanıcı link atmışsa linkin içeriğini tara ve LLM'e bilgi olarak ver!
            url_match = re.search(r'(https?://[^\s]+)', message + " " + ctx.get("raw_message", ""))
            if url_match:
                url = url_match.group(1)
                try:
                    import requests
                    from bs4 import BeautifulSoup
                    resp = requests.get(url, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, 'html.parser')
                        page_text = " ".join(soup.stripped_strings)[:3000] # İlk 3000 karakter yeterli
                        lookup_prompt += f"\n\nKULLANICININ VERDİĞİ LİNK İÇERİĞİ ({url}):\n{page_text}\n(Eğer bu verilerin içinde Fs, Qts, Vas, RMS varsa mutlaka buradan al!)"
                except Exception as e:
                    logger.warning(f"URL okunamadı: {url} - {e}")

            try:
                ts_resp = self._llm.generate(prompt=lookup_prompt, temperature=0.1)
                import json, re
                if ts_resp and "{" in ts_resp and "fs" in ts_resp.lower():
                    start_idx = ts_resp.find("{")
                    end_idx = ts_resp.rfind("}") + 1
                    json_str = ts_resp[start_idx:end_idx]
                    ts_data = json.loads(json_str)
                    
                    def safe_float(v):
                        try:
                            v_clean = re.sub(r'[^\d.]', '', str(v))
                            return float(v_clean) if v_clean else 0.0
                        except:
                            return 0.0

                    fs = safe_float(ts_data.get("fs", 0))
                    qts = safe_float(ts_data.get("qts", 0))
                    vas = safe_float(ts_data.get("vas", 0))
                    rms = safe_float(ts_data.get("rms", 0))
                    xmax = safe_float(ts_data.get("xmax", 12.0))
                    
                    if fs > 0 and qts > 0 and vas > 0:
                        from schemas.intake_packet import TSParams
                        intake.ts_params = TSParams(fs=fs, qts=qts, vas=vas, xmax=xmax if xmax > 0 else 12.0, re=4.0)
                        if rms >= 50:
                            intake.rms_power = rms

                        ts_fetched = True
                        ts_technical_info = f"Cihazın fabrika verisi: Fs: {fs}Hz. (Yani çok alt frekans isteniyorsa cihaz limiti {fs}Hz etrafındadır, bu durumu kullanıcıya belli ederek gerçeği söyle)."
                        ts_message = f"Cihazın ({brand_str} {model_str}) parametrelerini veritabanından çektim (Fs: {fs}Hz, Qts: {qts:.2f}, Vas: {vas}L). Müşteriye hemen hesaba geçtiğini belirt."
            except Exception as e:
                logger.error("[SES USTASI] TS Lookup Hatası: %s", e)

        print(f"DEBUG SES_USTASI: finalized missing_q: {missing_q}, is_ready: {is_ready}, intent: {intent}")
        # LLM'i çağıracağımız durumlar:
        # 1. Eksik bilgi varsa (soru sormak için)
        # 2. Asıl niyet tavsiye/bilgi ise (ör. sunroof sorusu)
        # 3. Her şey hazır GELDİĞİNDE de (müşteriye 'hesaba geçiyoruz' demek için)
        
        target_agent = route(intake) if is_ready else None

        if missing_q or intent in ("genel_tavsiye", "woofer_sorgu") or is_ready:
            if ts_fetched:
                ctx["ts_technical_info"] = ts_technical_info
                
            if is_ready and not missing_q:
                # Tasarıma geçiş bildirimi
                missing_q = "Bilgiler tamamlandı. Kullanıcının son cümlesine saygılı bir onay ver, ardından hemen kabin tasarımına geçiyoruz de. Uzatma."
                
            intro = self._ask_gemini(message, ctx=ctx, missing_q=missing_q, history=history)
            
            if not intro or str(intro).strip().startswith("None"):
                intro = missing_q if missing_q else "Müşterinin sorunuyla ilgileniliyor."
            else:
                intro = intro.strip()
                
            return {
                "reply": intro,
                "intake": intake,
                "route_to": target_agent,
                "needs_more_info": not is_ready,
                "questions": missing_q if not is_ready else "",
            }

        # LLM çalışmazsa default fallback (artık pek buraya düşmez)
        return {
            "reply": "Sistemi hesaplıyorum, lütfen bekleyin.",
            "intake": intake,
            "route_to": target_agent,
            "needs_more_info": False,
            "questions": "",
        }

    # ── Yardımcı: Adapter Üzerinden AI Çağrısı ────────────────────

    def _ask_gemini(self, message: str, ctx: dict | None = None, missing_q: str = "", history: list | None = None) -> str:
        """Direkt google-genai API çağrısı — adapter zinciri yok."""
        import os
        ctx = ctx or {}

        known_info = []
        if ctx.get("vehicle") or ctx.get("vehicle_type"):
            known_info.append(f"- Araç tipi: {ctx.get('vehicle') or ctx.get('vehicle_type')}")
        if ctx.get("diameter_inch"):
            known_info.append(f"- Çap: {ctx['diameter_inch']}\"")
        if ctx.get("brand"):
            known_info.append(f"- Marka: {ctx['brand']}")
        if ctx.get("woofer_model"):
            known_info.append(f"- Model: {ctx['woofer_model']}")

        system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")
        if known_info:
            system_prompt += (
                "\n\nBU BİLGİLER ZATEN ELİMİZDE, KESİNLİKLE TEKRAR SORMA:\n"
                + "\n".join(known_info)
            )
            
        if ctx.get("ts_technical_info"):
            system_prompt += (
                f"\n\nTEKNİK UYARI: {ctx['ts_technical_info']}\n"
                "Kullanıcıya bu bilgiyi sezdirerek (Örn: 'Cihazın fabrika rezonansı şu, yani anca buraya kadar inebiliriz' şeklinde) gerçekçi bir yaklaşım sergile."
            )

        if ctx.get("vehicle") or ctx.get("vehicle_type"):
            v_type = ctx.get("vehicle") or ctx.get("vehicle_type")
            try:
                from core.constants import CABIN_GAIN_PROFILES
                f3_base = CABIN_GAIN_PROFILES.get(v_type, (50, 0))[0]
            except Exception:
                f3_base = 50
            
            system_prompt += (
                f"\n\nARAÇ AKUSTİK BİLGİSİ (FIZIK DETAYI):\nKullanıcının aracı: {v_type}. Ortalama kabin rezonans frekansı: ~{f3_base}Hz. "
                "Eğer kullanıcı alt frekans / bas performansı gibi yorumlar yaparsa, bu aracın fiziksel yapısını (örneğin kabin hacmi, tavan-taban mesafesi, bagaj yalıtımı vb.) bir akustik mühendisi gibi değerlendir. "
                "Kullanıcının mantığı doğruysa bilimsel olarak onayla, yanlışsa doğrusunu açıkla (Örn: 'Doblo gibi Van kasalarda tavan-taban arasındaki paralellik içerideki rezonans frekansını ~50Hz civarına çeker'). "
                "Sadece kısaca 1-2 cümlelik profesyonel fiziksel analiz yap."
            )
            
        # ── BİLGİ KÜTÜPHANESİ ENTEGRASYONU ────────────────────────────
        # Sadece konuya ilgili koleksiyondan temiz, sınırlı veri getir.
        # keyword yoksa veya eşleşme bulunamazsa sistem promptuna HİÇBİR ŞEY eklenmez.
        try:
            from core.knowledge_engine import query_library

            # Arama için keyword havuzu — None değerleri içeride temizlenir
            lib_keywords = [
                ctx.get("brand"),
                ctx.get("woofer_model"),
                ctx.get("vehicle") or ctx.get("vehicle_type"),
                # Mesajdan ilk birkaç anlamlı kelime (araç/marka adı gibi)
                *message.split()[:4],
            ]

            # Konuya göre koleksiyon seçimi (otomatik; açıkça belirtmek gerekmez)
            lib_context = query_library(
                keywords=lib_keywords,
                collections=None,   # _auto_select_collections devreye girer
                max_chars=1200,
                top_n=5,
            )

            if lib_context:
                system_prompt += (
                    "\n\n[DD1 KÜTÜPHANE BİLGİSİ — YALNIZCA KONUYLA İLGİLİ]:\n"
                    + lib_context
                    + "\n\nYukarıdaki kütüphane bilgisini yalnızca müşterinin konusuyla"
                    " doğrudan ilgiliyse kullan. Alakasız detayları tekrar etme."
                )
        except Exception as e:
            logger.error("[SES USTASI] Kütüphane sorgusu başarısız: %s", e)
            
        if missing_q:
            system_prompt += (
                f"\n\nSİSTEM UYARISI: Tasarımı tamamlamak için şu bilgi eksik: '{missing_q.strip()}'. "
                "Bu eksiği müşteriye sıradan bir anketör gibi ('Hedefiniz SPL midir?') diye sorma! Dükkanındaki müşteriye nasıl soracaksan öyle ustaca ve samimi bir insan diliyle sor. Robotik davranırsan müşteri kızar."
            )

        try:
            return self._llm.generate(prompt=message, system_prompt=system_prompt, temperature=0.7, history=history)
        except Exception as e:
            logger.error("[SES USTASI] LLM_Engine çağrısı çöktü: %s", e)
            return missing_q if missing_q else ""


    # ── Yardımcı: Mesajdan IntakePacket ───────────────────────────

    def _build_intake_from_message(
        self,
        message: str,
        intent: str,
        confidence: float,
        context: dict | None,
    ) -> IntakePacket:
        """
        Gelen mesaja göre IntakePacket oluşturur (yeni interpreter kullanarak).
        """
        ctx = context or {}
        
        # chat_service.py zaten combined history ile parse_message çağırdı ve bize verdi.
        # Eğer context dolu geldiyse, tekrar regex koşturup geçmişi kaybetme!
        if ctx.get("normalized_panel"):
            ext = ctx
        else:
            from core.interpreter import parse_message
            ext = parse_message(message, ctx)
            
        pan = ext.get("normalized_panel", {})

        _ctx_diam = ctx.get("diameter_inch")
        diam_inch = pan.get("diameter_inch") or (_ctx_diam if _ctx_diam else 12)
        woofer_model = pan.get("woofer_model") or ctx.get("woofer_model") or ""
        target_freq_hz = ext.get("target_hz") or ctx.get("target_freq_hz")
        usage_domain = pan.get("domain", "car_audio")
        bass_char = ext.get("bass_char", "")
        
        rms_power = float(ctx.get("rms_power", 500))
        import re
        m_rms = re.search(r'(\d{2,4})\s*(?:[Ww](?:att)?|rms)', message, re.IGNORECASE)
        if m_rms:
            rms_power = float(m_rms.group(1))

        _char_purpose = {
            "SPL": "SPL", "patlamalı": "SPL",
            "tok": "SQL",  "günlük": "Günlük Bass", "flat": "Günlük Bass",
        }
        purpose = ctx.get("goal") or pan.get("goal") or _char_purpose.get(bass_char, "SQL")

        vehicle = pan.get("vehicle_type") or ctx.get("vehicle_type") or ctx.get("vehicle", "Sedan")
        if usage_domain in ("outdoor", "pro_audio", "home_audio"):
            vehicle = "Dış Sistem"

        ts = None
        if ctx.get("fs") and ctx.get("qts") and ctx.get("vas"):
            ts = TSParams(
                fs=ctx.get("fs"), qts=ctx.get("qts"), vas=ctx.get("vas"),
                xmax=ctx.get("xmax"),
            )

        enclosure_type = pan.get("enclosure_preference") or ctx.get("enclosure_preference") or "aero"
        # Eğer belirtilmediyse "aero" kabul et (Tahmini Portlu ise yine aero vs. yapılabilir)
        if "Belirtilmedi" in enclosure_type:
            enclosure_type = "aero"

        return build_intake(
            raw_message=message,
            intent=intent,
            vehicle=vehicle,
            purpose=purpose,
            diameter_inch=diam_inch,
            rms_power=rms_power,
            woofer_model=woofer_model,
            ts=ts,
            confidence=confidence,
            usage_domain=usage_domain,
            bass_char=bass_char,
            target_freq_hz=target_freq_hz,
            enclosure_type=enclosure_type,
        )

