"""
routers/monitor.py
Salt Okunur Log/Sistem Veri Saglayicisi (Kanban Panosu Icin)
"""
from fastapi import APIRouter
from pathlib import Path

router = APIRouter(prefix="/api/monitor", tags=["Monitor"])

# Sistem kok dizini (exemiz)
ROOT_DIR = Path(__file__).resolve().parent.parent.parent

LOG_FILES = {
    "dd1_bridge": "bridge_debug.log",
    "telegram": "telegram_log.txt"
}

def fetch_log_lines(filename: Path, n: int = 150) -> list[str]:
    """Log dosyasinin son satirlarini yormadan okur."""
    if not filename.exists():
        return []
    try:
        with open(filename, "rb") as f:
            f.seek(0, 2)
            block_size = max(1024, f.tell() // 5)
            f.seek(max(f.tell() - block_size, 0))
            lines = f.read().decode('utf-8', errors='replace').splitlines()
            return lines[-n:]
    except Exception:
        return []

@router.get("/logs")
def get_system_logs():
    """Kanban panosunda kullanilacak anlik operasyon satirlarini dondurur."""
    results = {}
    for src, fname in LOG_FILES.items():
        results[src] = fetch_log_lines(ROOT_DIR / fname, 200)
    
    return {
        "status": "ok",
        "data": results
    }
