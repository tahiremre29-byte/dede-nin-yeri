"""
core/ai_provider/base.py
Ortak AI Provider Arayüzü (Abstract Base)

Her yeni provider bu sınıftan türer ve generate() metodunu uygular.
Upstream (ai_adapter, chat_service, agents) yalnızca bu arayüzü ve
AIProviderResponse'u görür.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


# ── Ortak Response Şeması ────────────────────────────────────────────────────

@dataclass
class AIProviderResponse:
    """
    Provider-agnostik normalize edilmiş AI yanıtı.

    Tüm provider'lar (Gemini, OpenAI, …) bu dataclass'ı döner.
    Upstream katmanlar provider adını bilmek zorunda değildir.
    """
    text:             str            = ""
    finish_reason:    str            = "stop"   # stop | safety | length | error
    provider:         str            = ""        # "gemini" | "openai"
    model:            str            = ""
    usage:            Optional[dict] = None      # token sayıları
    structured_json:  Optional[dict] = None      # JSON parse (opsiyonel)
    tool_calls:       list           = field(default_factory=list)
    raw_response:     Any            = None      # sadece debug modda
    # Graceful degradation alanları — UI tarafına geçer
    ai_mode:          str            = "smart"   # "smart" | "standard"
    ai_error_class:   Optional[str]  = None      # key_invalid|quota_exceeded|…

    @property
    def ok(self) -> bool:
        return self.finish_reason not in ("error", "safety")

    def to_dict(self) -> dict:
        return {
            "text":           self.text,
            "finish_reason":  self.finish_reason,
            "provider":       self.provider,
            "model":          self.model,
            "usage":          self.usage,
            "ai_mode":        self.ai_mode,
            "ai_error_class": self.ai_error_class,
        }


# ── Abstract Provider ────────────────────────────────────────────────────────

class BaseAIProvider(ABC):
    """
    Ortak AI sağlayıcı arayüzü.
    Her provider __init__() içinde key'i doğrular ve client'ı kurar.
    """
    name:  str  = ""   # "gemini" | "openai"
    model: str  = ""

    @abstractmethod
    def generate(
        self,
        prompt:        str,
        system_prompt: str   = "",
        temperature:   float = 0.7,
        max_tokens:    int   = 2048,
        **kwargs,
    ) -> AIProviderResponse:
        """
        Prompt → AIProviderResponse döner.
        Hiçbir zaman raw exception fırlatmaz — her hatayı AIProviderResponse(finish_reason="error") olarak döner.
        """
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Basit ping — True: provider erişilebilir."""
        ...

    def _error_response(
        self,
        exc: Exception,
        provider_name: str = "",
        model_name:    str = "",
    ) -> AIProviderResponse:
        """
        Exception → normalize edilmiş hata response.
        alt sınıflar override etmek zorunda değil — ortak implementasyon.
        """
        from core.ai_provider.errors import classify_exception
        import logging
        log = logging.getLogger(f"dd1.ai_provider.{provider_name or self.name}")
        normalized = classify_exception(exc)
        log.error(
            "[AI_PROVIDER:%s] hata=%s | %s: %s",
            provider_name or self.name,
            normalized.error_class,
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        return AIProviderResponse(
            text           = normalized.user_message,
            finish_reason  = "error",
            provider       = provider_name or self.name,
            model          = model_name or self.model,
            ai_mode        = "standard",
            ai_error_class = normalized.error_class,
            structured_json = {
                "ai_mode":        "standard",
                "ai_error_class": normalized.error_class,
            },
        )
