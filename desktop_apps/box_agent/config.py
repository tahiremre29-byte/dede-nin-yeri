"""
DD1 Box Engineering Agent — Yapılandırma & Mühendislik Sabitleri
"""
import os
from pathlib import Path

# ─── Uygulama ───
APP_NAME    = "DD1 Box Engineering Agent"
APP_VERSION = "1.0.0"

# ─── API ───
API_BASE_URL = os.getenv("DD1_API_URL", "http://localhost:8000")
DD1_PREMIUM_KEY = os.getenv("DD1_PREMIUM_KEY", "premium-dev")

# ─── Dizinler ───
BASE_DIR    = Path(__file__).parent
OUTPUT_DIR  = BASE_DIR / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─── OpenAI (Usta Tavsiyesi için opsiyonel) ───
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-4o"

# ─── Fizik Sabitleri ───
SOUND_SPEED_MS   = 344.0   # m/s (20°C havada ses hızı)
AIR_DENSITY      = 1.18    # kg/m³
MAX_PORT_VELOCITY = 17.0   # m/s (port gürültüsü eşiği)

# ─── Ampirik Kabin Hacmi Tablosu (litre) ─── {inch: {amaç: (min, max)}}
EMPIRICAL_VB = {
    8:  {"SPL": (18, 25), "SQL": (22, 30), "Günlük Bass": (25, 35)},
    10: {"SPL": (30, 45), "SQL": (40, 55), "Günlük Bass": (45, 60)},
    12: {"SPL": (55, 75), "SQL": (65, 85), "Günlük Bass": (60, 80)},
    15: {"SPL": (90, 120), "SQL": (110, 140), "Günlük Bass": (100, 130)},
    18: {"SPL": (150, 200), "SQL": (180, 250), "Günlük Bass": (170, 220)},
}

# ─── Araç Tipi → Tuning Frekansı Aralığı (Hz) ───
VEHICLE_TUNING = {
    "Sedan":    (35, 40),
    "Hatchback":(38, 44),
    "SUV":      (32, 38),
    "Pickup":   (30, 36),
    "Van":      (28, 34),
}

# ─── Araç Tipi → Cabin Gain (dB tahmini) ───
CABIN_GAIN = {
    "Sedan":    8,
    "Hatchback":6,
    "SUV":      5,
    "Pickup":   4,
    "Van":      10,
}

# ─── Kullanım Amacı → Port Alanı Katsayısı (cm²/L) ───
PORT_AREA_COEFF = {
    "SPL":         58,
    "SQL":         50,
    "Günlük Bass": 46,
}

# ─── Empirical Sürücü Sd Tahminleri (cm²) ───
EMPIRICAL_SD = {
    8:  200,
    10: 340,
    12: 490,
    15: 855,
    18: 1320,
}

# ─── Empirical Xmax Tahminleri (mm) ───
EMPIRICAL_XMAX = {
    8:  8,
    10: 12,
    12: 15,
    15: 20,
    18: 25,
}

# ─── Empirical Fs Tahminleri (Hz) ───
EMPIRICAL_FS = {
    8:  45,
    10: 38,
    12: 32,
    15: 25,
    18: 20,
}
