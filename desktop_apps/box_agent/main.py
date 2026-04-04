"""
DD1 Box Engineering Agent — Uygulama Giriş Noktası
"""
import sys
import os
import traceback

# Windows'ta PyInstaller için yol sabitleme
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

LOG_DOSYASI = os.path.join(BASE_DIR, "hata_log.txt")


def _hata_yaz(mesaj: str):
    try:
        with open(LOG_DOSYASI, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"\n{'='*60}\n")
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]\n")
            f.write(mesaj + "\n")
    except Exception:
        pass


def main():
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont
        from PyQt6.QtCore import Qt
        from ui.main_window import AnaPencere
        from config import APP_NAME, APP_VERSION

        # HiDPI desteği
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )

        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        app.setOrganizationName("DD1")

        font = QFont("Segoe UI", 10)
        app.setFont(font)

        pencere = AnaPencere()
        pencere.show()

        _hata_yaz("Uygulama basarıyla başlatıldı.")
        sys.exit(app.exec())

    except Exception as e:
        hata_metni = traceback.format_exc()
        _hata_yaz(f"KRITIK HATA:\n{hata_metni}")
        print(f"HATA: {e}\nDetaylar: {hata_metni}")
        try:
            import tkinter.messagebox as mb
            mb.showerror("DD1 Box Agent — Başlatma Hatası",
                         f"Uygulama başlatılamadı:\n\n{e}\n\nDetaylar için {LOG_DOSYASI} dosyasına bakın.")
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
