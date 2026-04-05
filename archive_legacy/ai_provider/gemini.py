"""
core/ai_provider/gemini.py
Gemini Provider — google-genai SDK

BaseAIProvider'dan türer. generate() → AIProviderResponse döner.
Mevcut ai_adapter.py'deki Gemini mantığını kapsüller.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

from core.ai_provider.base import BaseAIProvider, AIProviderResponse

logger = logging.getLogger("dd1.ai_provider.gemini")


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini AI sağlayıcısı.

    Config:
        GEMINI_API_KEY   — developer mode
        AI_BACKEND_MODE  — "developer" (default) | "vertex"
        GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION — vertex için
        AI_MODEL (gemini_model_name) — model adı
        AI_TIMEOUT_SECONDS / AI_RETRY_COUNT
    """
    name = "gemini"

    def __init__(
        self,
        api_key:  Optional[str] = None,
        model:    Optional[str] = None,
        backend:  Optional[str] = None,
    ):
        from core.config import cfg
        self._cfg      = cfg
        self._backend  = (backend or cfg.ai_backend_mode or "developer").lower()
        self.model     = model or cfg.gemini_model_name or "gemini-2.0-flash"
        self._timeout  = cfg.ai_timeout_seconds
        self._retries  = cfg.ai_retry_count
        self._stream   = cfg.stream_enabled
        self._debug    = cfg.debug
        self._client   = self._build_client(api_key, cfg)
        logger.info(
            "[GEMINI] Başlatıldı — backend=%s model=%s timeout=%.0fs",
            self._backend, self.model, self._timeout,
        )

    # ── Client Kurulum ───────────────────────────────────────────────────────

    def _build_client(self, api_key: Optional[str], cfg) -> Any:
        try:
            from google import genai  # type: ignore[import]
        except ImportError as e:
            from core.ai_provider.errors import AIProviderError
            raise AIProviderError(
                "google-genai paketi bulunamadı. 'pip install google-genai' ile kur."
            ) from e

        if self._backend == "vertex":
            project  = cfg.google_cloud_project
            location = cfg.google_cloud_location
            if not project:
                from core.ai_provider.errors import AIKeyMissingError
                raise AIKeyMissingError("Vertex AI için GOOGLE_CLOUD_PROJECT gerekli.")
            logger.info("[GEMINI] Vertex AI: project=%s location=%s", project, location)
            return genai.Client(vertexai=True, project=project, location=location)

        key = api_key or cfg.gemini_api_key
        if not key:
            from core.ai_provider.errors import AIKeyMissingError
            raise AIKeyMissingError(
                "GEMINI_API_KEY bulunamadı. Ortam değişkeni veya api_key parametresi gerekli."
            )
        try:
            from google.genai import types as _gtypes  # type: ignore[import]
            http_opts = _gtypes.HttpOptions(timeout=int(self._timeout))
            return genai.Client(api_key=key, http_options=http_opts)
        except Exception:
            # Eski SDK sürümlerinde http_options olmayabilir
            return genai.Client(api_key=key)

    # ── Ana Generate ─────────────────────────────────────────────────────────

    def generate(
        self,
        prompt:        str,
        system_prompt: str   = "",
        temperature:   float = 0.7,
        max_tokens:    int   = 2048,
        **kwargs,
    ) -> AIProviderResponse:
        stream = kwargs.get("stream", self._stream)
        tools  = kwargs.get("tools", None)

        for attempt in range(1, self._retries + 1):
            try:
                if stream:
                    return self._generate_stream(prompt, system_prompt, tools, temperature, max_tokens)
                return self._generate_sync(prompt, system_prompt, tools, temperature, max_tokens)
            except Exception as exc:
                from core.ai_provider.errors import classify_exception, AIKeyMissingError, AIKeyInvalidError
                norm = classify_exception(exc)
                # Key hataları retry'sız direkt fall
                if isinstance(norm, (AIKeyMissingError, AIKeyInvalidError)):
                    return self._error_response(exc, self.name, self.model)
                wait = 2 ** (attempt - 1)
                logger.warning(
                    "[GEMINI] Geçici hata (deneme %d/%d): %s — %.0fs bekleniyor",
                    attempt, self._retries, exc, wait,
                )
                if attempt < self._retries:
                    time.sleep(wait)
                    continue
                return self._error_response(exc, self.name, self.model)

        return self._error_response(RuntimeError("Tüm Gemini denemeleri tükendi"), self.name, self.model)

    def health_check(self) -> bool:
        try:
            resp = self.generate("ping", system_prompt="reply ok", max_tokens=5)
            return resp.ok
        except Exception:
            return False

    # ── Dahili ──────────────────────────────────────────────────────────────

    def _generate_sync(self, prompt, system_prompt, tools, temperature, max_tokens) -> AIProviderResponse:
        config = self._build_gen_config(system_prompt, temperature, max_tokens, tools)
        resp   = self._client.models.generate_content(
            model=self.model, contents=prompt, config=config,
        )
        return self._normalize(resp)

    def _generate_stream(self, prompt, system_prompt, tools, temperature, max_tokens) -> AIProviderResponse:
        config = self._build_gen_config(system_prompt, temperature, max_tokens, tools)
        chunks = []
        for chunk in self._client.models.generate_content_stream(
            model=self.model, contents=prompt, config=config,
        ):
            if chunk.text:
                chunks.append(chunk.text)
        text = "".join(chunks)
        return AIProviderResponse(
            text=text, finish_reason="stop",
            provider=self.name, model=self.model,
            structured_json=self._try_parse_json(text),
        )

    def _build_gen_config(self, system_prompt, temperature, max_tokens, tools):
        from google.genai import types  # type: ignore[import]
        kw: dict = {
            "temperature":     temperature,
            "max_output_tokens": max_tokens,
        }
        if system_prompt:
            kw["system_instruction"] = system_prompt
        if tools:
            kw["tools"] = tools
        # NOT: timeout http_options üzerinden client'a uygulanıyor, buraya eklenmez
        return types.GenerateContentConfig(**kw)

    def _normalize(self, resp) -> AIProviderResponse:
        try:
            candidate = resp.candidates[0]
            text = "".join(
                p.text for p in candidate.content.parts
                if hasattr(p, "text") and p.text
            )
            finish = (candidate.finish_reason.name or "stop").lower()
        except Exception:
            text   = getattr(resp, "text", "")
            finish = "stop"
        usage = None
        if hasattr(resp, "usage_metadata") and resp.usage_metadata:
            um = resp.usage_metadata
            usage = {
                "prompt_tokens":     getattr(um, "prompt_token_count", None),
                "completion_tokens": getattr(um, "candidates_token_count", None),
                "total_tokens":      getattr(um, "total_token_count", None),
            }
        if finish in ("recitation", "safety", "block_reason"):
            finish = "safety"
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
