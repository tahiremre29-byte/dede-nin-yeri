"""
core/ai_runtime.py
AI Provider Se\u00e7ici — Runtime Fabrika

Kullan\u0131m:
    from core.ai_runtime import get_provider
    provider = get_provider()
    resp = provider.generate(prompt, system_prompt=...)

Config:
    AI_PROVIDER=gemini  → GeminiProvider
    AI_PROVIDER=openai  → OpenAIProvider (OPENAI_API_KEY gerekli)
    AI_PROVIDER=groq    → GroqProvider (GROQ_API_KEY gerekli, ucretsiz)
    AI_PROVIDER belirtilmezse default: groq
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.ai_provider.base import BaseAIProvider

logger = logging.getLogger("dd1.ai_runtime")


def get_provider(force: str | None = None) -> "BaseAIProvider":
    """
    Config'e göre uygun provider'ı döner.
    force parametresiyle test ortamında provider override edilebilir.

    Döner: BaseAIProvider instance (GeminiProvider | OpenAIProvider)
    Her çağrıda yeni instance üretir — singleton ai_adapter.py'de.
    """
    from core.config import cfg
    provider_name = force or cfg.ai_provider or "gemini"

    logger.info("[AI_RUNTIME] Provider seçildi: %s", provider_name)

    if provider_name == "openai":
        from core.ai_provider.openai import OpenAIProvider
        return OpenAIProvider()

    if provider_name == "gemini":
        from core.ai_provider.gemini import GeminiProvider
        return GeminiProvider()

    if provider_name == "groq":
        from core.ai_provider.groq import GroqProvider
        return GroqProvider()

    # Tanınmayan provider → Groq fallback (ucretsiz, hızlı)
    logger.warning(
        "[AI_RUNTIME] Bilinmeyen AI_PROVIDER='%s' — Groq'a düşülüyor.", provider_name
    )
    from core.ai_provider.groq import GroqProvider
    return GroqProvider()


def provider_name() -> str:
    """Aktif provider adını döner (log/UI için)."""
    from core.config import cfg
    return cfg.ai_provider or "gemini"
