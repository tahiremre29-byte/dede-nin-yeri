from fastapi import APIRouter
from pydantic import BaseModel
from services.history_service import history_db

router = APIRouter(prefix="/api/session", tags=["Session"])

class SessionResponse(BaseModel):
    session_id: str
    message: str

class RegisterRequest(BaseModel):
    session_id: str
    name: str
    email: str
    gdpr_consent: bool
    marketing_consent: bool = False

@router.post("/start", response_model=SessionResponse)
@router.get("/start", response_model=SessionResponse) # Provide GET for easy browser testing if needed
async def start_session():
    """
    Ürettiği benzersiz `session_id`'yi frontend'e döner.
    Frontend bu ID'yi localStorage gibi bir yerde saklayıp ardışık 
    chat ve design isteklerine koymalıdır.
    """
    session_id = history_db.start_session(client_info="web_ui_v1")
    return {"session_id": session_id, "message": "Oturum başarıyla oluşturuldu/kaydedildi."}

@router.post("/register")
async def register_session(req: RegisterRequest):
    """Kullanıcı kayıt bilgilerini kaydeder"""
    success = history_db.register_user(req.session_id, req.name, req.email)
    if success:
        return {"status": "success", "message": "Kayıt başarılı."}
    return {"status": "error", "message": "Kayıt işlemi başarısız."}
