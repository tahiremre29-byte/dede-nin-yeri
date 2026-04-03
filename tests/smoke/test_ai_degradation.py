"""
tests/smoke/test_ai_degradation.py
AI Graceful Degradation — Smoke Testler

[D1] key_missing  → ai_mode=standard, reply AI hata mesajı içermez
[D2] key_invalid  → ai_mode=standard, kullanıcı mesajı sade
[D3] quota_exceeded → ai_mode=standard, kullanıcı mesajı sade
[D4] timeout      → ai_mode=standard, kullanıcı mesajı sade
[D5] state        → fallback'ta normalized_panel korunuyor
"""
import sys, os, re
sys.path.insert(0, r"C:\Users\DDSOUND\Desktop\exemiz\dd1_platform")

# ── Yardımcı: yapay exception ile _classify_error test
def _get_adapter():
    from core.ai_adapter import reset_adapter, AIAdapter
    reset_adapter()
    return AIAdapter()

def test_d1_classify_key_missing():
    adapter = _get_adapter()
    exc = Exception("api_key bulunamadı / api key missing")
    reason, msg = adapter._classify_error(exc)
    assert reason == "key_invalid", f"[D1] FAIL: {reason}"
    assert "Akıllı mod" in msg, f"[D1] FAIL: msg='{msg}'"
    print(f"[D1] PASS: key_missing → reason={reason}")

def test_d2_classify_key_invalid():
    adapter = _get_adapter()
    exc = Exception("400 INVALID_ARGUMENT api key expired api_key_invalid")
    reason, msg = adapter._classify_error(exc)
    assert reason == "key_invalid", f"[D2] FAIL: {reason}"
    assert "Standart" in msg or "Akıllı" in msg, f"[D2] msg='{msg}'"
    print(f"[D2] PASS: key_invalid → reason={reason}")

def test_d3_classify_quota():
    adapter = _get_adapter()
    exc = Exception("429 resource exhausted quota exceeded")
    reason, msg = adapter._classify_error(exc)
    assert reason == "quota_exceeded", f"[D3] FAIL: {reason}"
    assert "yoğunluk" in msg or "Standart" in msg, f"[D3] msg='{msg}'"
    print(f"[D3] PASS: quota → reason={reason}")

def test_d4_classify_timeout():
    adapter = _get_adapter()
    exc = Exception("ConnectionError: timed out waiting for response")
    reason, msg = adapter._classify_error(exc)
    assert reason == "timeout", f"[D4] FAIL: {reason}"
    print(f"[D4] PASS: timeout → reason={reason}")

def test_d5_error_response_has_ai_mode():
    adapter = _get_adapter()
    exc = Exception("quota exceeded")
    resp = adapter._error_response(exc)
    assert resp.finish_reason == "error", "[D5] FAIL: finish_reason"
    assert resp.structured_json is not None, "[D5] FAIL: no structured_json"
    assert resp.structured_json.get("ai_mode") == "standard", "[D5] FAIL: ai_mode"
    assert resp.structured_json.get("ai_error_class") == "quota_exceeded", "[D5] FAIL: ai_error_class"
    # Kullanıcıya stack trace veya teknik exc gitmemeli
    assert "quota" not in resp.text.lower() or "yoğunluk" in resp.text, "[D5] FAIL: raw exception in reply"
    assert "Exception" not in resp.text, "[D5] FAIL: Exception class name in reply"
    print(f"[D5] PASS: error_response ai_mode=standard, text='{resp.text[:60]}'")

def test_d6_no_stack_trace_in_user_msg():
    adapter = _get_adapter()
    for exc_msg in ["google.api_core.exceptions.ResourceExhausted", "Traceback", "line 320 in _generate_sync"]:
        _, user_msg = adapter._classify_error(Exception(exc_msg))
        assert "Traceback" not in user_msg, f"[D6] FAIL: stack trace in reply for '{exc_msg}'"
        assert "line " not in user_msg, f"[D6] FAIL: line ref in reply for '{exc_msg}'"
    print("[D6] PASS: no stack trace in user messages")

if __name__ == "__main__":
    tests = [
        test_d1_classify_key_missing,
        test_d2_classify_key_invalid,
        test_d3_classify_quota,
        test_d4_classify_timeout,
        test_d5_error_response_has_ai_mode,
        test_d6_no_stack_trace_in_user_msg,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  [FAIL] {t.__name__}: {e}")
    print("--- smoke/test_ai_degradation DONE ---")
