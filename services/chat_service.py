"""
services/chat_service.py
DD1 Chat Servisi — Mesaj İşleme Orchestratörü

Thin router'ın çağırdığı tek servis.
Ses Ustası ajanını çalıştırır, router sonucuna göre KabinUstası'na aktarır.

Aşama 1: Ses Ustası → niyet sınıflama + IntakePacket
Aşama 2: Kabin gerekliyse → design_service.run_design()
Fallback: AI yoksa kural tabanlı extraction + route
"""
from __future__ import annotations
import logging
from typing import Optional

logger = logging.getLogger("dd1.chat_service")


from core.interpreter import parse_message as _rule_based_extract


def _build_user_reply(ext: dict, intent: str, conf: float) -> str:
    """
    Kullanıcıya gösterilen doğal Türkçe yanıt.
    KURAL: enclosure_preference_normalized ZORUNLU olarak uygulanır — override edilemez.
    """
    panel    = ext.get("normalized_panel", {})
    dia      = panel.get("diameter_inch") or ext["diameter_inch"]
    model    = ext["woofer_model"]
    hz       = ext.get("target_hz")
    bass     = ext.get("bass_char", "")
    brand    = panel.get("brand")
    size_raw = panel.get("diameter_raw") or f'{dia}"'
    enc_pref = panel.get("enclosure_preference", "ported")  # default ported
    enc_src  = panel.get("constraint_source", "inferred")

    # ── GLOSSARY EXPLANATION ─────────────────────────────────────────
    if intent == "glossary_explanation":
        msg_lower = (ext.get("raw_message", "")).lower()
        # Bagaj ölçüsü açıklaması
        if "bagaj" in msg_lower:
            return (
                "Bagaj ölçüsü, kutunun fiziksel olarak sığıp sığmayacağını anlamamda kritik.\n\n"
                "Metre veya cm olarak en, yükseklik, derinlik ölçülerini verirsen:\n"
                "• Sığma analizi yaparım\n"
                "• Kutu yönü öneririm\n"
                "• Port yerleşim zorluğunu belirlerim\n\n"
                'Örneğin: \"80x40x50\" veya \"en 80 yükseklik 40 derinlik 50\" yaz.'
            )
        if "portlu" in msg_lower or "port" in msg_lower:
            return (
                "Portlu kutu basını dışarı iter, daha derin ve güçlü bir bas üretir. "
                "Günlük kullanımda da iyi çalışır, yer uygunsa önerilir.\n\n"
                "Portlu mu, kapalı mı istiyorsun?"
            )
        if "kapalı" in msg_lower:
            return (
                "Kapalı kutu sıkı, kontrollü bas verir. "
                "Daha kompakt, bagajı daha az kaplar.\n\n"
                "Portlu mu, kapalı mı istiyorsun?"
            )
        if any(k in msg_lower for k in ['sql','sbp','spb']):
            return (
                "Dengeli ve yüksek sesli kurgu istiyorsun, anladım. "
                "Araç ve sürücü bilgisini verirsen sana özel kabin hesaplayabilirim."
            )
        return (
            "Bagaj öncelikleri, kutu tipi, hedef kullanım veya ölçü hakkında soru sorabilirsin."
        )

    # ── CLARIFICATION REQUEST ────────────────────────────────────────
    if intent == "clarification_request":
        return (
            "Sormak istediğin konuyu biraz açar mısın? "
            "Bagaj öncelik, portlu/kapalı kutu, kutu hacmi ya da hedef kullanım hakkında açıklama yapabilirim."
        )

    # ── ENCLOSURE STRING — KULLANICI BELİRTTİYSE ONUN DEDİĞİ ────────
    enc_label_map = {
        'sealed':    'kapalı kutu',
        'ported':    'portlu kutu',
        'bandpass':  'bandpass kutu',
    }
    enc_label = enc_label_map.get(enc_pref, 'portlu kutu')
    if enc_src == 'user_explicit':
        enc_str = f"**{enc_label}**"   # Bold: kullanıcı açıkça belirtti
    else:
        enc_str = enc_label

    # ── HOME AUDIO DOMAIN ────────────────────────────────────────────
    domain = panel.get("domain", "car_audio")

    if domain == "home_audio":
        brand_str = f"{brand} " if brand else ""
        q_list    = panel.get("next_questions") or []
        ack_parts = []
        if brand_str:                       ack_parts.append(f"{brand_str}sürücü")
        if size_raw and size_raw != '12"':  ack_parts.append(size_raw)
        if panel.get("room_size_m2"):       ack_parts.append(f"{panel['room_size_m2']} m² oda")
        if panel.get("placement_notes"):    ack_parts.append(panel["placement_notes"])
        ack_str = ", ".join(ack_parts) if ack_parts else "sürücü"
        if not q_list:
            return (
                f"Harika, {ack_str} için ev kullanımı kabini tasarımına hazırım. "
                f"Hesabı başlatmamı ister misin?"
            )
        q_str = " ".join(q_list)
        return (
            f"Ev / oda kullanımı için not aldım: {ack_str}. "
            f"{q_str}"
        )

    # ── OUTDOOR DOMAIN ───────────────────────────────────────────────
    if domain == "outdoor":
        brand_str = f"{brand} " if brand else ""
        q_list    = panel.get("next_questions") or []
        ack_str   = f"{brand_str}{size_raw}" if (size_raw and size_raw != '12"') else f"{brand_str}sürücü"
        if not q_list:
            return (
                f"Dış sistem / açık hava için {ack_str} kabin tasarımına hazırım. "
                f"T/S parametreleriniz varsa daha kesin hesap yapabilirim."
            )
        q_str = " ".join(q_list)
        return (
            f"Dış sistem için notumu aldım: {ack_str}. "
            f"{q_str}"
        )

    # ── KABIN TASARIM (car_audio) ─────────────────────────────────────
    if intent == "kabin_tasarim":
        brand_str = f"{brand} " if brand else ""
        q_list    = panel.get("next_questions") or []

        if enc_src == "user_explicit":
            enc_mention = f" için **{enc_label}**"
        else:
            enc_mention = " için kabin"

        ack_parts = []
        if size_raw and size_raw != '12"':
            ack_parts.append(f"{brand_str}{size_raw} sürücü")
        elif brand_str:
            ack_parts.append(f"{brand_str}sürücü")
        if panel.get("vehicle_model"):
            ack_parts.append(panel["vehicle_model"])
        elif panel.get("vehicle_type"):
            ack_parts.append(panel["vehicle_type"])
        ack_str = " ve ".join(ack_parts) if ack_parts else "sürücü"

        if not q_list:
            # Tüm bilgiler tamam — direkt hesaba geç
            fit_comment = panel.get("usta_fit_comment", "")
            fit_str = f" {fit_comment}" if fit_comment else ""
            return (
                f"Tamam, {ack_str}{enc_mention} için hesaba giriyorum.{fit_str}"
            )
        # Fit yorumu varsa sorudan önce ekle
        fit_comment = panel.get("usta_fit_comment", "")
        fit_prefix = f"{fit_comment} " if fit_comment else ""
        q_str = " ".join(q_list)
        return (
            f"Anladım, {ack_str}{enc_mention} notumu aldım. "
            f"{fit_prefix}{q_str}"
        )


    elif intent == "woofer_sorgu":
        brand_str = f"{brand} " if brand else ""
        return (
            f"{brand_str}{size_raw} çaplı sürücüler için veritabanında arama yapabilirim. "
            f"Belirli bir güç aralığı var mı?"
        )
    elif intent == "uretim_dosyasi":
        model_str = f"Sürücü: {model}. " if model != "Belirtilmedi" else ""
        return (
            f"DXF / STL üretimi için önce tasarımı tamamlamamız gerekiyor. "
            f"{model_str}Kabin hesabına başlamak için araç tipini ve bagaj ölçüsünü ver."
        )
    else:
        q_list = panel.get("next_questions") or []
        if q_list:
            return f"Dinliyorum. " + " ".join(q_list)
        return (
            f"Dinliyorum. Araç tipini ve hedef kullanımı paylaşırsanız size özel kabin önerebilirim."
        )



def _outdoor_reply(ext: dict) -> dict:
    """Açık hava / dış sistem talebi için kullanıcı dostu yanıt."""
    model_str = ext.get("woofer_model") or "belirtilmedi"
    size_raw  = ext.get("extracted_entities", {}).get("size_raw") or f'{ext["diameter_inch"]}"'
    hz_str    = f"{int(ext['target_hz'])} Hz" if ext.get("target_hz") else None
    char_str  = ext.get("bass_char", "")
    domain_label = {
        "outdoor":    "Açık Hava",
        "pro_audio":  "Pro Audio",
        "home_audio": "Ev Sistemi",
    }.get(ext["usage_domain"], "Dış Sistem")

    detail = f", tuning: {hz_str}" if hz_str else ""
    detail += f", karakter: {char_str}" if char_str else ""

    user_reply = (
        f"{domain_label} sistemi için talep aldım. "
        f"Sürücü: {model_str}, çap: {size_raw}{detail}.\n\n"
        f"Bu alan araç içi tasarımların dışında kalıyor; ancak {size_raw} sürücü için "
        f"portlu kabin hesabı yapabilirim. Devam etmek ister misiniz? "
        f"T/S parametreleriniz (Fs, Qts, Vas) varsa paylaşın."
    )
    return {
        "action":                  "ask",
        "reply":                   user_reply,
        "route_to":                "ses_ustasi",
        "design":                  None,
        "questions":               "- T/S parametreleri (Fs, Qts, Vas) var mı?\n- Kabin malzemesi kalınlığı?",
        "errors":                  [],
        "extracted_info":          ext,
        "extracted_entities":      ext.get("extracted_entities", {}),
        "normalized_entities":     ext.get("normalized_entities", {}),
        "user_visible_response":   user_reply,
        "internal_debug_message":  f"[outdoor_domain] usage_domain={ext.get('usage_domain')}",
    }


def process_message(
    message: str,
    context: dict | None = None,
    history: list | None = None,
) -> dict:
    """
    Kullanıcı mesajını işler — tam orchestration.

    Döner:
      {
        "action":                  str,
        "reply":                   str,   ← user_visible_response ile aynı
        "route_to":                str | None,
        "design":                  dict | None,
        "questions":               str,
        "errors":                  list[str],
        "extracted_info":          dict,
        "extracted_entities":      dict,   ← ham parse sonuçları
        "normalized_entities":     dict,   ← normalize edilmiş değerler
        "user_visible_response":   str,    ← kullanıcıya gösterilen
        "internal_debug_message":  str,    ← UI'da GÖSTERİLMEZ
      }
    """
    # ── History'deki kullanıcı mesajlarını birleştir ──
    # Böylece önceki turlarda verilen bilgiler (bagaj, araç tipi, hedef vb.)
    # kaybolmaz ve aynı soru tekrar sorulmaz.
    combined_message = ""
    if history:
        for h in history:
            role = h.get("role", "")
            if role in ("user", "human"):
                combined_message += h.get("content", h.get("message", "")) + " "
    combined_message += message
    
    ext = _rule_based_extract(combined_message)
    # raw_message'ı da sakla (glossary/clarification için)
    ext["raw_message"] = message
    
    # EKİP MONİTÖRÜ İÇİN CANLI SİNYAL FIRLAT (+board.html Sözcü animasyonu)
    from datetime import datetime
    try:
        with open(r"C:\Users\DDSOUND\Desktop\exemiz\bridge_debug.log", "a", encoding="utf-8") as _f:
            _f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [TRANSITION] req=USER session=ONLINE - -> sozcu packet=MesajIsleme\n")
    except:
        pass

    def _wrap(d: dict) -> dict:
        """Her response'a standart alanları ekle."""
        d.setdefault("intent",              ext.get("intent", ""))
        d.setdefault("confidence",          ext.get("confidence", 0.0))
        d.setdefault("extracted_entities",  ext.get("extracted_entities", {}))
        d.setdefault("normalized_entities", ext.get("normalized_entities", {}))
        d.setdefault("user_visible_response",  d.get("reply", ""))
        d.setdefault("internal_debug_message", "")
        return d

    try:
        from agents.ses_ustasi import SesUstasi
        agent = SesUstasi()

        # ── Context normalizasyonu: frontend → ses_ustasi ──────────────────
        # Frontend: vehicle key gönderir, ses_ustasi vehicle_type / vehicle bekler
        normalized_ctx = dict(context or {})
        if normalized_ctx.get("vehicle") and not normalized_ctx.get("vehicle_type"):
            normalized_ctx["vehicle_type"] = normalized_ctx["vehicle"]
        # ext normalied_panel'den ek bilgileri context'e doldur
        _np = ext.get("normalized_panel", {})
        for _k in ("brand", "diameter_inch", "diameter_raw",
                   "vehicle_type", "goal", "enclosure_preference"):
            if _np.get(_k) and not normalized_ctx.get(_k):
                normalized_ctx[_k] = _np[_k]
        if ext.get("rms_power") and not normalized_ctx.get("rms_power"):
            normalized_ctx["rms_power"] = ext["rms_power"]
        # normalized_panel'i de context'e ekle (ses_ustasi ctx.get("normalized_panel") kullanır)
        if _np and not normalized_ctx.get("normalized_panel"):
            normalized_ctx["normalized_panel"] = _np

        agent_result = agent.process(message, context=normalized_ctx)

        intake = agent_result.get("intake")
        if intake and getattr(intake, "usage_domain", "car_audio") in ("outdoor", "pro_audio", "home_audio"):
            outer = _outdoor_reply(ext)
            outer["reply"] = agent_result.get("reply") or outer["reply"]
            outer["user_visible_response"] = outer["reply"]
            return _wrap(outer)

        if agent_result["needs_more_info"]:
            user_reply = agent_result["reply"]
            intent_match_info = agent_result.get("intent_match")  # intent_matcher'dan

            # ── Tezgahtar Tetikleyici ────────────────────────────────────────
            # brand + diameter yakalanmışsa model aday listesi oluştur
            panel = ext.get("normalized_panel", {})
            brand    = panel.get("brand") or ext.get("brand", "")
            diam_in  = panel.get("diameter_inch") or ext.get("diameter_inch", 0)
            rms_w    = ext.get("rms_power", 500)
            spl_prof = "sql"
            if intent_match_info:
                spl_prof = intent_match_info.get("system_style", "sql")
                # system_style'ı spl_sq_profile'a mapla
                _style_to_prof = {
                    "stage_rear": "spl", "aggressive_loud": "spl", "show_loud": "spl",
                    "sub_heavy_inside": "spl_sql_border", "inside_sub_focus": "spl_sql_border",
                    "sql_balanced": "sql", "controlled_sub": "sql_sq_border",
                    "cadde_mod": "sql_to_spl", "hard_spl_bias": "spl",
                    "ambiguous_dual_path": "spl_or_sql",
                }
                spl_prof = _style_to_prof.get(spl_prof, "sql")

            ui_cards  = None
            resp_mode = "chat"
            short_reply = user_reply

            # Eğer Usta doğrudan model kodunu veya sürücü çapını soruyorsa Tezgahtar araya girip liste DÖKMESİN.
            missing_f = panel.get("missing_fields", [])
            skip_tz = True  # KULLANICI TALEBİ ÜZERİNE TEZGAHTAR ŞİMDİLİK TAMAMEN KAPATILDI

            if not skip_tz and (brand or ext.get("extracted_entities", {}).get("size_raw")):
                try:
                    from core.model_kandidat import get_model_candidates
                    from core.tezgahtar import present_candidates
                    candidates = get_model_candidates(
                        brand=brand,
                        diameter_inch=float(diam_in) if diam_in else 12,
                        rms_power=float(rms_w),
                        spl_sq_profile=spl_prof,
                    )
                    if candidates:
                        user_intent = intent_match_info.get("user_intent", "") if intent_match_info else ""
                        tz = present_candidates(
                            candidates=candidates,
                            brand=brand,
                            diameter_inch=float(diam_in) if diam_in else 12,
                            rms_power=float(rms_w),
                            spl_sq_profile=spl_prof,
                            user_intent=user_intent,
                        )
                        ui_cards   = tz["ui_cards"]
                        resp_mode  = "tezgahtar"
                        # Chat reply kısa kalır — ayrıntı kartlarda
                        short_reply = tz["question"]  # sadece kapanış sorusu
                except Exception as tz_exc:
                    logger.debug("[TEZGAHTAR] aktive edilemedi: %s", tz_exc)

            return _wrap({
                "action":                  "ask",
                "reply":                   short_reply,
                "route_to":                None,
                "design":                  None,
                "questions":               agent_result.get("questions", ""),
                "errors":                  [],
                "extracted_info":          ext,
                "user_visible_response":   short_reply,
                "internal_debug_message":  f"[needs_more_info] intent={ext['intent']} conf={ext['confidence']} tezgahtar={'on' if resp_mode=='tezgahtar' else 'off'}",
                "mode":                    resp_mode,
                "ui_cards":                ui_cards,
            })

        route_to = agent_result.get("route_to")

        if route_to == "kabin_ustasi" and intake is not None:
            from services.design_service import run_design
            design_result = run_design(intake)
            if design_result["success"]:
                acoustic    = design_result["acoustic_packet"]
                user_reply  = design_result.get("advice") or agent_result["reply"]
                return _wrap({
                    "action":    "design",
                    "reply":     user_reply,
                    "route_to":  "kabin_ustasi",
                    "design": {
                        "design_id":      acoustic.design_id,
                        "net_volume_l":   acoustic.net_volume_l,
                        "tuning_hz":      acoustic.tuning_hz,
                        "port_area_cm2":  acoustic.port_area_cm2,
                        "port_length_cm": acoustic.port_length_cm,
                        "enclosure_type": acoustic.enclosure_type,
                        "dimensions":     acoustic.dimensions.model_dump(),
                        "packet_hash":    acoustic.packet_hash,
                        "advice":         design_result.get("advice", ""),
                        "warnings":       design_result.get("warnings", []),
                    },
                    "questions":               "",
                    "errors":                  [],
                    "extracted_info":          ext,
                    "user_visible_response":   user_reply,
                    "internal_debug_message":  f"[design_ok] design_id={acoustic.design_id}",
                })
            else:
                err_msg = "Kabin hesabı tamamlanamadı. Lütfen sürücü bilgilerini kontrol edin."
                return _wrap({
                    "action":                  "error",
                    "reply":                   err_msg,
                    "route_to":                None,
                    "design":                  None,
                    "questions":               "",
                    "errors":                  design_result["errors"],
                    "extracted_info":          ext,
                    "user_visible_response":   err_msg,
                    "internal_debug_message":  f"[design_fail] errors={design_result['errors']}",
                })

        if route_to == "lazer_ajani":
            user_reply = "DXF / STL üretimi için önce kabin tasarımını tamamlamamız gerekiyor. Sürücü bilgilerini paylaşır mısınız?"
            return _wrap({
                "action":                  "route",
                "reply":                   user_reply,
                "route_to":                "lazer_ajani",
                "design":                  None,
                "questions":               "",
                "errors":                  [],
                "extracted_info":          ext,
                "user_visible_response":   user_reply,
                "internal_debug_message":  "[route] lazer_ajani",
            })

        user_reply = agent_result["reply"]
        return _wrap({
            "action":                  "info",
            "reply":                   user_reply,
            "route_to":                route_to,
            "design":                  None,
            "questions":               "",
            "errors":                  [],
            "extracted_info":          ext,
            "user_visible_response":   user_reply,
            "internal_debug_message":  f"[info] route={route_to}",
        })

    except (ValueError, Exception) as exc:
        exc_name = type(exc).__name__
        exc_msg  = str(exc).lower()

        # ── Hata sınıflandırması ────────────────────────────────────────────────
        if any(k in exc_msg for k in ("api key", "api_key", "invalid_argument",
                                       "key expired", "api_key_invalid")):
            err_class = "key_invalid"
        elif any(k in exc_msg for k in ("quota", "resource exhausted", "rate limit",
                                         "too many requests", "429")):
            err_class = "quota_exceeded"
        elif any(k in exc_msg for k in ("timeout", "timed out", "deadline")):
            err_class = "timeout"
        elif any(k in exc_msg for k in ("connection", "transport", "network", "ssl")):
            err_class = "network"
        else:
            err_class = "runtime"

        # ── Backend log — tam detay ─────────────────────────────────────────────
        logger.warning(
            "[CHAT_SERVICE] AI hata sınıfı=%s | %s: %s",
            err_class, exc_name, exc,
            exc_info=(err_class == "runtime"),  # sadece beklenmeyen hatalarda full trace
        )

        if ext["usage_domain"] in ("outdoor", "pro_audio", "home_audio"):
            result = _wrap(_outdoor_reply(ext))
            result["ai_mode"] = "standard"
            return result

        from core.router import quick_route
        agent_name, intent, conf = quick_route(message)
        user_reply = _build_user_reply(ext, intent, conf)


        return _wrap({
            "action":                  "ask",
            "reply":                   user_reply,
            "route_to":                agent_name,
            "design":                  None,
            "questions":               "",
            "errors":                  [],
            "extracted_info":          ext,
            "user_visible_response":   user_reply,
            "internal_debug_message":  (
                f"[fallback=standard] ai_error={err_class} | "
                f"exc={exc_name} | intent={intent} conf={conf:.0%}"
            ),
            "ai_mode":       "standard",    # UI göstergesi için
            "ai_error_class": err_class,    # frontend log için
        })
