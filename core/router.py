"""
core/router.py
DD1 Ajan Router — İsteği doğru ajana yönlendirir.

Sınıflama hiyerarşisi:
  1. Lazer anahtar kelimeleri → Lazer Ajanı
  2. Akustik/kabin anahtar kelimeleri → Kabin Ustası
  3. Diğer → Ses Ustası (varsayılan)

Router görevleri:
  - isteği sınıflandır
  - IntakePacket üret veya doğrula
  - eksik veri için soru üret
  - log kaydı yaz
"""
from __future__ import annotations
import re, logging
from datetime import datetime
from typing import Literal

from schemas.intake_packet import IntakePacket, IntentType

logger = logging.getLogger("dd1.router")

AgentName = Literal["ses_ustasi", "kabin_ustasi", "hifi_ustasi", "lazer_ajani"]

# ── Sınıflama Anahtar Kelimeleri ─────────────────────────────────────────────

_LAZER_KEYWORDS = re.compile(
    r"dxf|svg|stl|lazer|laser|kesim|nesting|finger.?joint|kilit.?geçme|"
    r"üretim.?dosya|çizim|imalat.?çizim|panel.?kes|format|export",
    re.IGNORECASE,
)

_ACOUSTIC_KEYWORDS = re.compile(
    r"litre|hacim|volume|port|tuning|hz|kabin|sealed|bassreflex|aero|bandpass|"
    r"pandizot|polyester|t/?s|thiele|small|fs|qts|vas|xmax|kapalı.?kutu|"
    r"ported|hesap|hesapla|ölçü|boyut|kaç.?litre|kaç.?hz|bas.?kabin|sub.?kabin",
    re.IGNORECASE,
)

_WOOFER_KEYWORDS = re.compile(
    r"woofer|hoparlör|subwoofer|speaker|sürücü|model|hertz|jl.?audio|"
    r"sundown|kicker|pioneer|sony|focal|morel|beyma",
    re.IGNORECASE,
)

_FEEDBACK_KEYWORDS = re.compile(
    r"feedback|geri.?bildirim|değerlend|puan|memnun|revizyon|saha.?notu",
    re.IGNORECASE,
)

_OUTDOOR_KEYWORDS = re.compile(
    r"açık.?hava|acik.?hava|dış.?sistem|dis.?sistem|dış.?mekan|dis.?mekan|"
    r"outdoor|pro.?audio|sahne.?ses|pa.?sistem|anfi|konser|"
    r"atölye|atolye|dükkan|dukkan|home.?audio|ev.?sistemi",
    re.IGNORECASE,
)

_BASS_CHAR_MAP = {
    r"patlamalı|pump|agresif":      "patlamalı",
    r"tok|derin|sql|warm":          "tok",
    r"spl|yarış|sert|impact":       "SPL",
    r"günlük|daily|müzik|clean":    "günlük",
    r"flat|ntr|referans":           "flat",
}

_MODEL_PATTERNS = [
    # Marka + model (sayılar dahil, virgül/noktalı virgül/inç/hz vb. öncesinde dur)
    re.compile(
        r'\b(jbl|hertz|sundown|focal|alpine|kenwood|pioneer|sony|kicker|'
        r'rockford|morel|skar|dd\.audio|dd|beyma|eminence|rcf|fane|'
        r'peavey|qsc|polk|jl\.audio|for.?x|mobass|cadence)'
        r'[\s\-]+([\w][\w\s\-\.]{1,40}?)'
        r'(?=\s*(?:[,;]|açık|araç|inç|inch|hz|hertz|litre|\d+\s*[wW]\b|$))',
        re.IGNORECASE,
    ),
]

# ── Sınıflama Fonksiyonu ─────────────────────────────────────────────────────

def classify_intent(message: str) -> tuple[IntentType, float]:
    """
    Kullanıcı mesajını niyet türüne çevirir.
    Döner: (intent_type, confidence_score)
    """
    if _LAZER_KEYWORDS.search(message):
        return "uretim_dosyasi", 0.92
    # Kabin kelimesi + açık hava/outdoor → kabin_tasarim (outdoor domain)
    if _OUTDOOR_KEYWORDS.search(message) and (
        _ACOUSTIC_KEYWORDS.search(message)
        or re.search(r"kabin|kutu|tasarla|hesapla", message, re.IGNORECASE)
    ):
        return "kabin_tasarim", 0.82
    if _FEEDBACK_KEYWORDS.search(message):
        return "feedback_gonder", 0.90
        
    # Tavsiye veya genel soru (nasıl, uyar mı, olur mu, kaç cm) => genel_tavsiye
    if re.search(r"fark\s*eder\s*mi|şart\s*mı|uyar\s*mı|hangisi|olur\s*mu|uyumlu|mantıklı|nasıl|kaç\s*cm|kullanılır\s*mı|kullanılırmı|bağlarsam|sonuç|ne\s*olur", message, re.IGNORECASE):
        return "genel_tavsiye", 0.85
        
    if _ACOUSTIC_KEYWORDS.search(message):
        return "kabin_tasarim", 0.88
        
    # Woofer + kabin/bagaj/ölçü kombosunu kabin tasarımı say
    if _WOOFER_KEYWORDS.search(message) and re.search(
        r"kabin|bagaj|ölçü|litre|hz|kutu|tasarım|sedan|araç|kasa",
        message, re.IGNORECASE
    ):
        return "kabin_tasarim", 0.80
    if _WOOFER_KEYWORDS.search(message):
        return "woofer_sorgu", 0.85
    # Belirsizse Ses Ustası devralır
    return "genel_tavsiye", 0.65


# (Bu fonksiyonlar core.interpreter'a tasindi)



def route(packet: IntakePacket) -> AgentName:
    """
    IntakePacket'e bakarak doğru ajan adını döner.
    Eksik veri varsa ses_ustasi'na döner (soru sorar).
    """
    if not packet.mark_complete() and packet.user_intent == "kabin_tasarim":
        return "ses_ustasi"     # Eksik veri → Ses Ustası tamamlatır

    dispatch: dict[IntentType, AgentName] = {
        "kabin_tasarim":   "kabin_ustasi",
        "uretim_dosyasi":  "lazer_ajani",
        "genel_tavsiye":   "ses_ustasi",
        "woofer_sorgu":    "ses_ustasi",
        "feedback_gonder": "ses_ustasi",
    }
    
    agent = dispatch.get(packet.user_intent, "ses_ustasi")
    
    # Domain bazlı özel yönlendirme (HiFi Ajanı)
    if agent == "kabin_ustasi" and packet.usage_domain in ("home_audio", "outdoor", "pro_audio"):
        agent = "hifi_ustasi"
        
    _log_route(packet, agent)
    return agent


def request_missing_fields(packet: IntakePacket) -> str:
    """
    Eksik alanlar için Türkçe soru metni üretir.
    Ses Ustası bu metni kullanıcıya iletir.
    NOT: T/S parametreleri (Fs, Qts, Vas) burada SORULMAZ — kabin hesabı aşamasında sorulur.
    """
    if not packet.missing_fields:
        return ""
    soru = []
    for field in packet.missing_fields:
        if "woofer" in field.lower() or "model" in field.lower():
            soru.append("Sürücü markası ve modeli ne? (bilmiyorsan yaklaşık güç yeter)")
        elif "t/s" in field.lower() or "fs" in field.lower():
            pass  # T/S ilk temasta SORULMAZ — yetki dışı
        elif "araç" in field.lower() or "vehicle" in field.lower():
            soru.append("Hangi araç? Sedan mı, SUV mu?")
        elif "diameter" in field.lower() or "çap" in field.lower():
            soru.append("Sürücü çapı kaç inç?")
        elif "rms" in field.lower() or "güç" in field.lower():
            soru.append("Kaç watt RMS sürücün var?")
        elif "trunk" in field.lower() or "bagaj" in field.lower():
            soru.append("Bagajda ne kadar yer ayırabiliriz, yer sıkıntısı var mı?")
        else:
            soru.append(f"'{field}' bilgisini söyler misin?")
    # Sadece en kritik 1 soruyu döndür
    return soru[0] if soru else ""


# ── Log Yardımcısı ───────────────────────────────────────────────────────────

def _log_route(packet: IntakePacket, agent: AgentName) -> None:
    logger.info(
        "[ROUTER] %s → %s | intent=%s confidence=%.2f missing=%s",
        packet.intake_id, agent,
        packet.user_intent, packet.confidence,
        packet.missing_fields or "none",
    )


# ── Quick classify (string API) ──────────────────────────────────────────────

def quick_route(message: str) -> tuple[AgentName, IntentType, float]:
    """
    Ham mesajdan doğrudan ajan adı döner.
    Tam IntakePacket olmadan hızlı yönlendirme için.
    """
    intent, conf = classify_intent(message)
    agent_map: dict[IntentType, AgentName] = {
        "kabin_tasarim":   "kabin_ustasi",
        "uretim_dosyasi":  "lazer_ajani",
        "genel_tavsiye":   "ses_ustasi",
        "woofer_sorgu":    "ses_ustasi",
        "feedback_gonder": "ses_ustasi",
    }
    
    agent = agent_map[intent]
    
    # Domain kontrolü
    from core.interpreter import _detect_usage_domain
    domain = _detect_usage_domain(message.lower())
    
    if agent == "kabin_ustasi" and domain in ("home_audio", "outdoor", "pro_audio"):
        agent = "hifi_ustasi"
        
    return agent, intent, conf
