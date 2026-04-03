"""
DD1 Platform — Kabin Tasarım Router  (Thin v4 — Backward-Compat Wrapper)

GERIYE UYUMLULUK:
  POST /design/enclosure        → design_service.design_from_params() → eski JSON formatı
  POST /design/produce          → design_service.run_full_pipeline() → ProductionPacket
  GET  /design/download/{id}    → exports/ DXF/STL (aktif download endpoint)
  GET  /design/{id}/files/dxf   → exports/ DXF (premium)
  GET  /design/{id}/files/stl   → exports/ STL
  GET  /design/{id}/info        → arşiv kaydını döner
  GET  /design/store/stats      → arşiv istatistikleri
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional
from pathlib import Path

from services.design_service import design_from_params, run_full_pipeline
import services.design_store as _store

logger = logging.getLogger("dd1.routers.design")

router = APIRouter(prefix="/design", tags=["Kabin Tasarim"])

_EXPORTS = Path(__file__).parent.parent / "exports"
_OUTPUT  = Path(__file__).parent.parent / "output"


def _is_premium(x_api_key: str | None) -> bool:
    return x_api_key == os.environ.get("DD1_PREMIUM_KEY", "premium-dev")


# ── İstek Modelleri ───────────────────────────────────────────────────────────

class EnclosureRequest(BaseModel):
    """Eski istemcilerle uyumlu istek şeması — tüm alanlar opsiyonel."""
    diameter_inch:  int   = 12
    rms_power:      float = 500
    vehicle:        str   = "Sedan"
    purpose:        str   = "SQL"
    woofer_model:   Optional[str]   = None
    fs:             Optional[float] = None
    qts:            Optional[float] = None
    vas:            Optional[float] = None
    xmax:           Optional[float] = None
    enclosure_type: str   = "aero"
    usage_domain:   str   = "car_audio"   # car_audio | outdoor | pro_audio | home_audio
    bass_char:      str   = "SQL"          # SQL | SPL | patlamalı | tok | günlük


class ProduceRequest(BaseModel):
    design_id:    str
    selected_option_id: str = "A"
    joint_profile: str   = "standard_6mm"
    export_format: str   = "DXF"
    material:      str   = "MDF"
    thickness_mm:  float = 18.0
    decorative:    Optional[str] = None


# ── Helper: Eski JSON Formatına Çevir ─────────────────────────────────────────

def _to_legacy_format(acoustic, success: bool, warnings: list,
                       advice: str, x_api_key: str | None) -> dict:
    """
    AcousticDesignPacket → eski /design/enclosure JSON formt.
    Eski frontend/EXE beklentilerini karşılar.
    """
    base = f"/design/{acoustic.design_id}/files"
    premium = _is_premium(x_api_key)
    return {
        # ── Eski alanlar (geriye uyumluluk) ───────────────────────
        "design_id":         acoustic.design_id,
        "mode":              acoustic.mode,
        "net_volume_l":      acoustic.net_volume_l,
        "tuning_hz":         acoustic.tuning_hz,
        "port":              {
            "area_cm2":   acoustic.port_area_cm2,
            "length_cm":  acoustic.port_length_cm,
            "count":      acoustic.port.count if acoustic.port else 1,
        },
        "dimensions":        acoustic.dimensions.model_dump(),
        "f3_hz":             acoustic.f3_hz,
        "port_velocity_ms":  acoustic.port_velocity_ms,
        "peak_spl_db":       acoustic.peak_spl_db,
        "validation_passed": success,
        "acoustic_advice":   acoustic.acoustic_notes,
        "expert_comment":    advice,
        "notes":             warnings,
        "panel_list":        acoustic.panel_list,
        "dxf_url":           f"{base}/dxf" if premium else None,
        "stl_url":           f"{base}/stl",
        # ── Yeni alanlar (güvenlik + izleme) ──────────────────────
        "packet_hash":       acoustic.packet_hash,
        "enclosure_type":    acoustic.enclosure_type,
    }


# ── POST /design/enclosure (Backward-Compat Wrapper) ─────────────────────────

@router.post("/enclosure")
def create_enclosure(req: EnclosureRequest,
                     x_api_key: str | None = Header(None)):
    """
    Eski istemcilerle uyumlu tasarım endpoint'i.
    İçi boşaltıldı → design_service.design_from_params() üzerinden KabinUstası.
    """
    result = design_from_params(
        diameter_inch=req.diameter_inch,
        rms_power=req.rms_power,
        vehicle=req.vehicle,
        purpose=req.purpose,
        woofer_model=req.woofer_model,
        fs=req.fs,
        qts=req.qts,
        vas=req.vas,
        xmax=req.xmax,
        enclosure_type=req.enclosure_type,
        usage_domain=req.usage_domain,
        bass_char=req.bass_char,
    )

    if not result["success"]:
        raise HTTPException(400, detail={
            "errors": result["errors"],
            "warnings": result.get("warnings", []),
        })

    return _to_legacy_format(
        acoustic=result["acoustic_packet"],
        success=result["success"],
        warnings=result.get("warnings", []),
        advice=result.get("advice", ""),
        x_api_key=x_api_key,
    )


# ── POST /design/produce ──────────────────────────────────────────────────────

@router.post("/produce")
def produce_files(req: ProduceRequest,
                  x_api_key: str | None = Header(None)):
    """
    Mevcut design_id için DXF/STL üretimi.
    immutable check yapılır; sapma → 422 + AcousticIntegrityError detayı.
    """
    logger.info("[PRODUCE_ENDPOINT] UI Üretim İsteği: design_id=%s | selected_option=%s", req.design_id, req.selected_option_id)
    try:
        result = run_full_pipeline(
            design_id=req.design_id,
            selected_option_id=req.selected_option_id,
            joint=req.joint_profile,
            fmt=req.export_format,
            material=req.material,
            thickness=req.thickness_mm,
            decorative=req.decorative,
        )
    except Exception as exc:
        # AcousticIntegrityError ve diğer hatalar
        err_type = type(exc).__name__
        logger.error("[PRODUCE] %s: %s", err_type, exc)
        raise HTTPException(422, detail={
            "error_code": err_type,
            "message": str(exc),
        })

    if not result["success"]:
        detail_dict = {
            "error_code": result.get("error_code", "E_PRODUCE_FAILED"),
            "errors": result["errors"],
        }
        if "conflict_report" in result:
            detail_dict["conflict_report"] = result["conflict_report"]
        raise HTTPException(400, detail=detail_dict)

    return {
        "design_id":      req.design_id,
        "success":        True,
        "files":          result.get("files", {}),
        "production_id":  result.get("production_packet").production_id
                          if result.get("production_packet") else None,
        "summary":        result.get("summary", ""),
    }


# ── POST /design/validate ───────────────────────────────────────────────────────────────

class ValidateRequest(BaseModel):
    design_id:         str
    expected_hash:     Optional[str] = None   # varsa hash uyum kontrolü


@router.post("/validate", summary="Kabin doğrulama")
def validate_design(req: ValidateRequest):
    """
    Archi'vteki AcousticDesignPacket'i doğrular.
    - Akustik kısıtları kontrol eder (validate_acoustic)
    - expected_hash verilmişse packet_hash ile eşleştirir
    - Döner: { valid, packet_hash, errors, warnings }
    """
    acoustic = _store.get_acoustic(req.design_id)
    if acoustic is None:
        raise HTTPException(404, detail=f"{req.design_id} arşivde bulunamadı.")

    from core.validators import validate_acoustic
    val = validate_acoustic(acoustic)

    # Hash uyum kontrolü (opsiyonel)
    hash_ok = True
    hash_note = ""
    if req.expected_hash:
        hash_ok = acoustic.packet_hash == req.expected_hash
        hash_note = "hash_match" if hash_ok else "hash_mismatch"

    return {
        "design_id":    req.design_id,
        "valid":        val.passed and hash_ok,
        "packet_hash":  acoustic.packet_hash,
        "errors":       val.errors,
        "warnings":     val.warnings,
        "hash_status":  hash_note or ("ok" if acoustic.packet_hash else "no_hash"),
        "net_volume_l": acoustic.net_volume_l,
        "tuning_hz":    acoustic.tuning_hz,
    }


# ── GET /design/{id}/info ─────────────────────────────────────────────────────

@router.get("/{design_id}/info")
def get_design_info(design_id: str):
    """Arşivden tasarım kaydını döner (tüm alanlar)."""
    rec = _store.get(design_id)
    if not rec:
        raise HTTPException(404, detail=f"design_id={design_id} arşivde yok.")
    return rec


# ── GET /design/store/stats ───────────────────────────────────────────────────

@router.get("/store/stats")
def store_stats():
    """Arşiv istatistikleri."""
    return _store.get_stats()


# ── GET /design/{id}/files/dxf ───────────────────────────────────────────────

@router.get("/{design_id}/files/dxf")
def download_dxf(design_id: str, x_api_key: str | None = Header(None)):
    if not _is_premium(x_api_key):
        raise HTTPException(403, detail="DXF indirme Premium uyeye ozguye.")
    for folder in [_EXPORTS, _OUTPUT]:
        path = folder / f"{design_id}.dxf"
        if path.exists():
            return FileResponse(str(path), media_type="application/dxf",
                                filename=f"DD1_{design_id}.dxf")
    raise HTTPException(404, detail=(
        f"DXF bulunamadi: {design_id}. "
        "Once /design/produce ile dosya uretiniz."
    ))


# ── GET /design/{id}/files/stl ───────────────────────────────────────────────

@router.get("/{design_id}/files/stl")
def download_stl(design_id: str):
    for folder in [_EXPORTS, _OUTPUT]:
        path = folder / f"{design_id}.stl"
        if path.exists():
            return FileResponse(str(path), media_type="model/stl",
                                filename=f"DD1_{design_id}.stl")
    raise HTTPException(404, detail=(
        f"STL bulunamadi: {design_id}. "
        "Once /design/produce ile dosya uretiniz."
    ))


# ── GET /design/download/{id} (Genel İndirme Endpoint'i) ─────────────────────

@router.get("/download/{design_id}")
def download_file(design_id: str,
                  fmt: str = "dxf",
                  x_api_key: str | None = Header(None)):
    """
    Aktif download endpoint — eski ve yeni istemciler bu URL'yi kullanır.
    fmt: 'dxf' | 'stl'
    DXF için premium key gerekir.
    """
    fmt = fmt.lower().strip(".")

    if fmt not in ("dxf", "stl"):
        raise HTTPException(400, detail="fmt sadece 'dxf' ya da 'stl' olabilir.")

    if fmt == "dxf" and not _is_premium(x_api_key):
        raise HTTPException(403, detail=(
            "DXF indirme Premium uyeye ozguye. "
            "STL icin fmt=stl kullaniniz."
        ))

    # exports/ → output/ → stub
    candidates = []
    for folder in [_EXPORTS, _OUTPUT]:
        candidates.append(folder / f"{design_id}.{fmt}")
        candidates.append(folder / f"{design_id}_stub.{fmt}")  # dev stub

    for path in candidates:
        if path.exists() and path.stat().st_size > 0:
            media_type = "application/dxf" if fmt == "dxf" else "model/stl"
            return FileResponse(
                str(path), media_type=media_type,
                filename=f"DD1_{design_id}.{fmt.upper()}"
            )

    # Arşivden design var mı kontrol et
    rec = _store.get(design_id)
    not_produced = (
        rec and rec.get("production_status") == "design_only"
    )
    hint = (
        "Uretim yapilmamis. Once POST /design/produce cagiriniz."
        if not_produced else
        f"{fmt.upper()} dosya bulunamadi."
    )
    raise HTTPException(404, detail=hint)


# ═══════════════════════════════════════════════════════════════════════════════
# DİJİTAL ATÖLYE — Yeni Endpoint'ler
# ═══════════════════════════════════════════════════════════════════════════════

class CloneRequest(BaseModel):
    material_thickness_mm: Optional[float] = None
    mode: Optional[str] = None
    vehicle: Optional[str] = None


@router.get("/{design_id}/ui_cards", summary="UI Presenter — Seçenek kartları")
async def get_ui_cards(
    design_id: str,
    selected_option: str = "A",
    use_ai_summary: bool = False,
):
    """
    UIDesignPresenter döner:
    - design_id, selected_option_id, production_ready, warning_level, badges[]
    - cards[] (A/B/C seçenek kartları, expand drawer, visual_preview, material_usage)
    - compare_payload (A vs B, 6 yapılandırılmış alan)
    - mode_lock_notice (FIXED_EXTERNAL modunda aktif)
    """
    rec = _store.get(design_id)
    if not rec:
        raise HTTPException(404, detail=f"{design_id} arşivde bulunamadı.")

    adp_dict = rec.get("acoustic_design_packet", {})
    conflict_report = adp_dict.get("conflict_report_dict") or {}

    # ConflictReport yoksa ADP verilerinden synthetic tek kart oluştur
    if not conflict_report or not conflict_report.get("options"):
        conflict_report = _build_synthetic_report(adp_dict, rec)

    # Usta özetleri (AI veya template)
    usta_summaries: dict = {}
    if use_ai_summary:
        try:
            from core.usta_ozeti import UstaOzeti
            ozet = UstaOzeti(use_ai=True)
            mode = conflict_report.get("mode", "fixed_acoustic")
            for opt in conflict_report.get("options", []):
                oid = opt.get("option_id", "?")
                usta_summaries[oid] = ozet.generate_option_summary(opt, mode)
        except Exception as exc:
            logger.warning("[ROUTER] UstaOzeti hata: %s", exc)
    else:
        try:
            from core.usta_ozeti import UstaOzeti, _template_summary
            ozet = UstaOzeti(use_ai=False)
            mode = conflict_report.get("mode", "fixed_acoustic")
            for opt in conflict_report.get("options", []):
                oid = opt.get("option_id", "?")
                usta_summaries[oid] = _template_summary(opt)
        except Exception as exc:
            logger.warning("[ROUTER] Template özet hata: %s", exc)

    from core.ui_presenter import presenter_from_conflict_report
    presenter = presenter_from_conflict_report(
        design_id=design_id,
        report_dict=conflict_report,
        selected_option_id=selected_option,
        usta_summaries=usta_summaries,
    )
    return JSONResponse(presenter.to_dict())


def _build_synthetic_report(adp: dict, rec: dict) -> dict:
    """ADP'den tek seçenekli synthetic conflict report üretir."""
    dims = [
        adp.get("outer_width_mm", 400),
        adp.get("outer_height_mm", 500),
        adp.get("outer_depth_mm", 350),
    ]
    return {
        "mode": rec.get("design_mode", "fixed_acoustic"),
        "options": [{
            "option_id": "A",
            "strategy": "direct_design",
            "recommended": True,
            "production_ready": rec.get("production_status", "design_only") != "design_only",
            "acoustic_delta_pct": adp.get("volume_breakdown", {}).get("delta_pct", 0.0),
            "fit_status": "ok",
            "estimated_final_net_l": adp.get("net_volume_l", 0.0),
            "estimated_final_tuning_hz": adp.get("tuning_hz", 0.0),
            "outer_dimensions_mm": dims,
            "material_thickness_mm": adp.get("material_thickness_mm", 18.0),
            "panel_join_strategy": "finger_joint",
            "manufacturability_status": "ok",
            "usta_summary": "",
            "panel_list": adp.get("panel_list", []),  # FIX: ADP'den UI Cards'a panel_list taşı
        }]
    }


@router.get("/archive/search", summary="Arşiv arama — araç/tarih filtreli")
async def search_archive(
    vehicle: Optional[str] = None,
    date_from: Optional[str] = None,
    limit: int = 20,
):
    """
    Geçmiş tasarımları arar.
    - vehicle: araç adı (partial match, case-insensitive)
    - date_from: ISO tarih (>=), örn. "2026-03-01"
    - limit: maksimum sonuç sayısı
    """
    results = _store.search(vehicle=vehicle, date_from=date_from, limit=limit)
    return JSONResponse({
        "count": len(results),
        "results": [
            {
                "design_id":    r.get("design_id"),
                "created_at":   r.get("created_at"),
                "vehicle":      r.get("intake_packet", {}).get("vehicle"),
                "net_volume_l": r.get("acoustic_design_packet", {}).get("net_volume_l"),
                "tuning_hz":    r.get("acoustic_design_packet", {}).get("tuning_hz"),
                "status":       r.get("production_status"),
                "cloned_from":  r.get("cloned_from"),
            }
            for r in results
        ]
    })


@router.post("/archive/{design_id}/clone", summary="Tasarım klonla & override")
async def clone_design(design_id: str, body: CloneRequest):
    """
    Mevcut tasarımı klonlar.
    Override: material_thickness_mm → tüm geometri yeniden hesap flag'i eklenir.
    Clone & Modify: "Geçen haftaki Egea projesini getir, 15mm kontra olsun" akışı.
    """
    overrides = body.model_dump(exclude_none=True)
    new_rec = _store.clone(design_id, overrides=overrides)
    if not new_rec:
        raise HTTPException(404, detail=f"{design_id} bulunamadı.")
    return JSONResponse({
        "new_design_id":  new_rec["design_id"],
        "cloned_from":    design_id,
        "material_override": new_rec.get("material_override"),
        "message": (
            f"Klonlandı: {design_id} → {new_rec['design_id']}. "
            + ("Malzeme değişimi tespit edildi; geometri yeniden hesap edin."
               if new_rec.get("material_override") else "")
        ),
    })


@router.get("/{design_id}/compare", summary="İki seçenek kıyaslama")
async def compare_designs(design_id: str, with_id: str):
    """
    İki design_id arasında yapılandırılmış ComparisonData döner.
    (net_l_diff, tuning_diff_hz, outer_dim_diff_mm, fit_diff,
     production_ready_diff, material_diff)
    """
    rec_a = _store.get(design_id)
    rec_b = _store.get(with_id)
    if not rec_a:
        raise HTTPException(404, detail=f"{design_id} bulunamadı.")
    if not rec_b:
        raise HTTPException(404, detail=f"{with_id} bulunamadı.")

    adp_a = rec_a.get("acoustic_design_packet", {})
    adp_b = rec_b.get("acoustic_design_packet", {})

    def _dims(adp: dict) -> list:
        return [adp.get("outer_width_mm", 0), adp.get("outer_height_mm", 0),
                adp.get("outer_depth_mm", 0)]

    pr_a = rec_a.get("production_status", "design_only") != "design_only"
    pr_b = rec_b.get("production_status", "design_only") != "design_only"
    dims_a = _dims(adp_a)
    dims_b = _dims(adp_b)
    t_a = adp_a.get("material_thickness_mm", 18.0)
    t_b = adp_b.get("material_thickness_mm", 18.0)
    net_a = adp_a.get("net_volume_l", 0.0)
    net_b = adp_b.get("net_volume_l", 0.0)
    tune_a = adp_a.get("tuning_hz", 0.0)
    tune_b = adp_b.get("tuning_hz", 0.0)

    if pr_a and not pr_b:   pr_diff = "A=Ready, B=NotReady"
    elif pr_b and not pr_a: pr_diff = "A=NotReady, B=Ready"
    elif pr_a and pr_b:     pr_diff = "İkisi de Ready"
    else:                   pr_diff = "İkisi de NotReady"

    return JSONResponse({
        "option_a_id":            design_id,
        "option_b_id":            with_id,
        "net_l_diff":             round(net_a - net_b, 3),
        "tuning_diff_hz":         round(tune_a - tune_b, 1),
        "outer_dim_diff_mm":      [round(a - b, 1) for a, b in zip(dims_a, dims_b)],
        "fit_diff":               "Eşit",
        "production_ready_diff":  pr_diff,
        "material_diff":          "Aynı" if t_a == t_b else f"A={t_a}mm, B={t_b}mm",
    })
