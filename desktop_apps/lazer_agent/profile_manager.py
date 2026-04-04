import json
import os

PROFILES_FILE = os.path.join(os.path.dirname(__file__), "material_profiles.json")

DEFAULT_PROFILES = {
    "MDF": {"kerf_width": 0.15},
    "Plywood": {"kerf_width": 0.18},
    "Pleksi": {"kerf_width": 0.10},
    "Akrilik": {"kerf_width": 0.12},
    "Diger": {"kerf_width": 0.15}
}

class ProfileManager:
    def __init__(self):
        self.profiles = self.load_profiles()

    def load_profiles(self):
        if os.path.exists(PROFILES_FILE):
            try:
                with open(PROFILES_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return DEFAULT_PROFILES.copy()
        return DEFAULT_PROFILES.copy()

    def save_profiles(self):
        try:
            with open(PROFILES_FILE, "w", encoding="utf-8") as f:
                json.dump(self.profiles, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Profil kaydetme hatası: {e}")

    def get_kerf(self, material_name):
        profile = self.profiles.get(material_name, self.profiles["Diger"])
        return profile.get("kerf_width", 0.15)

    def update_kerf(self, material_name, new_kerf):
        if material_name not in self.profiles:
            self.profiles[material_name] = {}
        self.profiles[material_name]["kerf_width"] = round(float(new_kerf), 3)
        self.save_profiles()

    def get_material_list(self):
        return list(self.profiles.keys())
