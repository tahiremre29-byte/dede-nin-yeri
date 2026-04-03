"""
DD1 Platform — AI Sohbet Router  (Thin — v3)

Router görevi: HTTP in/out yönetimi.
İş mantığı: services/chat_service.py
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Any

from services.chat_service import process_message

router = APIRouter(prefix="/chat", tags=["AI Asistan"])


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[dict] = None
    history: Optional[list[dict]] = None


class ChatResponse(BaseModel):
    action:                   str
    reply:                    str
    route_to:                 Optional[str]  = None
    design:                   Optional[dict] = None
    questions:                str            = ""
    errors:                   list[str]      = []
    extracted_info:           Optional[dict] = None
    # Standart yeni alanlar
    intent:                   Optional[str]  = None
    confidence:               Optional[float]= None
    extracted_entities:       Optional[dict] = None
    normalized_entities:      Optional[dict] = None
    normalized_panel:         Optional[dict] = None
    user_visible_response:    Optional[str]  = None
    internal_debug_message:   Optional[str]  = None
    # AI mod sinyali — UI göstergesi için
    ai_mode:                  str            = "smart"    # "smart" | "standard"
    ai_error_class:           Optional[str]  = None       # key_invalid|quota|timeout|network|runtime
    # Tezgahtar katmanı
    mode:                     str            = "chat"     # "chat" | "tezgahtar"
    ui_cards:                 Optional[list] = None       # model aday kartları


@router.post("/", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    Serbest metin → chat_service.process_message() → Ses Ustası → ilgili ajan.
    Router hesap veya karar mantığı içermez.
    """
    result = process_message(
        message=req.message,
        context=req.context,
        history=req.history,
    )
    # normalized_panel: extracted_info içindeyse toplevele taşı
    if "normalized_panel" not in result:
        ext = result.get("extracted_info") or {}
        result["normalized_panel"] = ext.get("normalized_panel", {})
        
    # Log the interaction
    from services.history_service import history_db
    if req.session_id:
        history_db.log_message(req.session_id, "user", req.message)
        history_db.log_message(req.session_id, "ai", result.get("reply", ""))
        
    return ChatResponse(**{k: v for k, v in result.items() if k in ChatResponse.model_fields})


@router.post("/route")
def route_only(req: ChatRequest) -> dict:
    """Sadece niyet sınıflama — debug / test. Ajan çağrısı yok."""
    from core.router import quick_route
    agent, intent, conf = quick_route(req.message)
    return {
        "message":    req.message,
        "intent":     intent,
        "confidence": round(float(conf), 3),
        "route_to":   agent,
    }
