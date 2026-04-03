"""
services/design_store.py
DD1 Atomik Kalıcı Design Store

Tasarım arşivini knowledge/design_archive.json'a atomik olarak yazar.

Yazma Protokolü:
  1. Veriyi .tmp dosyasına yaz (tam ve geçerli JSON)
  2. Mevcut dosyayı .bak olarak yedekle
  3. .tmp → orijinal dosyaya atomik rename

Şema Zorunlu Alanlar:
  schema_version, design_id, created_at, intake_packet,
  acoustic_design_packet, production_status, export_paths

Thread-safe: threading.Lock ile korunur.
Restart-safe: başlangıçta arşivi RAM'e yükler.
"""
from __future__ import annotations
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Optional

from schemas.acoustic_design_packet import AcousticDesignPacket

logger = logging.getLogger("dd1.design_store")

SCHEMA_VERSION = "1.0"
_BASE          = Path(__file__).parent.parent / "knowledge"
_ARCHIVE       = _BASE / "design_archive.json"
_EXPORTS_DIR   = Path(__file__).parent.parent / "exports"

_LOCK: Lock = Lock()
_CACHE: dict[str, dict] = {}   # design_id → arşiv kaydı (RAM)
_LOADED = False


# ── Başlatma: Arşivi RAM'e Yükle ─────────────────────────────────────────────

def _ensure_loaded() -> None:
    global _LOADED
    if _LOADED:
        return
    with _LOCK:
        if _LOADED:
            return
        _BASE.mkdir(parents=True, exist_ok=True)
        _EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        if _ARCHIVE.exists():
            try:
                raw = json.loads(_ARCHIVE.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    for rec in raw:
                        did = rec.get("design_id")
                        if did:
                            _CACHE[did] = rec
                    logger.info(
                        "[STORE] Arşiv yuklendi: %d kayit", len(_CACHE)
                    )
            except (json.JSONDecodeError, OSError) as exc:
                logger.error("[STORE] Arsiv okunamadi: %s", exc)
        _LOADED = True


# ── Atomik Yazma ──────────────────────────────────────────────────────────────

def _atomic_save() -> None:
    """
    Tüm cache'i atomik olarak disk'e yaz.
    .tmp → kaydet → .bak al → rename
    """
    records = list(_CACHE.values())
    payload = json.dumps(records, ensure_ascii=False, indent=2)

    tmp_path = _ARCHIVE.with_suffix(".tmp")
    bak_path = _ARCHIVE.with_suffix(".bak")

    # 1. .tmp'ye yaz
    tmp_path.write_text(payload, encoding="utf-8")

    # 2. Mevcut dosyayı .bak'a taşı
    if _ARCHIVE.exists():
        try:
            if bak_path.exists():
                bak_path.unlink()
            _ARCHIVE.rename(bak_path)
        except OSError as exc:
            logger.warning("[STORE] .bak olusturulamadi: %s", exc)

    # 3. .tmp → orijinal (atomik rename)
    os.replace(str(tmp_path), str(_ARCHIVE))
    logger.debug("[STORE] Atomik kayit tamamlandi: %d kayit", len(records))


# ── Kayıt Oluşturucu ──────────────────────────────────────────────────────────

def _make_record(
    acoustic: AcousticDesignPacket,
    intake_dict: dict | None = None,
    production_status: str = "design_only",
    export_paths: dict | None = None,
) -> dict:
    return {
        "schema_version":         SCHEMA_VERSION,
        "design_id":              acoustic.design_id,
        "created_at":             datetime.utcnow().isoformat() + "Z",
        "intake_packet":          intake_dict or {},
        "acoustic_design_packet": acoustic.model_dump(),
        "production_status":      production_status,
        "export_paths":           export_paths or {},
    }


# ── Public API ────────────────────────────────────────────────────────────────

def save(
    acoustic: AcousticDesignPacket,
    intake_dict: dict | None = None,
    production_status: str = "design_only",
    export_paths: dict | None = None,
) -> bool:
    """Akustik paketi arşive kaydet (atomik). True → başarılı."""
    _ensure_loaded()
    try:
        with _LOCK:
            record = _make_record(
                acoustic, intake_dict, production_status, export_paths
            )
            _CACHE[acoustic.design_id] = record
            _atomic_save()
        logger.info("[STORE] Kaydedildi: %s", acoustic.design_id)
        return True
    except OSError as exc:
        logger.error("[STORE] Kayit hatasi: %s", exc)
        return False


def get(design_id: str) -> Optional[dict]:
    """Arşivden kayıt döner. Yoksa None."""
    _ensure_loaded()
    with _LOCK:
        return _CACHE.get(design_id)


def get_acoustic(design_id: str) -> Optional[AcousticDesignPacket]:
    """Kaydı AcousticDesignPacket'e çevirerek döner."""
    rec = get(design_id)
    if not rec:
        return None
    try:
        return AcousticDesignPacket(**rec["acoustic_design_packet"])
    except Exception as exc:
        logger.error("[STORE] Paket deserializasyon hatasi: %s", exc)
        return None


def update_production(
    design_id: str,
    production_status: str,
    export_paths: dict,
) -> bool:
    """Mevcut kaydın üretim bilgilerini güncelle."""
    _ensure_loaded()
    try:
        with _LOCK:
            rec = _CACHE.get(design_id)
            if not rec:
                return False
            rec["production_status"] = production_status
            rec["export_paths"].update(export_paths)
            _atomic_save()
        return True
    except OSError as exc:
        logger.error("[STORE] Uretim guncelleme hatasi: %s", exc)
        return False


def list_all() -> list[str]:
    """Tüm arşivlenmiş design_id'leri döner."""
    _ensure_loaded()
    with _LOCK:
        return list(_CACHE.keys())


def list_designs() -> list[dict]:
    """Tüm arşivlenmiş tasarım kayıtlarını döner (en yeni önce).
    T11 selected_option_id zinciri testi ve UI için public API."""
    _ensure_loaded()
    with _LOCK:
        records = list(_CACHE.values())
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return records


def search(
    vehicle: str | None = None,
    date_from: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """
    Arşivde arama yapar.

    Filtreler:
      vehicle    — araç tipi (case-insensitive, partial match)
      date_from  — ISO tarih string (>=, ör. "2026-03-01")
      limit      — sonuç sayısı sınırı

    Döner: arşiv kayıt listesi (en yeni önce sıralı)
    """
    _ensure_loaded()
    with _LOCK:
        records = list(_CACHE.values())

    # Sırala: en yeni önce
    records.sort(key=lambda r: r.get("created_at", ""), reverse=True)

    results = []
    for rec in records:
        # Araç filtresi
        if vehicle:
            intake = rec.get("intake_packet", {})
            rec_vehicle = (intake.get("vehicle") or "").lower()
            if vehicle.lower() not in rec_vehicle:
                continue
        # Tarih filtresi
        if date_from:
            created = rec.get("created_at", "")
            if created < date_from:
                continue
        results.append(rec)
        if len(results) >= limit:
            break

    logger.info(
        "[STORE] search(vehicle=%s, date_from=%s) → %d sonuç",
        vehicle, date_from, len(results)
    )
    return results


def clone(
    design_id: str,
    overrides: dict | None = None,
) -> dict | None:
    """
    Mevcut bir tasarımı klonlar — yeni design_id ile arşive kaydeder.

    overrides (opsiyonel dict):
      material_thickness_mm  : yeni malzeme kalınlığı (tam yeniden hesap tetiklenir)
      mode                   : yeni tasarım modu
      vehicle                : yeni araç adı

    Döner: yeni arşiv kaydı veya None (kaynak bulunamazsa).
    """
    overrides = overrides or {}
    _ensure_loaded()

    with _LOCK:
        src = _CACHE.get(design_id)

    if src is None:
        logger.warning("[STORE] clone: kaynak bulunamadı: %s", design_id)
        return None

    import copy, uuid, datetime as _dt

    new_id  = f"dd1_{uuid.uuid4().hex[:8]}"
    new_rec = copy.deepcopy(src)
    new_rec["design_id"]  = new_id
    new_rec["created_at"] = _dt.datetime.utcnow().isoformat() + "Z"
    new_rec["cloned_from"] = design_id
    new_rec["production_status"] = "design_only"
    new_rec["export_paths"] = {}

    # Acoustic packet içindeki design_id güncelle
    adp = new_rec.get("acoustic_design_packet", {})
    adp["design_id"] = new_id
    new_rec["acoustic_design_packet"] = adp

    # Override: intake_packet
    intake = new_rec.get("intake_packet", {})
    if "vehicle" in overrides:
        intake["vehicle"] = overrides["vehicle"]
    new_rec["intake_packet"] = intake

    # Override: material_thickness
    if "material_thickness_mm" in overrides:
        new_t = float(overrides["material_thickness_mm"])
        old_t = adp.get("material_thickness_mm", 18.0)
        adp["material_thickness_mm"] = new_t
        # Trigger flag — UI'a recalculation gerektiğini bildirir
        new_rec["material_override"] = {
            "original_mm":       old_t,
            "new_mm":            new_t,
            "recalculation_required": True,
        }
        logger.info(
            "[STORE] clone: malzeme override %smm → %smm (design=%s→%s)",
            old_t, new_t, design_id, new_id,
        )

    # Override: mode
    if "mode" in overrides:
        new_rec["design_mode"] = overrides["mode"]

    with _LOCK:
        _CACHE[new_id] = new_rec
        _atomic_save()

    logger.info("[STORE] clone: %s → %s tamamlandı", design_id, new_id)
    return new_rec


def get_stats() -> dict:
    """Arşiv istatistikleri."""
    _ensure_loaded()
    with _LOCK:
        total = len(_CACHE)
        produced = sum(
            1 for v in _CACHE.values()
            if v.get("production_status") != "design_only"
        )
        return {
            "total_designs": total,
            "produced":      produced,
            "design_only":   total - produced,
            "archive_path":  str(_ARCHIVE),
            "exports_dir":   str(_EXPORTS_DIR),
        }
