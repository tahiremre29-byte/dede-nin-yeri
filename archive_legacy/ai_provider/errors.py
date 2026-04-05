"""
core/ai_provider/errors.py
Ortak AI Provider Hata Sınıfları

Tüm provider'lar (Gemini, OpenAI, vb.) bu hata sınıflarını kullanır.
Upstream katman provider'ı bilmez — sadece bu sınıfları görür.
"""
from __future__ import annotations

# ── Hata Hiyerarşisi ─────────────────────────────────────────────────────────

class AIProviderError(Exception):
    """Tüm AI provider hatalarının tabanı."""
    error_class: str = "provider_error"
    user_message: str = "Şu an akıllı yanıt üretemiyorum. Bilgilerini aldım, elimdekilerle devam edeyim."

class AIKeyMissingError(AIProviderError):
    error_class   = "key_missing"
    user_message  = "Akıllı mod şu an kapalı. Kural tabanlı sorgunda devam edebiliriz."

class AIKeyInvalidError(AIProviderError):
    error_class   = "key_invalid"
    user_message  = "Akıllı mod şu an çalışmıyor. Topladığım bilgilerle devam edebiliriz."

class AIQuotaError(AIProviderError):
    error_class   = "quota_exceeded"
    user_message  = "Sistem yoğundu, akıllı yanıt üretemedi. Kural tabanlı devam edelim."

class AITimeoutError(AIProviderError):
    error_class   = "timeout"
    user_message  = "Yanıt biraz geç kaldı. Topladığım bilgilerle devam edeyim."

class AINetworkError(AIProviderError):
    error_class   = "network_error"
    user_message  = "Bağlantı sorunu var. Elimdekilerle devam edeyim."

class AIRuntimeError(AIProviderError):
    error_class   = "runtime"
    user_message  = "Akıllı yanıt üretemedi. Topladığım bilgilerle devam edelim."



# ── Exception Sınıflandırıcı ─────────────────────────────────────────────────

_KEY_SIGNALS     = ("api key", "api_key", "invalid_argument", "key expired",
                    "api_key_invalid", "authenticationerror", "incorrect api key")
_QUOTA_SIGNALS   = ("quota", "resource exhausted", "rate limit",
                    "too many requests", "ratelimiterror")
_TIMEOUT_SIGNALS = ("timeout", "timed out", "deadline", "apitimeouterror")
_NETWORK_SIGNALS = ("connection", "transport", "network", "ssl",
                    "socket", "apiconnectionerror")


def classify_exception(exc: Exception) -> AIProviderError:
    """
    Ham exception'ı provider-agnostik AIProviderError alt sınıfına çevirir.
    Döner: AIProviderError alt sınıfı instance (error_class + user_message hazır).
    """
    msg = str(exc).lower()
    exc_name = type(exc).__name__.lower()
    combined = msg + " " + exc_name

    if any(k in combined for k in _KEY_SIGNALS):
        return AIKeyInvalidError(str(exc))
    if any(k in combined for k in _QUOTA_SIGNALS):
        return AIQuotaError(str(exc))
    if any(k in combined for k in _TIMEOUT_SIGNALS):
        return AITimeoutError(str(exc))
    if any(k in combined for k in _NETWORK_SIGNALS):
        return AINetworkError(str(exc))
    return AIRuntimeError(str(exc))
