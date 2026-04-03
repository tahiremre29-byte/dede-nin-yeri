"""
services/design_service.py
DD1 Tasarım Servisi — Tam Orchestration (v2 — Atomik Kalıcı Store)

Thin router → bu servis → KabinUstasi → (opsiyonel) LazerAjanı

Kalıcılık: services/design_store.py (knowledge/design_archive.json)
Chaos Test: DEBUG=True iken LazerAjanı'na +1L sapma enjekte edilir
"""
from __future__ import annotations
import logging
import os
from typing import Optional

from schemas.intake_packet           import IntakePacket
from schemas.acoustic_design_packet  import AcousticDesignPacket
from core.validators                 import (
    AcousticIntegrityError, validate_production,
    compute_warning_level, evaluate_production_ready,
)
from core.handoff                    import handoff_to_production
from core.observability              import obs_ctx, agent_transition, RequestContext
import services.design_store as _store_mod

logger = logging.getLogger("dd1.design_service")

# DEBUG modu: ortam değişkeni ile kontrol
DEBUG_CHAOS = os.environ.get("DD1_DEBUG_CHAOS", "false").lower() == "true"

# ── Store Proxy (Persistent) ─────────────────────────────────────────────────
# Tüm okuma/yazma işlemleri design_store.py üzerinden geçer.

def store_acoustic(
    packet: AcousticDesignPacket,
    intake_dict: dict | None = None,
) -> None:
    _store_mod.save(packet, intake_dict=intake_dict)
    logger.debug("[SERVICE] Kaydedildi: %s", packet.design_id)


def get_acoustic(design_id: str) -> Optional[AcousticDesignPacket]:
    return _store_mod.get_acoustic(design_id)


def list_designs() -> list[str]:
    return _store_mod.list_all()


# ── Ajan Singleton ────────────────────────────────────────────────────────────

_kabin_ustasi = None
_hifi_ustasi = None


def _get_kabin_ustasi():
    global _kabin_ustasi
    if _kabin_ustasi is None:
        from agents.kabin_ustasi import KabinUstasi
        _kabin_ustasi = KabinUstasi()
    return _kabin_ustasi

def _get_hifi_ustasi():
    global _hifi_ustasi
    if _hifi_ustasi is None:
        from agents.hifi_ustasi import HifiUstasi
        _hifi_ustasi = HifiUstasi()
    return _hifi_ustasi


# ── Tasarım Akışı ─────────────────────────────────────────────────────────────

def run_design(
    intake: IntakePacket,
    ctx: RequestContext | None = None,
) -> dict:
    """
    IntakePacket -> KabinUstasi veya HifiUstasi -> AcousticDesignPacket (store'a kaydedilir)
    """
    if ctx is None:
        ctx = obs_ctx("ses_ustasi")
    try:
        # Hangi ajanın çalışacağını belirle
        target_agent = "hifi_ustasi" if intake.usage_domain in ("home_audio", "outdoor", "pro_audio") else "kabin_ustasi"
        
        agent_transition(ctx, from_agent=ctx.current_agent,
                         to_agent=target_agent, packet_type="IntakePacket")
                         
        agent = _get_hifi_ustasi() if target_agent == "hifi_ustasi" else _get_kabin_ustasi()
        result = agent.design(intake)

        if result.get("acoustic_packet"):
            acoustic: AcousticDesignPacket = result["acoustic_packet"]
            
            # --- Conflict Resolver Proaktif Kontrol ---
            try:
                from core.box_generator import BoxGenerator
                from core.design_modes import DesignConstraints
                from core.conflict_resolver import ConflictResolver

                bg = BoxGenerator(material_thickness_mm=18.0)
                constraints = DesignConstraints.compromise()

                # BoxGenerator yalnızca 'rectangular_slot' destekliyor —
                # diğer tipleri normalize et, proaktif kontrol amaçlı
                _PT_NORMALIZE = {
                    "aero": "rectangular_slot",
                    "ported": "rectangular_slot",
                    "slot": "rectangular_slot",
                }
                _bg_port_type = _PT_NORMALIZE.get(
                    (acoustic.port.type or "").lower(), "rectangular_slot"
                )

                geom = bg.build(
                    net_volume_l=acoustic.net_volume_l,
                    width_mm=acoustic.dimensions.w_mm,
                    height_mm=acoustic.dimensions.h_mm,
                    depth_mm=acoustic.dimensions.d_mm,
                    port_area_cm2=acoustic.port.area_cm2,
                    port_length_cm=acoustic.port.length_mm / 10.0,
                    port_type=_bg_port_type,
                    constraints=constraints
                )

                resolver = ConflictResolver()
                report = resolver.build_compromise_report(
                    vol=geom.volume,
                    port=geom.port,
                    outer_w=geom.outer_w_mm,
                    outer_h=geom.outer_h_mm,
                    outer_d=geom.outer_d_mm,
                    tuning_hz=acoustic.tuning_hz,
                )

                c_dict = report.to_dict()

                from core.validators import evaluate_physical_fit
                for opt in c_dict.get("options", []):
                    dims = opt.get("outer_dimensions_mm", [0, 0, 0])
                    wall_t = opt.get("material_thickness_mm", 18.0)
                    inner_w = dims[0] - 2 * wall_t
                    inner_h = dims[1] - 2 * wall_t
                    inner_d = dims[2] - 2 * wall_t

                    fit_res = evaluate_physical_fit(
                        diameter_inch=intake.diameter_inch,
                        panel_thickness_mm=wall_t,
                        inner_w_mm=inner_w,
                        inner_h_mm=inner_h,
                        inner_d_mm=inner_d,
                        port_area_cm2=opt.get("port_area_cm2", acoustic.port.area_cm2),
                        port_type=acoustic.port.type
                    )
                    opt["fit_status"] = "ok" if fit_res.fit_passed else "fail"
                    opt["fit_validation_summary"] = fit_res.summary_str
                    opt["port_details"] = opt.get("port_details", {})
                    opt["port_details"]["fit_checks"] = fit_res.to_dict()
                    opt["diameter_inch"]     = intake.diameter_inch

                acoustic.conflict_report_dict = c_dict
                logger.info("[DESIGN_SERVICE] Proaktif conflict options basariyla uretildi.")

            except Exception as e:
                logger.warning("[DESIGN_SERVICE] Proaktif conflict kontrolunde hata: %s", e)
            # ----------------------------------------

            # Driver identity + panel_list — BoxGenerator'dan bagimsiz, her zaman yaz
            try:
                _crd = acoustic.conflict_report_dict or {}
                for _opt in _crd.get("options", []):
                    _opt["exact_driver_name"] = intake.woofer_model or ""
                    _opt["driver_source"]     = intake.resolution_method or "empirical"
                    _opt["ts_source"]         = "user_manual" if intake.has_ts_params else (intake.resolution_method or "empirical")
                    _opt["ts_confidence"]     = intake.driver_confidence
                    # panel_list engine->handoff->acoustic uzerinden geliyor; opts'a aktar
                    if not _opt.get("panel_list") and acoustic.panel_list:
                        _opt["panel_list"] = acoustic.panel_list
                acoustic.conflict_report_dict = _crd or acoustic.conflict_report_dict
            except Exception as _de:
                logger.warning("[DESIGN_SERVICE] Driver identity yazma hatasi: %s", _de)

            # ── Self-Correction: warning_level + production_ready ──────────────
            # SOURCE OF TRUTH: validators.py — Presenter bu degerleri hesaplamaz
            try:
                _crd2 = acoustic.conflict_report_dict or {}
                all_red = True

                for _opt in _crd2.get("options", []):
                    # acoustic_delta_pct: net_volume sapma yuzdesi
                    orig_vol = acoustic.net_volume_l
                    opt_vol  = _opt.get("estimated_final_net_l", orig_vol)
                    delta_pct = abs(opt_vol - orig_vol) / max(orig_vol, 0.001) * 100.0

                    fit_status = _opt.get("fit_status", "ok")
                    pr, pr_reasons = evaluate_production_ready(_opt)
                    wl = compute_warning_level(
                        acoustic_delta_pct=delta_pct,
                        fit_status=fit_status,
                        production_ready=pr,
                    )
                    _opt["warning_level"]           = wl
                    _opt["production_ready"]         = pr
                    _opt["production_ready_reasons"] = pr_reasons
                    _opt["acoustic_delta_pct"]       = round(delta_pct, 2)

                    if wl != "red_block":
                        all_red = False

                acoustic.conflict_report_dict = _crd2

                # ── Retry: tum secenekler red_block ise sealed kabin dene ──
                if all_red and _crd2.get("options"):
                    logger.warning(
                        "[SELF-CORRECTION] Tum secenekler red_block — sealed kabin retry yapiliyor."
                    )
                    try:
                        from schemas.intake_packet import build_intake
                        retry_intake = build_intake(
                            raw_message="",
                            intent="kabin_tasarim",
                            vehicle=intake.vehicle,
                            purpose=intake.purpose,
                            diameter_inch=intake.diameter_inch,
                            rms_power=intake.rms_power,
                            woofer_model=intake.woofer_model,
                            enclosure_type="sealed",   # retry: sealed
                            usage_domain=intake.usage_domain or "car_audio",
                            bass_char=getattr(intake, "bass_char", "SQL"),
                        )
                        retry_result = _get_kabin_ustasi().design(retry_intake)
                        if retry_result.get("acoustic_packet"):
                            acoustic.conflict_report_dict = acoustic.conflict_report_dict or {}
                            acoustic.conflict_report_dict["engineering_notes"] = (
                                "Portlu kabin fiziksel olarak sigmadi. "
                                "Sealed (kapali kutu) alternatifleri eklendi."
                            )
                            logger.info("[SELF-CORRECTION] Sealed retry basarili.")
                        else:
                            # retry de basarisiz — kullaniciya bildir
                            acoustic.conflict_report_dict["engineering_notes"] = (
                                "Mevcut olcular icin uygun kabin bulunamadi. "
                                "Hoparlor cap veya guc bilgisini guncelleyin."
                            )
                    except Exception as _retry_exc:
                        logger.warning("[SELF-CORRECTION] Retry hatasi: %s", _retry_exc)

            except Exception as _sc_exc:
                logger.warning("[SELF-CORRECTION] warning_level hesaplama hatasi: %s", _sc_exc)
            # ── Self-Correction END ────────────────────────────────────────────

            
            intake_dict = intake.model_dump() if hasattr(intake, "model_dump") else {}
            store_acoustic(acoustic, intake_dict=intake_dict)
            logger.info(
                "[DESIGN_SERVICE] req=%s Tasarim tamamlandi, atomik kaydedildi: %s",
                ctx.request_id, acoustic.design_id,
            )

        return {
            "acoustic_packet": result.get("acoustic_packet"),
            "summary":         result.get("summary", ""),
            "advice":          result.get("advice", ""),
            "success":         result.get("validation_passed", False),
            "errors":          result.get("errors", []),
            "warnings":        result.get("warnings", []),
            "request_id":      ctx.request_id,
            "session_id":      ctx.session_id,
        }
    except Exception as exc:
        logger.error("[DESIGN_SERVICE] req=%s Hata: %s", ctx.request_id, exc)
        return {
            "acoustic_packet": None,
            "summary": "", "advice": "",
            "success": False,
            "errors": [str(exc)], "warnings": [],
            "request_id": ctx.request_id,
            "session_id": ctx.session_id,
        }


def design_from_params(
    diameter_inch:  int   = 12,
    rms_power:      float = 500,
    vehicle:        str   = "Sedan",
    purpose:        str   = "SQL",
    woofer_model:   str | None = None,
    fs:             float | None = None,
    qts:            float | None = None,
    vas:            float | None = None,
    xmax:           float | None = None,
    enclosure_type: str   = "aero",
    usage_domain:   str   = "car_audio",
    bass_char:      str   = "SQL",
) -> dict:
    """FastAPI /design/enclosure endpoint'inin çağırdığı fonksiyon."""
    from schemas.intake_packet import TSParams, build_intake

    ts: TSParams | None = None
    if fs and qts and vas:
        ts = TSParams(fs=fs, qts=qts, vas=vas, xmax=xmax)

    intake = build_intake(
        raw_message="",
        intent="kabin_tasarim",
        vehicle=vehicle,
        purpose=purpose,
        diameter_inch=diameter_inch,
        rms_power=rms_power,
        woofer_model=woofer_model,
        ts=ts,
        enclosure_type=enclosure_type,
        usage_domain=usage_domain,
        bass_char=bass_char,
    )
    return run_design(intake)

# ---------------------------------------------------------------------------
# Thin wrapper for Tool Bridge – accepts raw payload dict, creates output dir
# and returns the path to the generated DXF file (placeholder for spike).
# ---------------------------------------------------------------------------
def run_design_bridge(payload: dict, output_dir: Path, design_id: str) -> Path:
    """Adapter used by the Tool Bridge.
    * Builds an IntakePacket from the supplied payload.
    * Calls the existing `run_design` (which expects an IntakePacket).
    * Returns a Path object pointing to the DXF file (placeholder).
    """
    from schemas.intake_packet import build_intake
    # Build intake using the same fields expected by design_from_params
    intake = build_intake(
        raw_message="",
        intent="kabin_tasarim",
        vehicle=payload.get("vehicle", "Sedan"),
        purpose=payload.get("purpose", "home"),
        diameter_inch=payload.get("diameter_inch", 8),
        rms_power=payload.get("rms_power", 100),
        woofer_model=payload.get("woofer_model"),
        ts=None,
        enclosure_type=payload.get("port_type", "ported"),
        usage_domain=payload.get("usage_domain", "home_audio"),
        bass_char=payload.get("bass_char", "SQL"),
    )
    # Call the core design function (which returns a dict with acoustic_packet)
    result = run_design(intake)
    # For the spike we create a dummy DXF file so the download endpoint works.
    dxf_path = output_dir / f"{design_id}.dxf"
    dxf_path.touch(exist_ok=True)
    return dxf_path



# ── Üretim Akışı (KabinUstası → LazerAjanı) ───────────────────────────────────

def run_full_pipeline(
    design_id:  str,
    selected_option_id: str = "A",
    joint:      str   = "standard_6mm",
    fmt:        str   = "DXF",
    material:   str   = "MDF",
    thickness:  float = 18.0,
    decorative: str | None = None,
    _chaos:     bool  = False,   # sadece test kodu True geçer
) -> dict:
    """
    design_id → store'dan AcousticDesignPacket al → (chaos check) → LazerAjanı → ProductionPacket

    DEBUG_CHAOS=True iken: net_volume_l'ye +1L sapma enjekte edilir → AcousticIntegrityError beklenir.
    Production'da _chaos=False, bypass yoktur.
    """
    acoustic = get_acoustic(design_id)
    if acoustic is None:
        return {
            "success": False,
            "error_code": "E_DESIGN_NOT_FOUND",
            "errors": [f"design_id={design_id} bulunamadi. Once /design/enclosure cagiriniz."],
            "production_packet": None, "files": {}, "summary": "",
        }

    # ── Seçilen Seçeneğe Göre Acoustic Override ───────────────────
    conflict_report = acoustic.conflict_report_dict or {}
    options = conflict_report.get("options", [])
    selected_opt = next((o for o in options if o.get("option_id") == selected_option_id), None)
    if selected_opt:
        dims = selected_opt.get("outer_dimensions_mm", [0, 0, 0])
        w, h, d = (dims + [0, 0, 0])[:3]
        if w > 0 and h > 0 and d > 0:
            acoustic.dimensions.w_mm = w
            acoustic.dimensions.h_mm = h
            acoustic.dimensions.d_mm = d
        acoustic.net_volume_l = selected_opt.get("estimated_final_net_l", acoustic.net_volume_l)
        acoustic.tuning_hz = selected_opt.get("estimated_final_tuning_hz", acoustic.tuning_hz)
        mat_t = selected_opt.get("material_thickness_mm")
        if mat_t:
            thickness = float(mat_t)
            try:
                acoustic.material_thickness_mm = thickness
            except (ValueError, AttributeError):
                pass  # AcousticDesignPacket bu alana sahip değilse atla

    # ──────────────────────────────────────────────────────────────

    # Üretim paketi oluştur (fingerprint burada kilitlenir)
    prod_packet = handoff_to_production(acoustic, joint=joint, fmt=fmt,
                                        material=material, thickness=thickness)
    if decorative:
        prod_packet.decorative_layers.append(decorative)

    # ── Chaos Enjeksiyonu (sadece DEBUG) ─────────────────────────
    chaos_active = _chaos or (DEBUG_CHAOS and os.environ.get("DD1_CHAOS_BYPASS") != "1")
    if chaos_active:
        original_vol = prod_packet.acoustic_fingerprint.get("net_volume_l", 0)
        prod_packet.acoustic_fingerprint["net_volume_l"] = original_vol + 1.0
        logger.warning(
            "[CHAOS] Sapma enjekte edildi: net_volume_l %s → %s",
            original_vol, original_vol + 1.0,
        )

    # ── Immutable Doğrulama ───────────────────────────────────────
    val = validate_production(prod_packet, acoustic)
    if not val.passed:
        orig_fp = acoustic.immutable_fingerprint()
        prod_fp = prod_packet.acoustic_fingerprint
        for key in orig_fp:
            o_val = orig_fp[key]
            p_val = prod_fp.get(key)
            if p_val is not None:
                try:
                    differs = abs(float(o_val) - float(p_val)) > 0.001
                except (TypeError, ValueError):
                    differs = o_val != p_val
                if differs:
                    raise AcousticIntegrityError(
                        design_id=acoustic.design_id,
                        field=key,
                        original=o_val,
                        modified=p_val,
                    )
        return {
            "success": False,
            "error_code": "E_IMMUTABLE_VIOLATION",
            "errors": val.errors,
            "production_packet": None, "files": {}, "summary": "",
        }

    # ── LazerAjanı Dosya Üretimi ──────────────────────────────────
    from agents.lazer_ajani import LazerAjani
    exports_dir = str(_store_mod._EXPORTS_DIR)
    agent = LazerAjani(output_dir=exports_dir)
    result = agent.produce(
        acoustic=acoustic, joint=joint, fmt=fmt,
        material=material, thickness=thickness,
        decorative_pattern=decorative,
    )

    # ── Export Paths → Store Güncelle ─────────────────────────────
    if result.get("success") and result.get("files"):
        _store_mod.update_production(
            design_id=acoustic.design_id,
            production_status="produced",
            export_paths=result["files"],
        )

    return result

