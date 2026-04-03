"""
core/observability.py
DD1 Gözlemlenebilirlik — Request/Session Takibi

Her isteğe bir request_id ve session_id atanır.
Ajan geçişleri zaman damgasıyla loglanır.

Kullanım:
    from core.observability import obs_ctx, agent_transition, RequestContext

    ctx = obs_ctx("ses_ustasi", session_id="abc123")
    agent_transition(ctx, from_agent="ses_ustasi", to_agent="kabin_ustasi")
"""
from __future__ import annotations
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("dd1.observability")


# ── Request Context ───────────────────────────────────────────────────────────

@dataclass
class RequestContext:
    request_id:  str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    session_id:  str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    started_at:  str = field(default_factory=lambda: _now())
    current_agent: str = ""
    transitions: list[dict] = field(default_factory=list)

    def elapsed_ms(self) -> float:
        start = datetime.fromisoformat(self.started_at.replace("Z", "+00:00"))
        now   = datetime.now(tz=timezone.utc)
        return (now - start).total_seconds() * 1000


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


# ── Fabrika ────────────────────────────────────────────────────────────────────

def obs_ctx(
    initial_agent: str = "ses_ustasi",
    session_id: str | None = None,
    request_id: str | None = None,
) -> RequestContext:
    """Yeni RequestContext oluştur ve başlangıcı logla."""
    ctx = RequestContext(
        request_id=request_id or uuid.uuid4().hex[:12],
        session_id=session_id or uuid.uuid4().hex[:8],
        current_agent=initial_agent,
    )
    logger.info(
        "[OBS] req=%s session=%s agent=%s started",
        ctx.request_id, ctx.session_id, initial_agent,
    )
    return ctx


# ── Ajan Geçişi ────────────────────────────────────────────────────────────────

def agent_transition(
    ctx: RequestContext,
    from_agent: str,
    to_agent: str,
    packet_type: str = "",
    extra: dict | None = None,
) -> None:
    """
    Ajan geçişini zaman damgasıyla logla ve context'e kaydet.

    Örnek log:
      [TRANSITION] req=a1b2 session=c3d4 ses_ustasi -> kabin_ustasi
                   packet=IntakePacket elapsed=12.3ms
    """
    ts = _now()
    record = {
        "at":          ts,
        "from":        from_agent,
        "to":          to_agent,
        "packet_type": packet_type,
        **(extra or {}),
    }
    ctx.transitions.append(record)
    ctx.current_agent = to_agent

    logger.info(
        "[TRANSITION] req=%s session=%s %s -> %s packet=%s elapsed=%.1fms",
        ctx.request_id, ctx.session_id,
        from_agent, to_agent,
        packet_type,
        ctx.elapsed_ms(),
    )


# ── Hata Maskeleme ─────────────────────────────────────────────────────────────

_ERROR_MAP: dict[str, str] = {
    "AcousticIntegrityError": (
        "Akustik guvenlik siniri asildi — parametreleri kontrol ediniz."
    ),
    "E_IMMUTABLE_VIOLATION": (
        "Uretim asamas\u0131nda akustik veriler degistirilemez."
    ),
    "E_DESIGN_NOT_FOUND": (
        "Tasarim bulunamadi. Once /design/enclosure ile tasarim oluşturun."
    ),
    "E_FILE_GENERATION": (
        "DXF dosyasi uretimi basarisiz. Parametreleri kontrolp ediniz."
    ),
    "ValueError": (
        "Gecersiz parametre. Lutfen girdi degerlerini kontrol ediniz."
    ),
}

_GENERIC_USER_MSG = "Islem tamamlanamadi. Lutfen tekrar deneyiniz."


def user_friendly_error(error_code: str, technical_msg: str = "") -> str:
    """
    Teknik hata kodunu/mesajı kullanıcıya gösterilecek sade mesaja çevirir.
    """
    for key, msg in _ERROR_MAP.items():
        if key in error_code or key in technical_msg:
            return msg
    return _GENERIC_USER_MSG


# ── Akış Özeti ────────────────────────────────────────────────────────────────

def flow_summary(ctx: RequestContext) -> dict:
    """Debug logları ve akış izleme için özet dict."""
    return {
        "request_id":   ctx.request_id,
        "session_id":   ctx.session_id,
        "started_at":   ctx.started_at,
        "elapsed_ms":   round(ctx.elapsed_ms(), 2),
        "transitions":  ctx.transitions,
        "final_agent":  ctx.current_agent,
    }
