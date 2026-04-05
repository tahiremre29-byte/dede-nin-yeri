"""
core/ai_provider/openai.py
OpenAI Provider — openai SDK

BaseAIProvider'dan türer. generate() → AIProviderResponse döner.
Config: OPENAI_API_KEY, OPENAI_MODEL (default: gpt-4o-mini)
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from core.ai_provider.base import BaseAIProvider, AIProviderResponse

logger = logging.getLogger("dd1.ai_provider.openai")


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI GPT sağlayıcısı.

    Config:
        OPENAI_API_KEY   — zorunlu
        OPENAI_MODEL     — default: gpt-4o-mini
        AI_TIMEOUT_SECONDS / AI_RETRY_COUNT
    """
    name = "openai"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model:   Optional[str] = None,
    ):
        from core.config import cfg
        self._cfg     = cfg
        self.model    = model or getattr(cfg, "openai_model", "gpt-4o-mini")
        self._timeout = cfg.ai_timeout_seconds
        self._retries = cfg.ai_retry_count
        self._debug   = cfg.debug
        self._client  = self._build_client(api_key, cfg)
        logger.info("[OPENAI] Başlatıldı — model=%s timeout=%.0fs", self.model, self._timeout)

    # ── Client Kurulum ───────────────────────────────────────────────────────

    def _build_client(self, api_key: Optional[str], cfg):
        try:
            import openai  # type: ignore[import]
        except ImportError as e:
            from core.ai_provider.errors import AIProviderError
            raise AIProviderError(
                "openai paketi bulunamadı. 'pip install openai' ile kur."
            ) from e

        key = api_key or getattr(cfg, "openai_api_key", "")
        if not key:
            from core.ai_provider.errors import AIKeyMissingError
            raise AIKeyMissingError(
                "OPENAI_API_KEY bulunamadı. Ortam değişkeni veya api_key parametresi gerekli."
            )
        return openai.OpenAI(api_key=key, timeout=self._timeout or 30)

    # ── Ana Generate ─────────────────────────────────────────────────────────

    def generate(
        self,
        prompt:        str,
        system_prompt: str   = "",
        temperature:   float = 0.7,
        max_tokens:    int   = 2048,
        **kwargs,
    ) -> AIProviderResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        for attempt in range(1, self._retries + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return self._normalize(resp)

            except Exception as exc:
                from core.ai_provider.errors import classify_exception, AIKeyMissingError, AIKeyInvalidError
                norm = classify_exception(exc)
                if isinstance(norm, (AIKeyMissingError, AIKeyInvalidError)):
                    return self._error_response(exc, self.name, self.model)
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "[OPENAI] Geçici hata (deneme %d/%d): %s — %.0fs bekleniyor",
                    attempt, self._retries, exc, wait,
                )
                if attempt < self._retries:
                    time.sleep(wait)
                    continue
                return self._error_response(exc, self.name, self.model)

        return self._error_response(RuntimeError("Tüm OpenAI denemeleri tükendi"), self.name, self.model)

    def health_check(self) -> bool:
        try:
            resp = self.generate("ping", system_prompt="reply ok", max_tokens=5)
            return resp.ok
        except Exception:
            return False

    # ── Normalize ────────────────────────────────────────────────────────────

    def _normalize(self, resp) -> AIProviderResponse:
        choice  = resp.choices[0]
        text    = choice.message.content or ""
        finish  = (choice.finish_reason or "stop").lower()
        # map openai finish reasons
        if finish not in ("stop", "length", "error", "safety"):
            finish = "stop"
        usage = None
        if resp.usage:
            usage = {
                "prompt_tokens":     resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
                "total_tokens":      resp.usage.total_tokens,
            }
        return AIProviderResponse(
            text=text, finish_reason=finish,
            provider=self.name, model=self.model,
            usage=usage,
            structured_json=self._try_parse_json(text),
        )

    def _try_parse_json(self, text: str):
        import json, re
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
        return None
