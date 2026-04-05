"""
DD1 Platform — Fiziksel Sabitler ve Ampirik Veriler
"""

SOUND_SPEED_MS = 344.0   # m/s (20°C havada ses hızı)
AIR_DENSITY    = 1.18    # kg/m³
MAX_PORT_VELOCITY = 17.0 # m/s (port gürültüsü eşiği)

# ─── Ampirik Kabin Hacmi Tablosu (litre) ─── {inch: {amaç: (min, max)}}
EMPIRICAL_VB = {
    8:  {"SPL": (18, 25), "SQL": (22, 30), "Günlük Bass": (25, 35)},
    10: {"SPL": (30, 45), "SQL": (35, 50), "Günlük Bass": (40, 55)},
    12: {"SPL": (45, 60), "SQL": (50, 65), "Günlük Bass": (45, 55)},
    15: {"SPL": (80, 100), "SQL": (90, 115), "Günlük Bass": (85, 110)},
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

# ─── Empirical Sürücü Verileri ───
EMPIRICAL_SD = {8: 200, 10: 340, 12: 490, 15: 855, 18: 1320}
EMPIRICAL_XMAX = {8: 8, 10: 12, 12: 15, 15: 20, 18: 25}
EMPIRICAL_FS = {8: 45, 10: 38, 12: 32, 15: 25, 18: 20}
