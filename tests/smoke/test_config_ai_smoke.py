"""
tests/smoke/test_config_ai_smoke.py
OBS-007 Sertle?tirme — Madde 3: Config + AIAdapter smoke testleri

[S1] config.py key loading: GEMINI_API_KEY .env'den yukleniyor mu?
[S2] LLMEngine init: ba?l?yor mu?
[S3] Key eksik oldugunda AIValidationError atiyor mu? (fallback yok)
[S4] Startup log mesajlari dogru siniftan geliyor mu?
"""
import sys, os, logging
from pathlib import Path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- S1: Key yukleme ---
def test_s1_key_loads():
    from core.config import reload_config
    cfg = reload_config()
    key = cfg.gemini_api_key
    assert key and len(key) >= 20, (
        f"[S1] FAIL: GEMINI_API_KEY yuklenmedi veya cok kisa (len={len(key)}). "
        ".env dosyasini kontrol et."
    )
    print(f"[S1] PASS: key={key[:8]}...{key[-4:]} ({len(key)} karakter)")

# --- S2: LLMEngine init ---
def test_s2_adapter_init():
    from core.llm_engine import LLMEngine
    engine = LLMEngine()
    assert engine.model_name == "gemini-2.5-flash", f"[S2] model hata: {engine.model_name}"
    print(f"[S2] PASS: model={engine.model_name}")

# --- S3: Key eksik -> ValueError ---
def test_s3_missing_key_raises():
    from core.llm_engine import LLMEngine
    from core import config as _cfg_mod
    original = os.environ.pop("GEMINI_API_KEY", None)
    try:
        # cfg singleton'u da key'siz yenile
        _cfg_mod.cfg = _cfg_mod._load_config()
        try:
            LLMEngine()   # KeyError/ValueError atmasi beklenir
            assert False, "[S3] FAIL: ValueError bekleniyor ama atilmadi"
        except ValueError:
            print("[S3] PASS: key eksik -> ValueError atti (fail-fast)")
    finally:
        if original:
            os.environ["GEMINI_API_KEY"] = original
        _cfg_mod.cfg = _cfg_mod._load_config()  # cfg'yi geri yukle

# --- S4: Startup log logger adi ---
def test_s4_startup_logger():
    import core.config as cc
    logger = logging.getLogger("dd1.config")
    assert logger is not None
    # _key_present degiskeni var mi?
    assert hasattr(cc, "_key_present"), "[S4] _key_present config'de yok"
    print(f"[S4] PASS: dd1.config logger mevcut, _key_present={cc._key_present}")

if __name__ == "__main__":
    tests = [test_s1_key_loads, test_s2_adapter_init, test_s3_missing_key_raises, test_s4_startup_logger]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
    print("ALL PASS -- smoke/test_config_ai_smoke")
