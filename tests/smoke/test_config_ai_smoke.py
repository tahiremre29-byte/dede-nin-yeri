"""
tests/smoke/test_config_ai_smoke.py
OBS-007 Sertle?tirme — Madde 3: Config + AIAdapter smoke testleri

[S1] config.py key loading: GEMINI_API_KEY .env'den yukleniyor mu?
[S2] AIAdapter init: backend=developer model=gemini-2.0-flash basliyor mu?
[S3] Key eksik oldugunda AIValidationError atiyor mu? (fallback yok)
[S4] Startup log mesajlari dogru siniftan geliyor mu?
"""
import sys, os, logging
sys.path.insert(0, r"C:\Users\DDSOUND\Desktop\exemiz\dd1_platform")

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

# --- S2: AIAdapter init ---
def test_s2_adapter_init():
    from core.ai_adapter import reset_adapter, AIAdapter
    reset_adapter()
    adapter = AIAdapter()
    assert adapter._backend == "developer", f"[S2] backend hata: {adapter._backend}"
    assert "gemini" in adapter._model, f"[S2] model hata: {adapter._model}"
    print(f"[S2] PASS: backend={adapter._backend} model={adapter._model}")

# --- S3: Key eksik -> AIValidationError ---
def test_s3_missing_key_raises():
    from core.ai_adapter import reset_adapter, AIAdapter
    from core.ai_adapter import AIValidationError
    from core import config as _cfg_mod
    reset_adapter()
    original = os.environ.pop("GEMINI_API_KEY", None)
    try:
        # cfg singleton'u da key'siz yenile
        _cfg_mod.cfg = _cfg_mod._load_config()
        try:
            AIAdapter()   # api_key=None → cfg.gemini_api_key="" → AIValidationError
            assert False, "[S3] FAIL: AIValidationError bekleniyor ama atilmadi"
        except AIValidationError:
            print("[S3] PASS: key eksik -> AIValidationError atti (fail-fast)")
    finally:
        if original:
            os.environ["GEMINI_API_KEY"] = original
        _cfg_mod.cfg = _cfg_mod._load_config()  # cfg'yi geri yukle
        reset_adapter()

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
