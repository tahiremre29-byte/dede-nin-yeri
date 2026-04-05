"""
core/ai_adapter.py
DD1 AI Adaptör Katmanı — google-genai SDK İzolasyonu

AMAÇ:
  Tüm AI/LLM çağrılarını tek bir katmanda toplar.
  Ajan dosyaları bu modülü kullanır; google.genai doğrudan import etmez.

CONTRACT:
  Her çağrı sonunda normalize edilmiş AIResponse döner:
    .text           — ham metin yanıtı
    .structured_json — parse edilmiş JSON (opsiyonel)
    .tool_calls     — function/tool calling çıktıları
    .usage_metadata — token/usage bilgileri
    .finish_reason  — "stop" | "safety" | "length" | "error"
    .raw_response   — sadece debug modda

BACKEND:
  developer mode: genai.Client(api_key=...)
  vertex mode:    genai.Client(vertexai=True, project=..., location=...)
  AI_BACKEND_MODE env değişkeniyle seçilir.

DAYANIKLILIK:
  - Timeout: AI_TIMEOUT_SECONDS
  - Retry: AI_RETRY_COUNT + exponential backoff
  - Transient error (503, timeout, rate limit) → retry
  - Validation error → direkt fail (retry yok)
  - Kullanıcıya sade mesaj, loklar detaylı

STREAM:
  STREAM_ENABLED=true ile açılır.
  Stream açık/kapalı fark etmeksizin AIResponse contract aynı.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger("dd1.ai_adapter")

# ── Lazımlı import'lar (geç yükleme ile döngüsel etkileri önlenir) ──────────

def _get_cfg():
    from core.config import cfg
    return cfg


# ── Hata Sınıfları ────────────────────────────────────────────────────────────

class AIAdapterError(Exception):
    """Adaptör seviyesinde kurtarılamaz hata."""

class AITransientError(AIAdapterError):
    """Geçici ağ/API hatası — retry edilebilir."""

class AIValidationError(AIAdapterError):
    """Şema/konfigürasyon hatası — retry edilemez."""


# ── Transient Hata Tespiti ───────────────────────────────────────────────────

_TRANSIENT_CODES = (429, 500, 502, 503, 504)
_TRANSIENT_MESSAGES = (
    "resource exhausted", "service unavailable", "quota exceeded",
    "rate limit", "timeout", "too many requests", "internal error",
    "unavailable",
)

def _is_transient(exc: Exception) -> bool:
    """HTTP kodu veya hata mesajına bakarak geçici hata mı belirler."""
    msg = str(exc).lower()
    if any(t in msg for t in _TRANSIENT_MESSAGES):
        return True
    # google-genai SDK genellikle status_code attribute veya ClientError barındırır
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code in _TRANSIENT_CODES:
        return True
    return False


# ── AIResponse Sözleşmesi ───────────────────────────────────────────────────

@dataclass
class AIResponse:
    """
    Normalize edilmiş AI yanıtı.
    Tüm ajan dosyalarının gördüğü tek ortak çıktı tipi.
    """
    text:             str             = ""
    structured_json:  Optional[dict]  = None
    tool_calls:       list            = field(default_factory=list)
    usage_metadata:   Optional[dict]  = None
    finish_reason:    str             = "stop"   # stop | safety | length | error
    raw_response:     Any             = None      # debug modda saklanır

    @property
    def ok(self) -> bool:
        return self.finish_reason not in ("error", "safety")

    def to_dict(self) -> dict:
        return {
            "text":            self.text,
            "structured_json": self.structured_json,
            "tool_calls":      self.tool_calls,
            "usage_metadata":  self.usage_metadata,
            "finish_reason":   self.finish_reason,
        }


# ── Ana Adaptör ──────────────────────────────────────────────────────────────

class AIAdapter:
    """
    DD1 AI Adaptör — Ajan katmanının tek AI temsilcisi.

    Kullanım:
        adapter = AIAdapter()           # config'den otomatik init
        resp    = adapter.generate(prompt, system_prompt=..., stream=False)
        print(resp.text)

    Developer mode (varsayılan):
        GEMINI_API_KEY gerekli.

    Vertex mode:
        AI_BACKEND_MODE=vertex
        GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION gerekli.
    """

    def __init__(
        self,
        api_key:   Optional[str] = None,
        model:     Optional[str] = None,
        backend:   Optional[str] = None,
    ):
        cfg = _get_cfg()

        self._backend  = (backend  or cfg.ai_backend_mode).lower()
        self._model    = model or cfg.gemini_model_name
        self._timeout  = cfg.ai_timeout_seconds
        self._retries  = cfg.ai_retry_count
        self._stream   = cfg.stream_enabled
        self._debug    = cfg.debug

        self._client = self._build_client(api_key, cfg)
        logger.info(
            "[AI_ADAPTER] Başlatıldı — backend=%s model=%s timeout=%.0fs retry=%d stream=%s",
            self._backend, self._model, self._timeout, self._retries, self._stream,
        )

    # ── Client Init ──────────────────────────────────────────────────────────

    def _build_client(self, api_key: Optional[str], cfg) -> Any:
        """Backend moduna göre google-genai istemcisi başlatır."""
        try:
            from google import genai  # type: ignore[import]
        except ImportError as e:
            raise AIValidationError(
                "google-genai paketi bulunamadı. "
                "'pip install google-genai' ile kur."
            ) from e

        if self._backend == "vertex":
            project  = cfg.google_cloud_project
            location = cfg.google_cloud_location
            if not project:
                raise AIValidationError(
                    "Vertex AI modu için GOOGLE_CLOUD_PROJECT gerekli."
                )
            logger.info(
                "[AI_ADAPTER] Vertex AI modu: project=%s location=%s",
                project, location,
            )
            return genai.Client(vertexai=True, project=project, location=location)

        # Developer mode (varsayılan)
        key = api_key or cfg.gemini_api_key
        if not key:
            raise AIValidationError(
                "GEMINI_API_KEY bulunamadı. "
                "Ortam değişkeni veya api_key parametresi gerekli."
            )
        return genai.Client(api_key=key)

    # ── Sync Generate ────────────────────────────────────────────────────────

    def generate(
        self,
        prompt:        str,
        system_prompt: Optional[str] = None,
        stream:        Optional[bool] = None,
        tools:         Optional[list] = None,
        temperature:   float = 0.7,
        max_tokens:    Optional[int] = None,
    ) -> AIResponse:
        """
        Sync AI çağrısı — provider-agnostic.

        AI_PROVIDER config'e göre GeminiProvider veya OpenAIProvider kullanır.
        Döner: AIResponse (mevcut upstream contract değişmez).
        """
        try:
            from core.ai_runtime import get_provider
            provider = get_provider()
            prov_resp = provider.generate(
                prompt        = prompt,
                system_prompt = system_prompt or "",
                temperature   = temperature,
                max_tokens    = max_tokens or 2048,
                stream        = stream if stream is not None else self._stream,
                tools         = tools,
            )
            # AIProviderResponse → AIResponse (upstream contract)
            return AIResponse(
                text            = prov_resp.text,
                structured_json = prov_resp.structured_json,
                tool_calls      = prov_resp.tool_calls if prov_resp.tool_calls else [],
                usage_metadata  = prov_resp.usage,
                finish_reason   = prov_resp.finish_reason,
                raw_response    = prov_resp.raw_response if self._debug else None,
            )
        except Exception as exc:
            # ai_runtime import hatasında eski Gemini yoluna düş (geçiş güvencesi)
            logger.warning("[AI_ADAPTER] Provider runtime hatası, legacy path: %s", exc)
            return self._error_response(exc)


    # ── Async Generate ───────────────────────────────────────────────────────

    async def agenerate(
        self,
        prompt:        str,
        system_prompt: Optional[str] = None,
        stream:        Optional[bool] = None,
        tools:         Optional[list] = None,
        temperature:   float = 0.7,
        max_tokens:    Optional[int] = None,
    ) -> AIResponse:
        """
        Async AI çağrısı — aynı AIResponse contract.
        google-genai SDK'nın async interface'ini kullanır.
        """
        use_stream = self._stream if stream is None else stream

        for attempt in range(1, self._retries + 1):
            try:
                from google.genai import types  # type: ignore[import]

                config = self._build_gen_config(
                    system_prompt, temperature, max_tokens, tools
                )

                if use_stream:
                    chunks = []
                    async for chunk in await self._client.aio.models.generate_content_stream(
                        model=self._model,
                        contents=prompt,
                        config=config,
                    ):
                        if chunk.text:
                            chunks.append(chunk.text)
                    full_text = "".join(chunks)
                    return AIResponse(
                        text=full_text,
                        structured_json=self._try_parse_json(full_text),
                        finish_reason="stop",
                    )

                resp = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=config,
                )
                return self._normalize_response(resp)

            except AIValidationError:
                raise

            except Exception as exc:
                if _is_transient(exc) and attempt < self._retries:
                    wait = 2 ** (attempt - 1)
                    logger.warning(
                        "[AI_ADAPTER] Async geçici hata (deneme %d/%d): %s — %.0fs",
                        attempt, self._retries, exc, wait,
                    )
                    import asyncio
                    await asyncio.sleep(wait)
                    continue
                logger.error("[AI_ADAPTER] Async FATAL: %s", exc, exc_info=True)
                return self._error_response(exc)

        return self._error_response(RuntimeError("Async denemeler tükendi"))

    # ── Dahili: Sync ─────────────────────────────────────────────────────────

    def _generate_sync(
        self,
        prompt:        str,
        system_prompt: Optional[str],
        tools:         Optional[list],
        temperature:   float,
        max_tokens:    Optional[int],
    ) -> AIResponse:
        config = self._build_gen_config(system_prompt, temperature, max_tokens, tools)
        resp   = self._client.models.generate_content(
            model    = self._model,
            contents = prompt,
            config   = config,
        )
        result = self._normalize_response(resp)
        logger.debug(
            "[AI_ADAPTER] Sync yanıt: finish=%s tokens=%s",
            result.finish_reason,
            result.usage_metadata.get("total_token_count") if result.usage_metadata else "-",
        )
        return result

    def _generate_stream(
        self,
        prompt:        str,
        system_prompt: Optional[str],
        tools:         Optional[list],
        temperature:   float,
        max_tokens:    Optional[int],
    ) -> AIResponse:
        config = self._build_gen_config(system_prompt, temperature, max_tokens, tools)
        chunks: list[str] = []
        last_resp = None

        for chunk in self._client.models.generate_content_stream(
            model    = self._model,
            contents = prompt,
            config   = config,
        ):
            if chunk.text:
                chunks.append(chunk.text)
            last_resp = chunk

        full_text = "".join(chunks)
        logger.debug("[AI_ADAPTER] Stream tamamlandı: %d chunk", len(chunks))

        # Son chunk'tan usage ve finish_reason al
        usage  = self._extract_usage(last_resp) if last_resp else None
        reason = self._extract_finish_reason(last_resp) if last_resp else "stop"

        return AIResponse(
            text             = full_text,
            structured_json  = self._try_parse_json(full_text),
            tool_calls       = self._extract_tool_calls(last_resp) if last_resp else [],
            usage_metadata   = usage,
            finish_reason    = reason,
            raw_response     = last_resp if self._debug else None,
        )

    # ── Dahili: GenerationConfig ─────────────────────────────────────────────

    def _build_gen_config(
        self,
        system_prompt: Optional[str],
        temperature:   float,
        max_tokens:    Optional[int],
        tools:         Optional[list],
    ) -> Any:
        """google.genai.types.GenerateContentConfig oluşturur."""
        try:
            from google.genai import types  # type: ignore[import]
        except ImportError:
            return None  # hatalı olan client zaten _build_client'ta yakalandı

        kwargs: dict = {
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system_instruction"] = system_prompt
        if max_tokens:
            kwargs["max_output_tokens"] = max_tokens
        if tools:
            kwargs["tools"] = tools

        return types.GenerateContentConfig(**kwargs)

    # ── Dahili: Normalize ────────────────────────────────────────────────────

    def _normalize_response(self, resp: Any) -> AIResponse:
        """
        google-genai SDK'sının GenerateContentResponse nesnesini
        AIResponse sözleşmesine dönüştürür.
        """
        try:
            text = resp.text or ""
        except (AttributeError, ValueError):
            # Bazen .text property bozuk response'ta exception atar
            text = ""
            try:
                # Fallback: candidates[0].content.parts[0].text
                text = resp.candidates[0].content.parts[0].text or ""
            except Exception:
                pass

        return AIResponse(
            text             = text.strip(),
            structured_json  = self._try_parse_json(text),
            tool_calls       = self._extract_tool_calls(resp),
            usage_metadata   = self._extract_usage(resp),
            finish_reason    = self._extract_finish_reason(resp),
            raw_response     = resp if self._debug else None,
        )

    def _extract_finish_reason(self, resp: Any) -> str:
        try:
            reason = resp.candidates[0].finish_reason
            # google-genai FinishReason enum veya int olabilir
            reason_str = str(reason).lower()
            if "safety" in reason_str:
                return "safety"
            if "max" in reason_str or "token" in reason_str or "length" in reason_str:
                return "length"
            if "stop" in reason_str or reason_str in ("1", "stop"):
                return "stop"
            return reason_str
        except Exception:
            return "stop"

    def _extract_usage(self, resp: Any) -> Optional[dict]:
        try:
            meta = resp.usage_metadata
            if meta is None:
                return None
            return {
                "prompt_token_count":     getattr(meta, "prompt_token_count", 0),
                "candidates_token_count": getattr(meta, "candidates_token_count", 0),
                "total_token_count":      getattr(meta, "total_token_count", 0),
            }
        except Exception:
            return None

    def _extract_tool_calls(self, resp: Any) -> list:
        """function_calls / tool_uses normalize eder."""
        calls = []
        try:
            for cand in resp.candidates:
                for part in cand.content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc:
                        calls.append({
                            "name": fc.name,
                            "args": dict(fc.args) if fc.args else {},
                        })
        except Exception:
            pass
        return calls

    def _try_parse_json(self, text: str) -> Optional[dict]:
        """Metinde JSON blok varsa parse eder."""
        if not text:
            return None
        # ```json ... ``` veya düz JSON
        stripped = text.strip()
        start = stripped.find("{")
        end   = stripped.rfind("}")
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(stripped[start: end + 1])
        except json.JSONDecodeError:
            return None

    def _classify_error(self, exc: Exception) -> tuple[str, str]:
        """
        Exception tipine göre (log_reason, user_message) çifti döner.
        log_reason  → backend log için teknik sınıf adı
        user_message → kullanıcıya gösterilen sade Türkçe mesaj
        """
        msg = str(exc).lower()
        # 1. Key eksik / geçersiz / süresi dolmuş
        if any(k in msg for k in ("api key", "api_key", "invalid_argument",
                                   "api key expired", "key expired", "api_key_invalid")):
            return "key_invalid", (
                "Akıllı mod şu an kullanılamıyor. Standart modda devam ediyoruz."
            )
        # 2. Kota / rate limit
        if any(k in msg for k in ("quota", "resource exhausted", "rate limit",
                                   "too many requests", "429")):
            return "quota_exceeded", (
                "Akıllı mod yoğunluk nedeniyle geçici devre dışı. "
                "Standart modla devam edebiliriz."
            )
        # 3. Timeout
        if any(k in msg for k in ("timeout", "timed out", "deadline")):
            return "timeout", (
                "Akıllı mod yanıt vermedi (zaman aşımı). Standart modla devam ediyoruz."
            )
        # 4. Network / transport
        if any(k in msg for k in ("connection", "transport", "network",
                                   "ssl", "socket", "connect")):
            return "network", (
                "Akıllı mod şu an erişilemiyor. Standart modla devam ediyoruz."
            )
        # 5. Generic AI runtime
        return "runtime", (
            "Akıllı mod şu an kullanılamıyor. Standart modla devam ediyoruz."
        )

    def _error_response(self, exc: Exception) -> AIResponse:
        """Hata durumunda kullanıcıya sade mesaj, loglara detay."""
        log_reason, user_msg = self._classify_error(exc)
        logger.error(
            "[AI_ADAPTER] Hata sınıfı=%s | %s: %s",
            log_reason, type(exc).__name__, exc, exc_info=True,
        )
        return AIResponse(
            text          = user_msg,
            finish_reason = "error",
            structured_json = {
                "ai_mode":        "standard",   # downstream'e fallback sinyali
                "ai_error_class": log_reason,   # key_invalid | quota | timeout | network | runtime
            },
        )



# ── Singleton (lazy) ─────────────────────────────────────────────────────────

_adapter_instance: Optional[AIAdapter] = None

def get_adapter(
    api_key: Optional[str] = None,
    model:   Optional[str] = None,
    backend: Optional[str] = None,
) -> AIAdapter:
    """
    Paylaşımlı adaptör singleton'u döner.
    İlk çağrıda başlatılır; sonrasında aynı nesne kullanılır.

    Testlerde farklı parametrelerle override yapmak için
    reset_adapter() çağır.
    """
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = AIAdapter(api_key=api_key, model=model, backend=backend)
    return _adapter_instance


def reset_adapter() -> None:
    """Test ve yeniden yapılandırma için singleton'u sıfırlar."""
    global _adapter_instance
    _adapter_instance = None
    logger.info("[AI_ADAPTER] Singleton sıfırlandı.")
