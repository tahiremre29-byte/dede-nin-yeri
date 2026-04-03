"""
DD1 Platform — FastAPI Ana Uygulama
"""
import sys
from pathlib import Path

# Proje kökünü path'e ekle
sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse


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

from routers import design, woofers, chat, feedback, tool_bridge, knowledge, session, monitor

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="DD1 Platform API",
    description="Quantum Ses Sistemleri Yönetim Platformu",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Tum erisimlere izin veren CORS (Masaustunden HTML acmak icin sart)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routerları bağla
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

@app.get("/api/config/features", tags=["Config"])
def get_features():
    from core.config import cfg
    return {
        "auth_anonymous_mode": cfg.auth_anonymous_mode,
        "auth_registration_required": cfg.auth_registration_required,
        "auth_consent_screens": cfg.auth_consent_screens,
        "history_tracking_enabled": cfg.history_tracking_enabled
    }


# Dijital Atölye — Statik Dosyalar (DDSound Web)
# Mount işlemi tüm API endpointlerinden sonra yapılmalı ki onları ezmesin.
_STATIC = Path(__file__).parent.parent / "ddsound_web"
if _STATIC.exists():
    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="web_root")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=9000, reload=True)
