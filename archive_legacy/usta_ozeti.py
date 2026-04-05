"""
core/usta_ozeti.py
DD1 Usta Özeti Motoru

GÖREV:
  ConflictOption verileri → Ses Ustası diliyle dinamik Türkçe özet.
  AIAdapter üzerinden LLM kullanır; API yoksa template fallback çalışır.

KURAL:
  - Hesap yapmaz — verileri anlatır.
  - Samimi ama profesyonel usta dili.
  - Her seçenek için bağımsız özet.
  - Kıyaslama için A vs B karşılaştırma özeti.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("dd1.usta_ozeti")

# ── Offline Şablon Üreteci ─────────────────────────────────────────────────────

_STRATEGY_TEMPLATES: dict[str, str] = {
    "keep_outer_dims_reduce_port": (
        "Bu seçenekte dış ölçüleri aynen korudum. Port boyutlarını biraz kısalttım; "
        "tuning ({tuning_hz:.0f}Hz) hedeften {delta:.1f}Hz kayıyor ama kutu milimi milimetresine yerlerine oturuyor."
    ),
    "invert_driver_mounting": (
        "Sürücüyü ters monte edersek ~{gain_l:.1f}L iç hacim kazanıyoruz. "
        "Fark kulağa gelmez; ama bagajda son nefese kadar her santimetreyi kullanıyoruz."
    ),
    "optimize_bracing_reduce_displacement": (
        "Takoz geometrisini optimize ederek {gain_l:.1f}L kazandım. "
        "Yapısal sağlamlık korunuyor, net hacim hedefine yaklaşıyoruz."
    ),
    "thin_material_15mm": (
        "18mm MDF yerine 15mm huş kontraplak kullanırsak her panelden 3mm kazan kazanıyorsun. "
        "Toplam +{gain_l:.2f}L iç hacim. Parmak birleşim hesabı sıfırdan yapıldı, üretime hazır."
    ),
    "shorten_port_length": (
        "Portu {old_len:.0f}mm'den {new_len:.0f}mm'ye kısalttım. "
        "Tuning hedefi ({tuning_hz:.0f}Hz) tutturuluyor, port artık iç duvara rahat sığıyor."
    ),
    "switch_to_aero_port": (
        "Slot port yerine aerodinamik aero port öneriyorum. "
        "Aynı tuning'i daha az yükseklikte elde ediyoruz — bu sürücü boyutu için çok uygun."
    ),
    "external_port_mounting": (
        "Port'u dışarı taşırsak kabin içi tamamen temizleniyor. "
        "Ek mekanik iş var ama akustik ve bagaj kısıtlamaları aynı anda çözülüyor."
    ),
    "reduce_outer_depth": (
        "Derinliği {diff:.0f}mm kısalttım. "
        "Bagaj yerleşimi için kritik, tuning'de {tune_diff:.0f}Hz kırpıyoruz — kabul edilebilir."
    ),
    "reduce_outer_height": (
        "Yüksekliği {diff:.0f}mm düşürdüm. "
        "Bagajın düz zemine oturacak, tuning {tune_diff:.0f}Hz sapmayı kucaklıyor."
    ),
    "compromise_balance": (
        "İkisi arasında dengeli köprü bu seçenek. "
        "Dış ölçü {w:.0f}x{h:.0f}x{d:.0f}mm, net {net_l:.1f}L, tuning {tuning_hz:.0f}Hz. "
        "Hem bagaj hem akustik için makul orta yol."
    ),
}

_DEFAULT_TEMPLATE = (
    "Seçenek {option_id}: {net_l:.1f}L net hacim, {tuning_hz:.0f}Hz tuning. "
    "Dış ölçüler {w:.0f}x{h:.0f}x{d:.0f}mm. "
    "Durum: {'Üretime hazır' if production_ready else 'Onay bekliyor'}."
)


def _template_summary(option_dict: dict) -> str:
    """LLM yokken şablon tabanlı özet üretir."""
    strategy = option_dict.get("strategy", "")
    dims = option_dict.get("outer_dimensions_mm", [0, 0, 0])
    w, h, d = (dims + [0, 0, 0])[:3]
    net_l  = option_dict.get("estimated_final_net_l", 0.0)
    tuning = option_dict.get("estimated_final_tuning_hz", 0.0)
    delta  = option_dict.get("acoustic_delta_pct", 0.0)
    pr     = option_dict.get("production_ready", False)
    mr     = option_dict.get("material_recalculation") or {}

    tmpl = _STRATEGY_TEMPLATES.get(strategy)
    if tmpl:
        try:
            return tmpl.format(
                option_id=option_dict.get("option_id", "?"),
                net_l=net_l, tuning_hz=tuning, delta=delta,
                w=w, h=h, d=d,
                gain_l=mr.get("volume_gain_l", 0.0),
                old_len=mr.get("old_port_length_mm", 400),
                new_len=mr.get("new_port_length_mm", 300),
                diff=abs(mr.get("outer_dim_change_mm", 20.0)),
                tune_diff=abs(delta * tuning / 100),
                production_ready=pr,
            )
        except (KeyError, Exception):
            pass

    # Genel fallback
    return (
        f"Seçenek {option_dict.get('option_id','?')}: "
        f"{net_l:.1f}L net hacim, {tuning:.0f}Hz tuning, "
        f"dış ölçü {w:.0f}x{h:.0f}x{d:.0f}mm. "
        f"{'Üretime hazır.' if pr else 'Onay bekliyor.'}"
    )


# ── UstaOzeti Sınıfı ──────────────────────────────────────────────────────────

class UstaOzeti:
    """
    ConflictOption verilerini Ses Ustası diliyle anlat.
    generate_option_summary()    → tek seçenek için özet
    generate_comparison_summary() → A vs B için paragraf
    """

    def __init__(self, api_key: Optional[str] = None, use_ai: bool = True):
        self._use_ai = use_ai
        self._adapter = None
        if use_ai:
            try:
                from core.ai_adapter import AIAdapter
                self._adapter = AIAdapter(api_key=api_key)
            except Exception as exc:
                logger.warning(
                    "[USTA OZETI] AIAdapter başlatılamadı, template mod aktif: %s", exc
                )
                self._use_ai = False

    # ── Tek Seçenek ───────────────────────────────────────────────────────────

    def generate_option_summary(
        self,
        option_dict: dict,
        mode: str = "fixed_acoustic",
        context: str = "",
    ) -> str:
        """
        Seçenek kartı için usta dili özet.
        use_ai=True ve adapter hazırsa LLM kullanır, yoksa template döner.
        """
        if self._use_ai and self._adapter:
            return self._ai_option_summary(option_dict, mode, context)
        return _template_summary(option_dict)

    def _ai_option_summary(self, opt: dict, mode: str, context: str) -> str:
        dims = opt.get("outer_dimensions_mm", [0, 0, 0])
        w, h, d = (dims + [0, 0, 0])[:3]
        prompt = (
            f"Bir ses ustası olarak bu tasarım seçeneği için kısa (2-3 cümle) "
            f"samimi Türkçe özet yaz. Hesap yapma, yorumla.\n\n"
            f"Seçenek: {opt.get('option_id','?')}\n"
            f"Strateji: {opt.get('strategy','')}\n"
            f"Net hacim: {opt.get('estimated_final_net_l',0):.2f}L\n"
            f"Tuning: {opt.get('estimated_final_tuning_hz',0):.0f}Hz\n"
            f"Dış ölçü: {w:.0f}x{h:.0f}x{d:.0f}mm\n"
            f"Delta: %{opt.get('acoustic_delta_pct',0):.1f}\n"
            f"Üretime hazır: {'Evet' if opt.get('production_ready') else 'Hayır'}\n"
            f"Mod: {mode}\n"
            f"Ek bağlam: {context}"
        )
        system = (
            "Sen DD1 Ses Ustası'nın sesini taşıyan akıllı bir özet motorusun. "
            "Usta gibi konuş — samimi, pratik, saha odaklı. "
            "Akademik veya soğuk bir dil kullanma. "
            "2-3 cümle yeterli."
        )
        try:
            resp = self._adapter.generate(prompt, system_prompt=system)
            if resp.ok and resp.text:
                return resp.text
        except Exception as exc:
            logger.warning("[USTA OZETI] AI çağrı hatası: %s", exc)
        return _template_summary(opt)

    # ── Karşılaştırma ─────────────────────────────────────────────────────────

    def generate_comparison_summary(
        self,
        opt_a: dict,
        opt_b: dict,
        mode: str = "fixed_acoustic",
    ) -> str:
        """A vs B için kısa karşılaştırma paragrafı."""
        if self._use_ai and self._adapter:
            return self._ai_comparison(opt_a, opt_b, mode)
        return self._template_comparison(opt_a, opt_b)

    def _ai_comparison(self, opt_a: dict, opt_b: dict, mode: str) -> str:
        dims_a = opt_a.get("outer_dimensions_mm", [0, 0, 0])
        dims_b = opt_b.get("outer_dimensions_mm", [0, 0, 0])
        prompt = (
            f"Bir ses ustası olarak iki tasarım arasındaki kritik farkı "
            f"2-3 cümleyle anlat. Sayısal veriler var:\n\n"
            f"Seçenek A ({opt_a.get('option_id','A')}): "
            f"{opt_a.get('estimated_final_net_l',0):.2f}L, "
            f"{opt_a.get('estimated_final_tuning_hz',0):.0f}Hz, "
            f"{'Hazır' if opt_a.get('production_ready') else 'Onay Bekliyor'}\n"
            f"Seçenek B ({opt_b.get('option_id','B')}): "
            f"{opt_b.get('estimated_final_net_l',0):.2f}L, "
            f"{opt_b.get('estimated_final_tuning_hz',0):.0f}Hz, "
            f"{'Hazır' if opt_b.get('production_ready') else 'Onay Bekliyor'}\n"
            f"Mod: {mode}"
        )
        system = (
            "Sen DD1 Ses Ustası'sın. Saha ustası gibi kısa ve net konuş. "
            "Hangisi daha iyi derken net bir görüş bildir."
        )
        try:
            resp = self._adapter.generate(prompt, system_prompt=system)
            if resp.ok and resp.text:
                return resp.text
        except Exception as exc:
            logger.warning("[USTA OZETI] AI karşılaştırma hatası: %s", exc)
        return self._template_comparison(opt_a, opt_b)

    def _template_comparison(self, opt_a: dict, opt_b: dict) -> str:
        """LLM yokken şablon karşılaştırma."""
        id_a = opt_a.get("option_id", "A")
        id_b = opt_b.get("option_id", "B")
        net_a = opt_a.get("estimated_final_net_l", 0.0)
        net_b = opt_b.get("estimated_final_net_l", 0.0)
        tune_a = opt_a.get("estimated_final_tuning_hz", 0.0)
        tune_b = opt_b.get("estimated_final_tuning_hz", 0.0)
        pr_a = opt_a.get("production_ready", False)
        pr_b = opt_b.get("production_ready", False)

        winner = id_a if pr_a and not pr_b else (id_b if pr_b and not pr_a else "İkisi de")
        return (
            f"Seçenek {id_a} için {net_a:.1f}L ve {tune_a:.0f}Hz, "
            f"Seçenek {id_b} için {net_b:.1f}L ve {tune_b:.0f}Hz. "
            f"Net hacim farkı {abs(net_a - net_b):.2f}L, "
            f"tuning farkı {abs(tune_a - tune_b):.0f}Hz. "
            f"{'Üretime hazır: ' + winner + '.' if winner != 'İkisi de' else 'Her iki seçenek üretim onayı bekliyor.'}"
        )
