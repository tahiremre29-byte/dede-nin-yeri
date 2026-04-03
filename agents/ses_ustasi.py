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
            reply = self._ask_gemini(message, ctx=ctx)
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
        missing_q = ""
        _np_ctx = ctx.get("normalized_panel", {})
        
        if _np_ctx.get("next_questions"):
            missing_q = " ".join(_np_ctx["next_questions"])

        # ── YENİ: TS Parametre Lookup Akışı (ARTIK HER ZAMAN ÇALIŞIR) ──
        ts_fetched = False
        ts_message = ""
        ts_technical_info = ""
        
        if intake.woofer_model and not intake.has_ts_params:
            brand_str = ctx.get("brand", "")
            model_str = intake.woofer_model
            lookup_prompt = (
                f"{brand_str} {model_str} subwoofer (car audio) için fabrika T/S parametrelerinden "
                f"Fs, Qts ve Vas değerlerini kesin olarak biliyor musun? Biliyorsan SADECE JSON formatında dön: "
                f"{{\"fs\": 30.0, \"qts\": 0.45, \"vas\": 55.0}}. Emin değilsen veya bulamazsan "
                f"SADECE 'BİLİNMİYOR' kelimesini dön. Başka hiçbir açıklama yazma."
            )
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
                            # clean non-numeric chars except dot
                            v_clean = re.sub(r'[^\d.]', '', str(v))
                            return float(v_clean) if v_clean else 0.0
                        except:
                            return 0.0

                    fs = safe_float(ts_data.get("fs", 0))
                    qts = safe_float(ts_data.get("qts", 0))
                    vas = safe_float(ts_data.get("vas", 0))
                    
                    if fs > 0 and qts > 0 and vas > 0:
                        from schemas.intake_packet import TSParams
                        intake.ts_params = TSParams(fs=fs, qts=qts, vas=vas, xmax=12.0, re=4.0)
                        ts_fetched = True
                        ts_technical_info = f"Cihazın fabrika verisi: Fs: {fs}Hz. (Yani çok alt frekans isteniyorsa cihaz limiti {fs}Hz etrafındadır, bu durumu kullanıcıya belli ederek gerçeği söyle)."
                        ts_message = f"Reis cihazın ({brand_str} {model_str}) parametrelerini veritabanından çektim (Fs: {fs}Hz, Qts: {qts:.2f}, Vas: {vas}L). Hemen üretim hattına, hesap kitabına paslıyorum işi."
                    else:
                        ts_fail_msg = "Ayrıca Reis cihazın parametrelerini (Fs, Qts, Vas) veritabanında bulamadım (özel seri olabilir). Sana zahmet kataloğundan Fs, Qts ve Vas değerlerini yazar mısın?"
                        missing_q = missing_q + " " + ts_fail_msg if missing_q else ts_fail_msg
                else:
                    ts_fail_msg = "Ayrıca Reis cihazın parametrelerini (Fs, Qts, Vas) veritabanında bulamadım (özel seri olabilir). Sana zahmet kataloğundan Fs, Qts ve Vas değerlerini yazar mısın?"
                    missing_q = missing_q + " " + ts_fail_msg if missing_q else ts_fail_msg
            except Exception as e:
                logger.error("[SES USTASI] TS Lookup Hatası: %s", e)
                ts_fail_msg = "Ayrıca Reis cihazın parametrelerini (Fs, Qts, Vas) veritabanında bulamadım (özel seri olabilir). Sana zahmet kataloğundan Fs, Qts ve Vas değerlerini yazar mısın?"
                missing_q = missing_q + " " + ts_fail_msg if missing_q else ts_fail_msg

        print(f"DEBUG SES_USTASI: finalized missing_q: {missing_q}")
        if missing_q:
            # Eksik bilgi var — AI uzerinden doğal forma sok
            # Teknik bilgiyi context'e ekleyelim
            if ts_fetched:
                ctx["ts_technical_info"] = ts_technical_info
                
            intro = self._ask_gemini(message, ctx=ctx, missing_q=missing_q)
            # Guard
            if not intro or str(intro).strip().startswith("None"):
                intro = missing_q
            else:
                intro = _sanitize_reply(intro)
            return {
                "reply": intro,
                "intake": intake,
                "route_to": None,
                "needs_more_info": True,
                "questions": missing_q,
            }

        agent = route(intake)
        reply_str = ts_message if ts_fetched else f"Talebinizi {agent.replace('_', ' ').title()}'na iletiyorum."
        return {
            "reply": reply_str,
            "intake": intake,
            "route_to": agent,
            "needs_more_info": False,
            "questions": "",
        }

    # ── Yardımcı: Adapter Üzerinden AI Çağrısı ────────────────────

    def _ask_gemini(self, message: str, ctx: dict | None = None, missing_q: str = "") -> str:
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
                "Kullanıcıya bu bilgiyi sezdirerek (Örn: 'Reis senin cihazın frekansı şu, yani anca buraya kadar ineriz' şeklinde) gerçekçi bir yaklaşım sergile."
            )
            
        if missing_q:
            system_prompt += (
                f"\n\nSİSTEM MESAJI: Tasarımı tamamlamak için şu bilgi eksik: '{missing_q.strip()}'. "
                "Bu eksiği kullanıcıya doğal, usta ağzıyla ve doğrudan sor. Yukarıdaki teknik uyarıyı (varsa) soruyla harmanla. 'Dinliyorum' vb. robotik girişler yapma. Tek soru sor."
            )

        try:
            return self._llm.generate(prompt=message, system_prompt=system_prompt, temperature=0.7)
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
        from core.interpreter import parse_message
        
        ctx = context or {}
        
        # interpreter'i çağır 
        # (Gerçekte chat_service zaten çağırıyor ama SesUstasi hala mesajla çalışıyor)
        ext = parse_message(message, ctx)
        pan = ext.get("normalized_panel", {})

        diam_inch = pan.get("diameter_inch") or int(ctx.get("diameter_inch", 12))
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
        )

