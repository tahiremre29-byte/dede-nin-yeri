"""
DD1 Platform — FastAPI Ana Uygulama
"""
import sys
import os
from pathlib import Path

# Proje kökünü path'e ekle
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


# .env dosyasını yükle — python-dotenv varsa onu kullan, yoksa elle oku
def _load_env():
    from pathlib import Path
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    try:
        from dotenv import load_dotenv
        load_dotenv(dotenv_path=env_path, override=True)
        return
    except ImportError:
        pass
    # python-dotenv kurulu değilse manuel oku
    import os
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                os.environ[key] = val  # override=True — her zaman .env kazanır

_load_env()

_PUBLIC_BETA_MODE = os.environ.get("DD1_PUBLIC_BETA_MODE", "false").strip().lower() in {
    "1", "true", "yes", "on",
}

from routers import public_beta
if not _PUBLIC_BETA_MODE:
    from routers import design, woofers, chat, feedback, tool_bridge, knowledge, session, monitor

app = FastAPI(
    title="DD1 Platform API",
    description="Quantum Ses Sistemleri Yönetim Platformu",
    version="1.0.0",
    docs_url=None if _PUBLIC_BETA_MODE else "/docs",
    redoc_url=None if _PUBLIC_BETA_MODE else "/redoc",
    openapi_url=None if _PUBLIC_BETA_MODE else "/openapi.json",
)

# Public beta ayni origin'den calisir. Ayri bir on yuz kullanilacaksa izinli
# origin'ler DD1_ALLOWED_ORIGINS ile virgulle ayrilarak tanimlanir.
_allowed_origins = [
    item.strip()
    for item in os.environ.get(
        "DD1_ALLOWED_ORIGINS",
        "http://127.0.0.1:9000,http://localhost:9000",
    ).split(",")
    if item.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST"] if _PUBLIC_BETA_MODE else ["*"],
    allow_headers=["Content-Type", "X-API-Key", "X-Admin-Key"],
)

if _PUBLIC_BETA_MODE:
    @app.middleware("http")
    async def public_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; base-uri 'none'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response

# Halka acik site her modda dar API'yi kullanir. Yonetim ve eski istemci
# endpoint'leri yalniz public-beta modu kapaliyken yuklenir.
app.include_router(public_beta.router)
if not _PUBLIC_BETA_MODE:
    app.include_router(session.router)
    app.include_router(design.router)
    app.include_router(woofers.router)
    app.include_router(chat.router)
    app.include_router(feedback.router)
    app.include_router(tool_bridge.router)
    app.include_router(knowledge.router)
    app.include_router(monitor.router)

# Statik Dosyalar (En Sona Taşındı)


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}

if not _PUBLIC_BETA_MODE:
    @app.get("/api/config/features", tags=["Config"])
    def get_features():
        from core.config import cfg
        return {
            "auth_anonymous_mode": cfg.auth_anonymous_mode,
            "auth_registration_required": cfg.auth_registration_required,
            "auth_consent_screens": cfg.auth_consent_screens,
            "history_tracking_enabled": cfg.history_tracking_enabled
        }


# DD1 Halka Açık Beta — gerçek hesap motoruyla aynı origin'de servis edilir.
# Mount işlemi tüm API endpointlerinden sonra yapılmalı ki onları ezmesin.
_STATIC = Path(__file__).resolve().parent / "public_beta"
app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="web_root")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
