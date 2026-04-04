"""
DD1 Box Engineering Agent — PyQt6 Ana Pencere
Parametre girişi, hesaplama, sonuç gösterimi, SVG/PDF çıktı.
"""
import os
import sys
import threading
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QTextEdit, QPushButton, QComboBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QTabWidget, QFrame, QMessageBox, QStatusBar,
    QApplication, QCheckBox, QScrollArea, QFileDialog, QLineEdit,
    QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtSvgWidgets import QSvgWidget

from config import APP_NAME, APP_VERSION, OUTPUT_DIR


# ─────────────────────────────────────────────
# Worker Thread — hesaplamaları arka planda çalıştırır
# ─────────────────────────────────────────────

class HesapWorker(QThread):
    ilerleme = pyqtSignal(str)
    tamamlandi = pyqtSignal(dict)
    hata = pyqtSignal(str)

    def __init__(self, params: dict):
        super().__init__()
        self.params = params

    def run(self):
        try:
            self.ilerleme.emit("🌐 DD1 Platform API'ye bağlanılıyor...")
            from services.api_client import ApiClient
            
            # API isteği gönder
            self.ilerleme.emit("⚙️ Hesaplama motoru çalıştırılıyor...")
            response = ApiClient.calculate_enclosure(self.params)
            
            # Sonuçları işle
            design_id = response["design_id"]
            self.ilerleme.emit(f"✅ Tasarım #{design_id} üretildi.")
            
            # SVG ve PDF'i yerel dizine indir/kopyala simülasyonu 
            # (API şu an local olduğu için URL'leri direkt kullanabiliriz veya ilerde download eklenebilir)
            # Şimdilik server çıktısı local temp dizininde olduğu için direkt yolları kullanacağız.
            # NOT: Bu kısım API production olduğunda download service ile değiştirilecek.
            
            # Basit Mock: API verilerinden local paths üret (Şimdilik API local temp kullanıyor)
            import tempfile
            temp_dir = Path(tempfile.gettempdir()) / "dd1_files"
            svg_path = str(temp_dir / f"{design_id}.svg")
            pdf_path = str(temp_dir / f"{design_id}.pdf") # Report generator ilerde eklenebilir

            # Teknik rapor metnini oluştur (Server'dan gelen verilerle)
            self.tamamlandi.emit(response)

        except Exception as e:
            import traceback
            hata_mesaji = f"Sunucu hatası: {str(e)}"
            if "ConnectionError" in traceback.format_exc():
                hata_mesaji = "DD1 Platform API sunucusuna bağlanılamadı. Lütfen sunucunun çalıştığından emin olun."
            self.hata.emit(f"{hata_mesaji}\n\n{traceback.format_exc()}")


# ─────────────────────────────────────────────
# Ana Pencere
# ─────────────────────────────────────────────

class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self._ui_yukle()

    def _ui_yukle(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(1200, 800)
        self.resize(1350, 900)

        merkez = QWidget()
        self.setCentralWidget(merkez)
        ana = QVBoxLayout(merkez)
        ana.setContentsMargins(0, 0, 0, 0)
        ana.setSpacing(0)

        # Başlık şeridi
        self._baslik_seridi(ana)

        # İçerik — yatay splitter
        icerik = QWidget()
        icerik_l = QHBoxLayout(icerik)
        icerik_l.setContentsMargins(12, 12, 12, 12)
        icerik_l.setSpacing(12)
        ana.addWidget(icerik, 1)

        # Sol: giriş formu
        sol = self._sol_panel()
        icerik_l.addWidget(sol, 38)

        # Sağ: sonuç tabları
        sag = self._sag_panel()
        icerik_l.addWidget(sag, 62)

        # Durum çubuğu
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(f"{APP_NAME} v{APP_VERSION} — Hazır")

        self.setStyleSheet(STIL)

    # ─── Başlık ───────────────────────────────────────────────────────────────

    def _baslik_seridi(self, duzen):
        frame = QFrame()
        frame.setObjectName("baslik_frame")
        frame.setFixedHeight(64)
        h = QHBoxLayout(frame)
        h.setContentsMargins(20, 0, 20, 0)

        ikon = QLabel("🔊")
        ikon.setFont(QFont("Segoe UI Emoji", 26))
        h.addWidget(ikon)

        v = QVBoxLayout()
        v.setSpacing(0)
        lbl1 = QLabel(APP_NAME)
        lbl1.setObjectName("baslik_lbl")
        lbl2 = QLabel("Mühendis gibi hesapla. Usta gibi üret.")
        lbl2.setObjectName("alt_lbl")
        v.addWidget(lbl1)
        v.addWidget(lbl2)
        h.addLayout(v)
        h.addStretch()
        duzen.addWidget(frame)

    # ─── Sol Panel — Giriş Formu ─────────────────────────────────────────────

    def _sol_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sol_panel")

        scroll = QScrollArea()
        scroll.setWidget(panel)
        scroll.setWidgetResizable(True)
        scroll.setObjectName("scroll_area")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # ── Temel Bilgiler ────────────────────────────────────────────────────
        grp1 = QGroupBox("① TEMEL BİLGİLER")
        grp1.setObjectName("grup_kutu")
        g1 = QGridLayout(grp1)

        g1.addWidget(QLabel("Subwoofer Çapı:"), 0, 0)
        self.diameter_cb = QComboBox()
        self.diameter_cb.addItems(['8"', '10"', '12"', '15"', '18"'])
        self.diameter_cb.setCurrentIndex(2)
        g1.addWidget(self.diameter_cb, 0, 1)

        g1.addWidget(QLabel("RMS Güç (W):"), 1, 0)
        self.rms_spin = QSpinBox()
        self.rms_spin.setRange(50, 10000)
        self.rms_spin.setValue(500)
        self.rms_spin.setSingleStep(50)
        g1.addWidget(self.rms_spin, 1, 1)

        g1.addWidget(QLabel("Araç Tipi:"), 2, 0)
        self.vehicle_cb = QComboBox()
        self.vehicle_cb.addItems(["Sedan", "Hatchback", "SUV", "Pickup", "Van"])
        g1.addWidget(self.vehicle_cb, 2, 1)

        g1.addWidget(QLabel("Kullanım Amacı:"), 3, 0)
        self.purpose_cb = QComboBox()
        self.purpose_cb.addItems(["SPL", "SQL", "Günlük Bass"])
        g1.addWidget(self.purpose_cb, 3, 1)

        g1.addWidget(QLabel("Malzeme Kalınlığı (mm):"), 4, 0)
        self.thickness_spin = QDoubleSpinBox()
        self.thickness_spin.setRange(9, 36)
        self.thickness_spin.setValue(18)
        self.thickness_spin.setSingleStep(0.5)
        g1.addWidget(self.thickness_spin, 4, 1)

        g1.addWidget(QLabel("Bas nasıl olsun?"), 5, 0)
        self.bass_char_cb = QComboBox()
        self.bass_char_cb.addItems([
            "Müzik Temiz Olsun",
            "Koltuğu Yumruklasın",
            "Yeri Titret",
            "Camları Sallayalım",
            "Mahalle Duysun"
        ])
        g1.addWidget(self.bass_char_cb, 5, 1)

        g1.addWidget(QLabel("Subwoofer hangi yöne baksın?"), 6, 0)
        self.sub_dir_cb = QComboBox()
        self.sub_dir_cb.addItems([
            "Arkaya baksın",
            "Öne baksın",
            "Yukarı baksın"
        ])
        g1.addWidget(self.sub_dir_cb, 6, 1)

        layout.addWidget(grp1)

        # ── T/S Parametreleri (Opsiyonel) ─────────────────────────────────────
        grp2 = QGroupBox("② T/S PARAMETRELERİ (Opsiyonel)")
        grp2.setObjectName("grup_kutu")
        g2 = QGridLayout(grp2)

        self.ts_check = QCheckBox("T/S parametrelerini kullan")
        self.ts_check.setObjectName("ts_check")
        self.ts_check.toggled.connect(self._ts_toggle)
        g2.addWidget(self.ts_check, 0, 0, 1, 2)

        ts_fields = [
            ("Fs (Hz):",   "fs_spin",   10, 200,  32,  0.1),
            ("Qts:",       "qts_spin",  0.1, 2.0, 0.45, 0.01),
            ("Vas (L):",   "vas_spin",  1, 500,   60,   1),
            ("Sd (cm²):",  "sd_spin",   50, 3000, 490,  10),
            ("Xmax (mm):", "xmax_spin", 1, 100,   15,   0.5),
            ("Re (Ω):",    "re_spin",   0.5, 20,  3.5,  0.1),
        ]
        self._ts_widgets = []
        for i, (label, attr, mn, mx, default, step) in enumerate(ts_fields, 1):
            lbl = QLabel(label)
            spin = QDoubleSpinBox()
            spin.setRange(mn, mx)
            spin.setValue(default)
            spin.setSingleStep(step)
            spin.setEnabled(False)
            setattr(self, attr, spin)
            g2.addWidget(lbl, i, 0)
            g2.addWidget(spin, i, 1)
            self._ts_widgets.extend([lbl, spin])

        layout.addWidget(grp2)

        # ── Hesapla Butonu ────────────────────────────────────────────────────
        self.calc_btn = QPushButton("🔊  HESAPLA")
        self.calc_btn.setObjectName("hesapla_btn")
        self.calc_btn.setFixedHeight(52)
        self.calc_btn.clicked.connect(self._hesapla)
        layout.addWidget(self.calc_btn)

        self.progress_lbl = QLabel("")
        self.progress_lbl.setObjectName("ilerleme_lbl")
        self.progress_lbl.setWordWrap(True)
        layout.addWidget(self.progress_lbl)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setObjectName("progress_bar")
        layout.addWidget(self.progress_bar)

        layout.addStretch()
        return scroll

    # ─── Sağ Panel — Sonuçlar ─────────────────────────────────────────────────

    def _sag_panel(self) -> QWidget:
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("sonuc_tab")

        # Tab 1 — Teknik Rapor
        self.rapor_kutu = QTextEdit()
        self.rapor_kutu.setReadOnly(True)
        self.rapor_kutu.setObjectName("sonuc_kutu")
        self.rapor_kutu.setPlaceholderText(
            "Hesaplama sonuçları burada görünecek...\n\n"
            "← Sol taraftan parametreleri girin ve HESAPLA butonuna basın."
        )
        self.tab_widget.addTab(self.rapor_kutu, "📊 Sonuçlar")

        # Tab 2 — SVG Çizim
        self.svg_container = QWidget()
        svg_layout = QVBoxLayout(self.svg_container)
        self.svg_widget = QSvgWidget()
        self.svg_widget.setMinimumSize(600, 400)
        svg_layout.addWidget(self.svg_widget)
        self.tab_widget.addTab(self.svg_container, "✏️ Teknik Çizim")

        # Tab 3 — Usta Tavsiyesi
        self.tavsiye_kutu = QTextEdit()
        self.tavsiye_kutu.setReadOnly(True)
        self.tavsiye_kutu.setObjectName("sonuc_kutu")
        self.tavsiye_kutu.setPlaceholderText("Usta tavsiyesi burada görünecek...")
        self.tab_widget.addTab(self.tavsiye_kutu, "🔧 Usta Tavsiyesi")

        # Panel Listesi Tab
        self.panel_kutu = QTextEdit()
        self.panel_kutu.setReadOnly(True)
        self.panel_kutu.setObjectName("sonuc_kutu")
        self.panel_kutu.setPlaceholderText("Panel ölçü listesi burada görünecek...")
        self.tab_widget.addTab(self.panel_kutu, "📐 Panel Listesi")

        # Wrapper
        wrapper = QFrame()
        wrapper.setObjectName("sag_panel")
        wl = QVBoxLayout(wrapper)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(8)

        # Üst: başlık + indirme butonları
        ust = QHBoxLayout()
        baslik = QLabel("HESAP SONUÇLARI")
        baslik.setObjectName("panel_baslik")
        ust.addWidget(baslik)
        ust.addStretch()

        self.pdf_btn = QPushButton("📄 PDF Aç")
        self.pdf_btn.setObjectName("indirme_btn")
        self.pdf_btn.setEnabled(False)
        self.pdf_btn.clicked.connect(self._pdf_ac)
        ust.addWidget(self.pdf_btn)

        self.svg_btn = QPushButton("✏️ SVG Aç")
        self.svg_btn.setObjectName("indirme_btn")
        self.svg_btn.setEnabled(False)
        self.svg_btn.clicked.connect(self._svg_ac)
        ust.addWidget(self.svg_btn)

        self.folder_btn = QPushButton("📁 Klasör Aç")
        self.folder_btn.setObjectName("indirme_btn_kucuk")
        self.folder_btn.clicked.connect(self._klasor_ac)
        ust.addWidget(self.folder_btn)

        wl.addLayout(ust)
        wl.addWidget(self.tab_widget, 1)
        return wrapper

    # ─── Olaylar ──────────────────────────────────────────────────────────────

    def _ts_toggle(self, checked: bool):
        for w in self._ts_widgets:
            w.setEnabled(checked)

    def _hesapla(self):
        diameter_map = {0: 8, 1: 10, 2: 12, 3: 15, 4: 18}
        params = {
            "diameter": diameter_map[self.diameter_cb.currentIndex()],
            "rms": self.rms_spin.value(),
            "vehicle": self.vehicle_cb.currentText(),
            "purpose": self.purpose_cb.currentText(),
            "thickness": self.thickness_spin.value(),
            "bass_char": self.bass_char_cb.currentText(),
            "sub_dir": self.sub_dir_cb.currentText(),
        }

        if self.ts_check.isChecked():
            params.update({
                "fs": self.fs_spin.value(),
                "qts": self.qts_spin.value(),
                "vas": self.vas_spin.value(),
                "sd": self.sd_spin.value(),
                "xmax": self.xmax_spin.value(),
                "re": self.re_spin.value(),
            })
        else:
            params.update({"fs": 0, "qts": 0, "vas": 0, "sd": 0, "xmax": 0, "re": 0})

        # UI kilitle
        self.calc_btn.setEnabled(False)
        self.calc_btn.setText("⏳ Hesaplanıyor...")
        self.progress_bar.setVisible(True)
        self.progress_lbl.setText("🔄 Başlatılıyor...")
        self.rapor_kutu.clear()
        self.tavsiye_kutu.clear()
        self.panel_kutu.clear()

        # Worker
        self.worker = HesapWorker(params)
        self.worker.ilerleme.connect(self._ilerleme)
        self.worker.tamamlandi.connect(self._bitti)
        self.worker.hata.connect(self._hata)
        self.worker.start()

    def _ilerleme(self, msg):
        self.progress_lbl.setText(msg)
        self.status.showMessage(msg)

    def _bitti(self, res: dict):
        self._ui_ac()
        
        # ── Sonuçlar Tab ──────────────────────────────────────────────────────
        vel_ok = res["port_velocity_ms"] < 17
        rapor = f"""{'=' * 60}
  {res['mode']}
{'=' * 60}

  KABiN HESAP SONUCLARI
  Net Kabin Hacmi:     {res['net_volume_l']} L
  Tuning Frekansi:     {res['tuning_hz']} Hz
  -3 dB Alt Frekans:   {res['f3_hz']} Hz
  Port Uzunlugu:       {res['port']['length_mm'] / 10.0} cm

  AKUSTIK ANALIZ
  Cone Excursion:      {res['cone_excursion_mm']} mm
  Port Hava Hizi:      {res['port_velocity_ms']} m/s {'OK' if vel_ok else 'YUKSEK!'}
  Tahmini Tepe SPL:    {res['peak_spl_db']} dB
  Group Delay:         {res['group_delay_ms']} ms

  Dış Genişlik:        {res['dimensions']['w_mm']} mm
  Dış Yükseklik:       {res['dimensions']['h_mm']} mm
  Dış Derinlik:        {res['dimensions']['d_mm']} mm

{'=' * 60}
  DD1 AKUSTİK TAVSİYESİ
{'=' * 60}
  {res['acoustic_advice']}

  {res['expert_comment']}
"""
        if res.get("notes"):
            rapor += "\n  NOTLAR\n"
            for n in res["notes"]:
                rapor += f"  * {n}\n"

        self.rapor_kutu.setPlainText(rapor)

        # ── SVG Tab ───────────────────────────────────────────────────────────
        # NOT: API local makinada çalıştığı için temp path'ten SVG'yi yüklüyoruz.
        import tempfile
        temp_dir = Path(tempfile.gettempdir()) / "dd1_files"
        svg_path = str(temp_dir / f"{res['design_id']}.svg")
        
        if os.path.exists(svg_path):
            self.svg_widget.load(svg_path)
            self.svg_btn.setEnabled(True)
            self._svg_path = svg_path

        # ── Usta Tavsiyesi Tab ────────────────────────────────────────────────
        self.tavsiye_kutu.setPlainText(res.get("acoustic_advice", ""))

        # ── Panel Listesi Tab ─────────────────────────────────────────────────
        panel_text = f"{'═'*50}\n  PANEL ÖLÇÜ LİSTESİ (Sunucudan Gelen)\n{'═'*50}\n\n"
        for p in res.get("panel_list", []):
            note = f" — {p['note']}" if p.get('note') else ""
            panel_text += f"  [{p['qty']}x] {p['name']:.<20s} {p['w']} × {p['h']} mm{note}\n"
        
        self.panel_kutu.setPlainText(panel_text)

        # ── PDF ───────────────────────────────────────────────────────────────
        self.pdf_btn.setEnabled(False)

        self.progress_lbl.setText("✅ Hesaplama tamamlandı!")
        self.status.showMessage(
            f"✅ {res['mode']} — {res['net_volume_l']}L | {res['tuning_hz']}Hz | SPL {res['peak_spl_db']}dB"
        )

    def _hata(self, msg):
        self._ui_ac()
        self.rapor_kutu.setPlainText(f"❌ HATA:\n\n{msg}")
        self.progress_lbl.setText("❌ Hata oluştu")
        self.status.showMessage("Hata!")

    def _ui_ac(self):
        self.calc_btn.setEnabled(True)
        self.calc_btn.setText("🔊  HESAPLA")
        self.progress_bar.setVisible(False)

    def _pdf_ac(self):
        if hasattr(self, "_pdf_path"):
            os.startfile(self._pdf_path)

    def _svg_ac(self):
        if hasattr(self, "_svg_path"):
            os.startfile(self._svg_path)

    def _klasor_ac(self):
        os.startfile(str(OUTPUT_DIR))


# ─────────────────────────────────────────────
# QSS Stil — Koyu Teknik Tema
# ─────────────────────────────────────────────

STIL = """
QMainWindow, QWidget {
    background-color: #0f1923;
    color: #e2e8f0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

#baslik_frame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a2744, stop:1 #0f1923);
    border-bottom: 2px solid #f97316;
}

#baslik_lbl {
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
}

#alt_lbl {
    font-size: 11px;
    color: #94a3b8;
}

#sol_panel, #sag_panel {
    background-color: #131f2e;
    border-radius: 10px;
    padding: 4px;
}

#scroll_area {
    background-color: transparent;
    border: none;
}

#grup_kutu {
    border: 1px solid #1e3a5f;
    border-radius: 8px;
    font-weight: bold;
    color: #f97316;
    padding: 8px;
    margin-top: 6px;
}
#grup_kutu::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
}

QLabel {
    font-size: 12px;
}

QComboBox, QSpinBox, QDoubleSpinBox {
    background-color: #1a2744;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 12px;
    min-height: 26px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #1a2744;
    color: #e2e8f0;
    selection-background-color: #f97316;
}

#hesapla_btn {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ea580c, stop:1 #f97316);
    color: white;
    border: none;
    border-radius: 8px;
    font-size: 16px;
    font-weight: bold;
    letter-spacing: 1px;
}
#hesapla_btn:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #f97316, stop:1 #fb923c);
}
#hesapla_btn:disabled { background-color: #374151; color: #6b7280; }

#indirme_btn {
    background-color: #065f46;
    color: #a7f3d0;
    border: 1px solid #059669;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
}
#indirme_btn:hover { background-color: #059669; color: white; }
#indirme_btn:disabled { background-color: #1f2937; color: #4b5563; border-color: #374151; }

#indirme_btn_kucuk {
    background-color: #1e3a5f;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
}

QTextEdit {
    background-color: #0d1b2a;
    color: #e2e8f0;
    border: 1px solid #1e3a5f;
    border-radius: 6px;
    padding: 8px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}

#sonuc_kutu {
    background-color: #0a1628;
    font-size: 12px;
}

#ilerleme_lbl {
    color: #f97316;
    font-size: 12px;
    font-style: italic;
}

#panel_baslik {
    font-size: 14px;
    font-weight: bold;
    color: #f97316;
    padding: 4px 0;
}

QTabWidget::pane {
    border: 1px solid #1e3a5f;
    border-radius: 6px;
    background-color: #0a1628;
}
QTabBar::tab {
    background: #131f2e;
    color: #94a3b8;
    border: 1px solid #1e3a5f;
    border-bottom: none;
    padding: 8px 16px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-size: 12px;
}
QTabBar::tab:selected {
    background: #1e3a5f;
    color: #f97316;
    font-weight: bold;
}

QCheckBox {
    spacing: 8px;
    font-size: 12px;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
}

QProgressBar {
    background-color: #1e3a5f;
    border: 1px solid #f97316;
    border-radius: 4px;
    height: 6px;
}
QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #ea580c, stop:1 #f97316);
    border-radius: 4px;
}

QScrollBar:vertical {
    background-color: #0f1923;
    width: 10px;
}
QScrollBar::handle:vertical {
    background-color: #f97316;
    border-radius: 5px;
    min-height: 30px;
}

QStatusBar {
    background-color: #0a1628;
    color: #64748b;
    font-size: 11px;
    border-top: 1px solid #1e3a5f;
}
QGroupBox { font-size: 11px; }
QMessageBox { background-color: #131f2e; }
"""
