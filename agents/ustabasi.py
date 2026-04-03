"""
agents/ustabasi.py
DD1 UstaBaşı — Konuşmacı Ajan

YETKİ SINIRI:
- Teknik truth ÜRETMEZ.
- Sadece sistemden gelen kararı (missing_fields, next_question, conflict_report vb.)
  kullanıcı diline çevirir.
- Her turda tek soru sorar.
- Karar motoru değil; anlatım katmanı.

GİRDİ:
  UstaBasiInput dataclass (bkz. aşağıda) — zorunlu olmayan alanlar None geçilebilir.

ÇIKTI:
  {
    "user_message": str,        ← kullanıcıya gönderilecek mesaj
    "optional_summary": str,    ← kısa öz (opsiyonel, UI için)
    "question_asked": str|None, ← bu turda sorulan soru (loglama için)
  }
"""
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from core.ai_adapter import AIAdapter

logger = logging.getLogger("dd1.ustabasi")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "ustabasi.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

# ── Giriş Yapısı ──────────────────────────────────────────────────────────────

@dataclass
class UstaBasiInput:
    """Sistemden bu ajana iletilen yapılandırılmış durum."""
    usage_domain: str = "car_audio"          # car_audio | home_audio | outdoor
    collected_info_summary: str = ""          # şu ana kadar toplanan bilgilerin özeti
    missing_fields: list[str] = field(default_factory=list)
    next_question_slot: Optional[str] = None  # hangi slot sorulacak (ajan bunu soru haline çevirir)
    next_question_label: Optional[str] = None # Türkçe etiket (örn: "bagaj ölçüsü")
    expert_summary: str = ""                  # teknik ajanın kısa çıktısı
    warning_level: Optional[str] = None       # None | "yellow" | "red_block"
    conflict_report: Optional[dict] = None    # seçenekalr strukturü
    selected_option_summary: Optional[str] = None
    production_ready: bool = False
    fit_validation_summary: Optional[str] = None
    vehicle_model: Optional[str] = None       # varsa araç modeli (Doblo vb.)
    vehicle_type: Optional[str] = None        # sedan | panelvan | suv...
    history: list[dict] = field(default_factory=list)
    # DD1 Dil Doktrini §9.3 — belirsiz goal sinyali için bağlam ipucu
    goal_hint: Optional[str] = None  # ambiguous_aggressive | ambiguous_visibility | ambiguous_scene | sq_sql | ambiguous_fill

# ── Domain Etiketleri ─────────────────────────────────────────────────────────

_DOMAIN_CONTEXT = {
    "car_audio":  "araç içi ses sistemi kurulumu",
    "home_audio": "ev / oda ses sistemi",
    "outdoor":    "açık hava / dış sistem",
    "pro_audio":  "profesyonel ses / sahne sistemi",
}

_WARNING_TONE = {
    "yellow":    "Bu çözüm sınırda çalışıyor, bilerek devam etmek lazım.",
    "red_block": "Bu iş bu haliyle üretime giremez.",
}

# ── Ana Sınıf ─────────────────────────────────────────────────────────────────

class UstaBasi:
    """
    DD1 UstaBaşı — sistemin konuşan yüzü.
    Teknik truth'u başka ajanlar üretir; bu ajan onu doğal Türkçeye çevirir.
    """

    def __init__(self, api_key: str | None = None):
        self._adapter = AIAdapter(api_key=api_key)
        logger.info("[USTABAŞI] Başlatıldı")

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(self, inp: UstaBasiInput) -> dict:
        """
        Yapılandırılmış girdiyi doğal Türkçe kullanıcı mesajına çevirir.
        Döner: { user_message, optional_summary, question_asked }
        """
        # Önce kural tabanlı fallback dene — AI'a gerek olmayabilir
        reply = self._fallback_speak(inp)

        question_asked = inp.next_question_label if inp.next_question_slot else None
        return {
            "user_message": reply.strip(),
            "optional_summary": self._build_summary(inp),
            "question_asked": question_asked,
        }


    # ── Fallback (AI yokken) ──────────────────────────────────────────────────

    def _fallback_speak(self, inp: UstaBasiInput) -> str:
        """AI erişimi yokken kural tabanlı usta dili üretir."""
        parts = []

        # Araç tanıma onayı
        vehicle_label = inp.vehicle_model or inp.vehicle_type
        if vehicle_label:
            parts.append(f"{vehicle_label.title()} tamam.")

        # Toplanan bilgi özeti varsa
        if inp.collected_info_summary:
            parts.append(inp.collected_info_summary)

        # Uyarı
        if inp.warning_level and inp.warning_level in _WARNING_TONE:
            parts.append(_WARNING_TONE[inp.warning_level])

        # Fit özeti
        if inp.fit_validation_summary:
            parts.append(inp.fit_validation_summary)

        # Seçenek anlatımı
        if inp.conflict_report and not inp.selected_option_summary:
            options = inp.conflict_report.get("options", [])
            if options:
                parts.append(self._narrate_options(options))

        # Mühürleme
        if inp.selected_option_summary:
            parts.append(f"Mühürlendi. {inp.selected_option_summary}")
            if inp.production_ready:
                parts.append("Üretime geçebiliriz.")
            else:
                parts.append("Üretime geçmeden önce bir şeyleri netleştirelim.")
        
        # Tek soru
        if inp.next_question_label and not inp.selected_option_summary:
            parts.append(self._format_question(inp))

        if not parts:
            return "Dinliyorum, devam et."

        return " ".join(parts)

    def _format_question(self, inp: UstaBasiInput) -> str:
        """Eksik alana göre usta tarzı soru üretir. DD1 Dil Doktrini §9.3 — goal bağlam dallanması."""
        slot = inp.next_question_slot
        vehicle = inp.vehicle_model or inp.vehicle_type or "araç"

        # ── Goal sorusu: bağlam ipucuna göre saha dili soru ─────────────────
        if slot == "goal":
            hint = inp.goal_hint
            if hint == "ambiguous_aggressive":
                return ("Sert vursun derken — altta oturan derin baskıyı mı istiyorsun, "
                        "yoksa ritimde kafana vuran kick'i mi? İkisi bambaşka yol.")
            if hint == "ambiguous_visibility":
                return ("Gelirken duyulsun derken — altta basını mı hissettirmek istiyorsun, "
                        "yoksa camdan müzik mi çıksın? İkisi ayrı yol.")
            if hint == "ambiguous_scene":
                return "Bagajı açınca çalıyorsun — dışa mı veriyor, araç içine mi?"
            if hint == "sq_sql":
                return ("SQ diyince — sessiz ortamda mı dinliyorsun genelde, "
                        "yoksa yüksek açıp da pis çıkmasın mı istiyorsun? SQL ayrı iş.")
            if hint == "ambiguous_fill":
                return "Ses dolsun derken — orta frekanslar mı dolsun, yoksa alt bas dolgunluğu mu?"
            # Varsayılan
            return "Hedef frekans yönü ne? Altta tok bas mı, ortada müzik sahnesi mi, yoksa tiz detay mı?"

        _SLOT_QUESTIONS = {
            "trunk_dims":    f"Tamam. Şimdi tek kritik şey kaldı: bagaj ölçüsünü biliyor musun? En, yükseklik, derinlik ver (cm).",
            "vehicle_type":  f"Araç kasa yapısı ne? Sedan mı, SUV mi, ticari mi?",
            "diameter":      "Sürücü çapı ne kadar? (inch veya cm olarak)",
            "brand_or_model":"Sürücü markası veya modeli?",
            "room_size":     "Oda kaç metrekare?",
            "placement":     "Kutuyu nereye koymayı düşünüyorsun? Köşe, duvar kenarı, orta?",
            "target_hz":     "Hedef tuning frekansı var mı? (Hz olarak)",
        }

        if slot in _SLOT_QUESTIONS:
            return _SLOT_QUESTIONS[slot]

        # Fallback
        label = inp.next_question_label or slot or "eksik bilgi"
        return f"Bir şeyi netleştirelim: {label}?"

    def _narrate_options(self, options: list[dict]) -> str:
        """A/B/C seçeneklerini usta diliyle anlatır."""
        lines = []
        for opt in options:
            oid = opt.get("option_id", "?")
            summary = opt.get("usta_summary", "")
            warning = opt.get("warning_level", "")
            badge = "🔴 Engel" if warning == "red_block" else ("🟡 Dikkat" if warning == "yellow" else "✅")
            lines.append(f"{oid}: {summary} [{badge}]")
        return "\n".join(lines)

    # ── State Metni (AI için) ─────────────────────────────────────────────────

    def _build_state_text(self, inp: UstaBasiInput) -> str:
        domain_ctx = _DOMAIN_CONTEXT.get(inp.usage_domain, inp.usage_domain)
        parts = [f"[Bağlam: {domain_ctx}]"]

        if inp.vehicle_model:
            parts.append(f"Araç modeli: {inp.vehicle_model}")
        elif inp.vehicle_type:
            parts.append(f"Araç tipi: {inp.vehicle_type}")

        if inp.collected_info_summary:
            parts.append(f"Toplanan bilgi: {inp.collected_info_summary}")

        if inp.missing_fields:
            parts.append(f"Eksik alanlar: {', '.join(inp.missing_fields)}")

        if inp.next_question_slot:
            parts.append(f"Sorulacak kritik alan: {inp.next_question_label or inp.next_question_slot}")

        if inp.expert_summary:
            parts.append(f"Teknik özet: {inp.expert_summary}")

        if inp.warning_level:
            parts.append(f"Uyarı seviyesi: {inp.warning_level}")

        if inp.fit_validation_summary:
            parts.append(f"Fiziksel sığma durumu: {inp.fit_validation_summary}")

        if inp.conflict_report:
            opts = inp.conflict_report.get("options", [])
            for o in opts:
                oid = o.get("option_id")
                summary = o.get("usta_summary", "")
                net_l = o.get("net_l", "")
                wl = o.get("warning_level", "ok")
                parts.append(f"Seçenek {oid}: {summary} | hacim={net_l}L | durum={wl}")

        if inp.selected_option_summary:
            parts.append(f"Kullanıcının seçimi: {inp.selected_option_summary}")
            parts.append(f"Üretime hazır: {'evet' if inp.production_ready else 'hayır'}")

        return "\n".join(parts)

    def _build_summary(self, inp: UstaBasiInput) -> str:
        vehicle = inp.vehicle_model or inp.vehicle_type or ""
        domain = _DOMAIN_CONTEXT.get(inp.usage_domain, "")
        missing_count = len(inp.missing_fields)
        if inp.selected_option_summary:
            return f"Seçim mühürlendi. Üretime hazır: {inp.production_ready}"
        if missing_count:
            return f"{vehicle} | {domain} | {missing_count} eksik alan"
        return f"{vehicle} | {domain} | Tüm bilgiler tamam"


# ── Modül-düzey kolaylık fonksiyonu ──────────────────────────────────────────

def speak_from_state(state: dict, api_key: str | None = None) -> dict:
    """
    chat_service veya herhangi bir orchestrator tarafından
    tek satırda çağrılabilecek kolaylık fonksiyonu.

    Beklenen state anahtarları (hepsi opsiyonel):
      usage_domain, collected_info_summary, missing_fields,
      next_question_slot, next_question_label, expert_summary,
      warning_level, conflict_report, selected_option_summary,
      production_ready, fit_validation_summary,
      vehicle_model, vehicle_type, history
    """
    inp = UstaBasiInput(
        usage_domain=state.get("usage_domain", "car_audio"),
        collected_info_summary=state.get("collected_info_summary", ""),
        missing_fields=state.get("missing_fields", []),
        next_question_slot=state.get("next_question_slot"),
        next_question_label=state.get("next_question_label"),
        expert_summary=state.get("expert_summary", ""),
        warning_level=state.get("warning_level"),
        conflict_report=state.get("conflict_report"),
        selected_option_summary=state.get("selected_option_summary"),
        production_ready=state.get("production_ready", False),
        fit_validation_summary=state.get("fit_validation_summary"),
        vehicle_model=state.get("vehicle_model"),
        vehicle_type=state.get("vehicle_type"),
        history=state.get("history", []),
        goal_hint=state.get("goal_hint"),  # DD1 Dil Doktrini §9.3
    )
    agent = UstaBasi(api_key=api_key)
    return agent.speak(inp)
