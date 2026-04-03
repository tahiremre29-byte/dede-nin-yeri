"""
core/config.py
DD1 Environment Configuration

ENV değişkeni DD1_ENV: "development" | "test" | "production"  (varsayılan: development)

Kullanım:
    from core.config import cfg
    if cfg.debug: ...
    if cfg.is_production: ...
"""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path

import logging as _logging
import warnings as _warnings

# ── .env yükleme — python-dotenv varsa kullan, yoksa elle oku ─────────────────
_DD1_ROOT = Path(__file__).resolve().parent.parent  # core/ -> dd1_platform/
_ENV_PATH  = _DD1_ROOT / ".env"

_startup_log = _logging.getLogger("dd1.config")
_env_file_ok  = False

def _load_env_file():
    global _env_file_ok
    if not _ENV_PATH.exists():
        _startup_log.warning("[CONFIG] .env bulunamadi: %s", _ENV_PATH)
        return
    try:
        from dotenv import load_dotenv as _ld
        _ld(_ENV_PATH, override=True)
        _env_file_ok = True
        _startup_log.info("[CONFIG] .env yuklendi (dotenv): %s", _ENV_PATH)
        return
    except ImportError:
        pass
    # Manuel fallback
    with open(_ENV_PATH, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _, _v = _line.partition("=")
            _k = _k.strip()
            _v = _v.strip().strip('"').strip("'")
            if _k:
                os.environ[_k] = _v
    _env_file_ok = True
    _startup_log.info("[CONFIG] .env yuklendi (manuel): %s", _ENV_PATH)

_load_env_file()

# Key kontrolü: import anında uyar (ajan kapalıyken kullanıcı bilsin)
_key_present = bool(os.environ.get("GEMINI_API_KEY", ""))
if not _key_present:
    _startup_log.warning(
        "[CONFIG] GEMINI_API_KEY bulunamadı. "
        "Akıllı mod (AI ajan) devre dışı — yalnız kural tabanlı intake çalışır. "
        ".env dosyasına GEMINI_API_KEY ekle veya ortam değişkeni olarak set et."
    )


@dataclass(frozen=True)
class DD1Config:
    env:            str   = "development"

    # Genel
    debug:          bool  = False
    log_level:      str   = "INFO"

    # Chaos / Test
    chaos_enabled:  bool  = False      # üretimde kesinlikle False

    # API
    gemini_api_key: str   = ""
    premium_key:    str   = "premium-dev"

    # Dizinler
    knowledge_dir:  str   = "knowledge"
    exports_dir:    str   = "exports"
    output_dir:     str   = "output"
    archive_file:   str   = "knowledge/design_archive.json"

    # Akustik sinirlar (merkezi)
    max_port_velocity_ms: float = 25.0
    min_volume_l:         float = 5.0
    max_volume_l:         float = 600.0

    # DXF Export surumu
    dxf_version:  str = "R2010"   # "R2010" (modern) | "R12" (legacy/CorelDraw eski)

    # ── AI Adapter (google-genai) ─────────────────────────────────────────────
    # Backend: "developer" (API key) | "vertex" (GCP)
    ai_backend_mode:      str   = "developer"    # env: AI_BACKEND_MODE
    gemini_model_name:    str   = "gemini-2.0-flash"  # env: GEMINI_MODEL_NAME
    ai_timeout_seconds:   float = 30.0           # env: AI_TIMEOUT_SECONDS
    ai_retry_count:       int   = 3              # env: AI_RETRY_COUNT
    stream_enabled:       bool  = False          # env: STREAM_ENABLED
    google_cloud_project: str   = ""             # env: GOOGLE_CLOUD_PROJECT
    google_cloud_location:str   = "us-central1" # env: GOOGLE_CLOUD_LOCATION
    # ── AI Provider Seçici (v1 adapter) ──────────────────────────────────────────
    ai_provider:          str   = "gemini"       # env: AI_PROVIDER (gemini | openai)
    openai_api_key:       str   = ""             # env: OPENAI_API_KEY
    openai_model:         str   = "gpt-4o-mini" # env: OPENAI_MODEL

    # Cakisma Cozum Motor esikleri
    conflict_threshold_pct:               float = 3.0   # On-eri tetik esigi
    delta_fail_threshold_pct:             float = 2.0   # Uretim durdurma
    volume_deficit_suggest_invert_pct:    float = 3.0   # Invert driver onerisi icin min
    volume_deficit_suggest_material_pct:  float = 7.0   # Malzeme degisimi icin min
    compromise_option_count:              int   = 3

    # Feature Flags (Auth & Registration)
    auth_anonymous_mode:                  bool  = True
    auth_registration_required:           bool  = False
    auth_consent_screens:                 bool  = False
    history_tracking_enabled:             bool  = True
    dxf_download_policy:                  str   = "open" # "open" | "paid_per_file" | "premium_subscription" | "admin_free"

    # Mod bazli resize izni (frozen dict yerine str key ile tutuyoruz)
    # Okuma: cfg.resize_allowed_for(mode)
    def resize_allowed_for(self, mode: str) -> bool:
        return mode == "fixed_acoustic"

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def is_test(self) -> bool:
        return self.env == "test"

    @property
    def is_development(self) -> bool:
        return self.env in ("development", "dev")


def _load_config() -> DD1Config:
    env = os.environ.get("DD1_ENV", "development").lower()
    debug = env != "production" and os.environ.get("DD1_DEBUG", "false").lower() == "true"

    # Chaos: sadece development/test ve explicit DD1_CHAOS=true
    chaos = (
        env != "production"
        and os.environ.get("DD1_CHAOS", "false").lower() == "true"
    )

    return DD1Config(
        env=env,
        debug=debug,
        log_level="DEBUG" if debug else "INFO",
        chaos_enabled=chaos,
        gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
        premium_key=os.environ.get("DD1_PREMIUM_KEY", "premium-dev"),
        dxf_version=os.environ.get("DD1_DXF_VERSION", "R2010").upper(),
        # AI Adapter
        ai_backend_mode=os.environ.get("AI_BACKEND_MODE", "developer").lower(),
        gemini_model_name=os.environ.get("GEMINI_MODEL_NAME", "gemini-2.0-flash"),
        ai_timeout_seconds=float(os.environ.get("AI_TIMEOUT_SECONDS", "30")),
        ai_retry_count=int(os.environ.get("AI_RETRY_COUNT", "3")),
        stream_enabled=os.environ.get("STREAM_ENABLED", "false").lower() == "true",
        google_cloud_project=os.environ.get("GOOGLE_CLOUD_PROJECT", ""),
        google_cloud_location=os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"),
        # AI Provider Adapter v1
        ai_provider=os.environ.get("AI_PROVIDER", "gemini").lower(),
        openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        
        # Auth Feature Flags
        auth_anonymous_mode=os.environ.get("AUTH_ANONYMOUS_MODE", "true").lower() == "true",
        auth_registration_required=os.environ.get("AUTH_REGISTRATION_REQUIRED", "true").lower() == "true",
        auth_consent_screens=os.environ.get("AUTH_CONSENT_SCREENS", "false").lower() == "true",
        history_tracking_enabled=os.environ.get("HISTORY_TRACKING_ENABLED", "true").lower() == "true",
        dxf_download_policy=os.environ.get("DXF_DOWNLOAD_POLICY", "open").lower(),
    )


# Singleton — her yerde `from core.config import cfg` ile kullan
cfg: DD1Config = _load_config()


def reload_config() -> DD1Config:
    """Birim testlerinde env değişkenlerini değiştirdikten sonra çağır."""
    global cfg
    cfg = _load_config()
    return cfg
